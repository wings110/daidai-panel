"""命令验证工具 - 防止命令注入和路径遍历攻击"""

import os
import re
from pathlib import Path
from typing import Tuple, Optional


# 允许的解释器白名单
ALLOWED_INTERPRETERS = {
    'python': 'python',
    'python3': 'python3',
    'node': 'node',
    'ts-node': 'ts-node',
}

# 允许的文件扩展名
ALLOWED_EXTENSIONS = {'.py', '.js', '.ts', '.sh'}

# 安全的包名格式 (用于依赖管理)
# 支持: requests, requests==2.31.0, django>=3.0, flask~=2.0
PKG_NAME_PATTERN = re.compile(r'^[a-zA-Z0-9_\-\.]+([=<>!~]+[a-zA-Z0-9_\-\.]+)?$')


class CommandValidationError(Exception):
    """命令验证失败异常"""
    pass


def validate_command(command: str, scripts_dir: str) -> Tuple[str, str]:
    """
    严格验证任务命令的安全性

    Args:
        command: 用户输入的命令 (如 "python script.py")
        scripts_dir: 脚本根目录的绝对路径

    Returns:
        (interpreter, absolute_script_path): 验证通过的解释器和脚本绝对路径

    Raises:
        CommandValidationError: 验证失败时抛出异常
    """
    if not command or not command.strip():
        raise CommandValidationError("命令不能为空")

    # 1. 解析命令
    parts = command.strip().split(maxsplit=1)
    if len(parts) != 2:
        raise CommandValidationError(
            "命令格式错误，正确格式: <解释器> <脚本路径>\n"
            "示例: python script.py 或 node app.js"
        )

    interpreter, script_path = parts

    # 2. 验证解释器
    if interpreter not in ALLOWED_INTERPRETERS:
        raise CommandValidationError(
            f"不支持的解释器: {interpreter}\n"
            f"允许的解释器: {', '.join(ALLOWED_INTERPRETERS.keys())}"
        )

    # 3. 验证脚本路径格式
    # 禁止绝对路径
    if os.path.isabs(script_path):
        raise CommandValidationError("禁止使用绝对路径，请使用相对于脚本目录的路径")

    # 禁止包含危险字符
    dangerous_patterns = ['..', '~', '$', '`', ';', '|', '&', '>', '<', '\n', '\r']
    for pattern in dangerous_patterns:
        if pattern in script_path:
            raise CommandValidationError(f"脚本路径包含非法字符: {pattern}")

    # 4. 验证文件扩展名
    file_ext = Path(script_path).suffix.lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        raise CommandValidationError(
            f"不支持的文件类型: {file_ext}\n"
            f"允许的类型: {', '.join(ALLOWED_EXTENSIONS)}"
        )

    # 5. 构建绝对路径并验证
    try:
        scripts_base = Path(scripts_dir).resolve()
        full_path = (scripts_base / script_path).resolve()

        # 防止路径遍历攻击
        if not str(full_path).startswith(str(scripts_base)):
            raise CommandValidationError(
                "禁止访问脚本目录外的文件\n"
                f"脚本必须位于: {scripts_base}"
            )

        # 验证文件存在
        if not full_path.is_file():
            raise CommandValidationError(
                f"脚本文件不存在: {script_path}\n"
                "请先上传脚本文件"
            )

    except (ValueError, OSError) as e:
        raise CommandValidationError(f"无效的文件路径: {str(e)}")

    return interpreter, str(full_path)


def validate_script_path(script_path: str, scripts_dir: str) -> str:
    """
    验证脚本路径的安全性 (用于脚本管理接口)

    Args:
        script_path: 相对脚本路径
        scripts_dir: 脚本根目录

    Returns:
        absolute_path: 验证通过的绝对路径

    Raises:
        CommandValidationError: 验证失败
    """
    if not script_path or not script_path.strip():
        raise CommandValidationError("脚本路径不能为空")

    # 禁止绝对路径
    if os.path.isabs(script_path):
        raise CommandValidationError("禁止使用绝对路径")

    # 禁止危险字符
    dangerous_patterns = ['..', '~', '$', '`', ';', '|', '&', '\n', '\r']
    for pattern in dangerous_patterns:
        if pattern in script_path:
            raise CommandValidationError(f"路径包含非法字符: {pattern}")

    try:
        scripts_base = Path(scripts_dir).resolve()
        full_path = (scripts_base / script_path).resolve()

        # 防止路径遍历
        if not str(full_path).startswith(str(scripts_base)):
            raise CommandValidationError("禁止访问脚本目录外的文件")

        return str(full_path)

    except (ValueError, OSError) as e:
        raise CommandValidationError(f"无效的路径: {str(e)}")


def validate_package_name(pkg_name: str) -> bool:
    """
    验证包名格式 (用于依赖管理)

    Args:
        pkg_name: 包名

    Returns:
        bool: 是否合法
    """
    if not pkg_name or len(pkg_name) > 100:
        return False
    return bool(PKG_NAME_PATTERN.match(pkg_name))


def sanitize_env_vars(env_vars: dict) -> dict:
    """
    清理环境变量，移除危险变量

    Args:
        env_vars: 原始环境变量字典

    Returns:
        dict: 清理后的环境变量
    """
    # 危险的环境变量黑名单
    dangerous_vars = {
        'LD_PRELOAD',
        'LD_LIBRARY_PATH',
        'DYLD_INSERT_LIBRARIES',
        'PYTHONPATH',  # 可能被用于注入恶意模块
        'NODE_PATH',
    }

    # 只保留安全的环境变量
    safe_env = {}
    for key, value in env_vars.items():
        if key not in dangerous_vars:
            # 确保值是字符串且不包含危险字符
            if isinstance(value, str) and '\x00' not in value:
                safe_env[key] = value

    return safe_env
