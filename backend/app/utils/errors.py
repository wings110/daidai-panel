"""统一错误处理"""


class APIError(Exception):
    """API业务异常基类"""

    def __init__(self, message: str, code: int = 400, data: dict | None = None):
        self.message = message
        self.code = code
        self.data = data or {}
        super().__init__(self.message)


class ValidationError(APIError):
    """参数验证错误"""

    def __init__(self, message: str, field: str | None = None):
        data = {"field": field} if field else {}
        super().__init__(message, code=400, data=data)


class NotFoundError(APIError):
    """资源不存在错误"""

    def __init__(self, message: str = "资源不存在"):
        super().__init__(message, code=404)


class UnauthorizedError(APIError):
    """未授权错误"""

    def __init__(self, message: str = "未授权访问"):
        super().__init__(message, code=401)


class ForbiddenError(APIError):
    """禁止访问错误"""

    def __init__(self, message: str = "无权限访问"):
        super().__init__(message, code=403)


class ConflictError(APIError):
    """资源冲突错误"""

    def __init__(self, message: str = "资源冲突"):
        super().__init__(message, code=409)


class ServerError(APIError):
    """服务器内部错误"""

    def __init__(self, message: str = "服务器内部错误"):
        super().__init__(message, code=500)
