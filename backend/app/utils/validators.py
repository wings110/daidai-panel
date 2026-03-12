"""
输入验证和数据清理工具函数
"""
from typing import Any, Optional


def safe_strip(value: Any, default: str = "") -> str:
    """
    安全地对值执行 strip 操作

    Args:
        value: 任意类型的值
        default: 默认值（当 value 为 None 或空时返回）

    Returns:
        清理后的字符串
    """
    if value is None:
        return default
    if isinstance(value, str):
        return value.strip()
    return str(value).strip() if value != "" else default


def safe_str(value: Any, default: str = "") -> str:
    """
    安全地将值转换为字符串

    Args:
        value: 任意类型的值
        default: 默认值（当 value 为 None 时返回）

    Returns:
        字符串值
    """
    if value is None:
        return default
    if isinstance(value, str):
        return value
    return str(value)


def safe_int(value: Any, default: int = 0) -> int:
    """
    安全地将值转换为整数

    Args:
        value: 任意类型的值
        default: 默认值（当转换失败时返回）

    Returns:
        整数值
    """
    if value is None:
        return default
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def safe_bool(value: Any, default: bool = False) -> bool:
    """
    安全地将值转换为布尔值

    Args:
        value: 任意类型的值
        default: 默认值（当 value 为 None 时返回）

    Returns:
        布尔值
    """
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in ("true", "1", "yes", "on")
    return bool(value)


def validate_string_length(value: str, max_length: int, field_name: str = "字段") -> Optional[str]:
    """
    验证字符串长度

    Args:
        value: 要验证的字符串
        max_length: 最大长度
        field_name: 字段名称（用于错误消息）

    Returns:
        如果验证失败，返回错误消息；否则返回 None
    """
    if len(value) > max_length:
        return f"{field_name}长度不能超过 {max_length} 个字符"
    return None


def validate_required(value: Any, field_name: str = "字段") -> Optional[str]:
    """
    验证必填字段

    Args:
        value: 要验证的值
        field_name: 字段名称（用于错误消息）

    Returns:
        如果验证失败，返回错误消息；否则返回 None
    """
    if value is None or (isinstance(value, str) and not value.strip()):
        return f"{field_name}不能为空"
    return None
