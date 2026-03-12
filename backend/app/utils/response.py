"""统一响应格式"""

from flask import jsonify


def success_response(data=None, message: str | None = None, **kwargs):
    """成功响应

    Args:
        data: 响应数据
        message: 提示消息
        **kwargs: 其他字段（如total、page等）

    Returns:
        Flask jsonify响应
    """
    response = {"success": True}

    if message:
        response["message"] = message

    if data is not None:
        response["data"] = data

    # 添加其他字段（如分页信息）
    response.update(kwargs)

    return jsonify(response)


def error_response(message: str, code: int = 400, **kwargs):
    """错误响应

    Args:
        message: 错误消息
        code: HTTP状态码
        **kwargs: 其他字段

    Returns:
        Flask jsonify响应和状态码
    """
    response = {
        "success": False,
        "error": message
    }
    response.update(kwargs)

    return jsonify(response), code


def paginated_response(items: list, total: int, page: int, page_size: int):
    """分页响应

    Args:
        items: 数据列表
        total: 总数
        page: 当前页码
        page_size: 每页大小

    Returns:
        Flask jsonify响应
    """
    return success_response(
        data=items,
        total=total,
        page=page,
        page_size=page_size
    )
