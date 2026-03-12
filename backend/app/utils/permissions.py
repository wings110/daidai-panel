"""权限控制装饰器"""

from functools import wraps

from flask import jsonify
from flask_jwt_extended import get_jwt_identity

from app.models.user import User


def require_role(role: str):
    """要求用户具有指定角色或更高权限

    用法:
        @jwt_required()
        @require_role("operator")
        def some_api():
            ...
    """
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            identity = get_jwt_identity()
            # 开放 API Token 跳过角色检查
            if isinstance(identity, str) and identity.startswith("app:"):
                return fn(*args, **kwargs)

            user = User.query.filter_by(username=identity).first()
            if not user:
                return jsonify({"error": "用户不存在"}), 401
            if not user.enabled:
                return jsonify({"error": "账户已禁用"}), 403
            if not user.has_permission(role):
                return jsonify({"error": "权限不足"}), 403

            return fn(*args, **kwargs)
        return wrapper
    return decorator


def require_admin(fn):
    """要求管理员权限的快捷装饰器"""
    return require_role(User.ROLE_ADMIN)(fn)


def get_current_user() -> User | None:
    """获取当前请求的用户对象"""
    identity = get_jwt_identity()
    if not identity or (isinstance(identity, str) and identity.startswith("app:")):
        return None
    return User.query.filter_by(username=identity).first()
