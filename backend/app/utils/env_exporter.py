"""环境变量导出工具（参考青龙面板）"""

import os
import json
from typing import List, Dict
from pathlib import Path
from app.utils.file_lock import write_file_with_lock


def escape_shell_value(value: str) -> str:
    """转义 Shell 特殊字符"""
    # 如果包含特殊字符，用单引号包裹并转义单引号
    if any(c in value for c in [' ', '$', '`', '"', '\\', '\n', '\t', '!', '*', '?', '[', ']', '(', ')', '{', '}', ';', '&', '|', '<', '>']):
        return f"'{value.replace(chr(39), chr(39) + chr(92) + chr(39) + chr(39))}'"
    return value


def escape_js_value(value: str) -> str:
    """转义 JavaScript 特殊字符"""
    return json.dumps(value)


def escape_py_value(value: str) -> str:
    """转义 Python 特殊字符"""
    return repr(value)


def export_env_to_shell(env_vars: List[Dict], output_path: str) -> None:
    """导出环境变量为 Shell 格式（.env 文件）- 带文件锁

    参考青龙：qinglong-develop/back/services/env.ts:202-241

    Args:
        env_vars: 环境变量列表 [{"name": "KEY", "value": "value"}, ...]
        output_path: 输出文件路径
    """
    lines = ["#!/bin/bash", "# 呆呆面板 - 环境变量", ""]

    # 按名称分组（同名变量用 & 连接）
    grouped = {}
    for env in env_vars:
        name = env["name"]
        value = env["value"]
        if name in grouped:
            grouped[name].append(value)
        else:
            grouped[name] = [value]

    # 生成 Shell 格式
    for name, values in sorted(grouped.items()):
  if len(values) == 1:
            # 单个值
            escaped_value = escape_shell_value(values[0])
            lines.append(f'export {name}={escaped_value}')
        else:
            # 多个值用 & 连接
            combined_value = "&".join(values)
            escaped_value = escape_shell_value(combined_value)
            lines.append(f'export {name}={escaped_value}')

    content = '\n'.join(lines) + '\n'

    # 使用文件锁写入
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    write_file_with_lock(output_path, content)

    # 设置可执行权限（Unix 系统）
    try:
        os.chmod(output_path, 0o755)
    except Exception:
        pass


def export_env_to_js(env_vars: List[Dict], output_path: str) -> None:
    """导出环境变量为 JavaScript 格式（.env.js 文件）- 带文件锁

    参考青龙：qinglong-develop/back/services/env.ts:202-241

    Args:
        env_vars: 环境变量列表
        output_path: 输出文件路径
    """
    lines = ["// 呆呆面板 - 环境变量", ""]

    # 按名称分组
    grouped = {}
    for env in env_vars:
        name = env["name"]
        value = env["value"]
        if name in grouped:
            grouped[name].append(value)
        else:
            grouped[name] = [value]

    # 生成 JavaScript 格式
    for name, values in sorted(grouped.items()):
        if len(values) == 1:
            escaped_value = escape_js_value(values[0])
            lines.append(f'process.env.{name} = {escaped_value};')
        else:
            combined_value = "&".join(values)
            escaped_value = escape_js_value(combined_value)
            lines.append(f'process.env.{name} = {escaped_value};')

    content = '\n'.join(lines) + '\n'

    # 使用文件锁写入
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    write_file_with_lock(output_path, content)


def export_env_to_python(env_vars: List[Dict], output_path: str) -> None:
    """导出环境变量为 Python 格式（.env.py 文件）- 带文件锁

    参考青龙：qinglong-develop/back/services/env.ts:202-241

    Args:
        env_vars: 环境变量列表
        output_path: 输出文件路径
    """
    lines = ["# -*- coding: utf-8 -*-", "# 呆呆面板 - 环境变量", "import os", ""]

    # 按名称分组
    grouped = {}
    for env in env_vars:
        name = env["name"]
        value = env["value"]
        if name in grouped:
            grouped[name].append(value)
        else:
            grouped[name] = [value]

    # 生成 Python 格式
    for name, values in sorted(grouped.items()):
        if len(values) == 1:
            escaped_value = escape_py_value(values[0])
            lines.append(f'os.environ[{repr(name)}] = {escaped_value}')
        else:
            combined_value = "&".join(values)
            escaped_value = escape_py_value(combined_value)
            lines.append(f'os.environ[{repr(name)}] = {escaped_value}')

    content = '\n'.join(lines) + '\n'

    # 使用文件锁写入
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    write_file_with_lock(output_path, content)


def export_all_formats(env_vars: List[Dict], base_dir: str) -> Dict[str, str]:
    """导出所有格式的环境变量文件 - 带文件锁

    Args:
        env_vars: 环境变量列表（只包含已启用的）
        base_dir: 输出目录

    Returns:
        导出的文件路径字典 {"shell": "...", "js": "...", "python": "..."}
    """
    base_path = Path(base_dir)
    base_path.mkdir(parents=True, exist_ok=True)

    paths = {
        "shell": str(base_path / ".env"),
        "js": str(base_path / ".env.js"),
        "python": str(base_path / ".env.py"),
    }

    export_env_to_shell(env_vars, paths["shell"])
    export_env_to_js(env_vars, paths["js"])
    export_env_to_python(env_vars, paths["python"])

    return paths
