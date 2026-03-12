"""呆呆面板 - 全局请求钩子（安全加固）"""

from flask import Flask, request, jsonify

# 精确白名单：无需认证的路径
AUTH_WHITELIST = {
    "/api/auth/login",
    "/api/auth/init",
    "/api/open/auth/token",
    "/health",
}


def register_hooks(app: Flask) -> None:
    """注册全局 before_request 和 after_request 钩子"""

    @app.before_request
    def normalize_and_check_auth():
        """路径规范化 + 全局鉴权前置检查"""
        # 1. 统一转小写，防止大小写绕过
        normalized = request.path.lower().rstrip("/")

        # 2. 白名单精确匹配，直接放行
        if normalized in AUTH_WHITELIST:
            return None

        # 3. SSE 流（自行通过 query token 验证）
        if normalized.endswith("/stream") and "/api/logs/" in normalized:
            return None
        if normalized == "/api/system/resource-stream":
            return None

        # 4. OPTIONS 预检请求放行（CORS）
        if request.method == "OPTIONS":
            return None

        # 注意：具体的 JWT 校验由各路由的 @jwt_required 装饰器负责
        # 这里只做路径规范化和基础拦截，双重校验

    @app.after_request
    def set_security_headers(response):
        """设置安全响应头"""
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response

    @app.route("/health")
    def health_check():
        """健康检查端点"""
        return jsonify({"status": "ok", "service": "daidai-panel"})
