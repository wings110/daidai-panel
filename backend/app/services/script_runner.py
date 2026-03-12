"""脚本执行器 - 安全地执行用户脚本"""

import os
import subprocess
import logging
from typing import Optional, Callable
from dataclasses import dataclass, field
from pathlib import Path

from app.utils.command_validator import (
    validate_command,
    sanitize_env_vars,
    CommandValidationError,
    ALLOWED_INTERPRETERS
)

logger = logging.getLogger(__name__)


@dataclass
class ScriptResult:
    """脚本执行结果"""
    returncode: int
    output: str
    process: Optional[subprocess.Popen] = None


def run_command(
    command: str,
    scripts_dir: str,
    timeout: int = 300,
    env_vars: Optional[dict] = None,
    max_log_size: int = 10 * 1024 * 1024,
    on_output: Optional[Callable] = None,
) -> ScriptResult:
    """安全执行命令（支持完整命令格式，如 "python script.py"）

    Args:
        command: 完整命令，如 "python script.py" 或 "node app.js"
        scripts_dir: 脚本根目录
        timeout: 超时时间（秒）
        env_vars: 注入的环境变量
        max_log_size: 最大日志大小（字节）
        on_output: 逐行输出回调函数，签名 (line: str) -> None

    Returns:
        ScriptResult: 执行结果

    Raises:
        ValueError: 参数非法
        FileNotFoundError: 脚本文件不存在
    """
    # 1. 使用安全验证器验证命令
    try:
        interpreter, full_path = validate_command(command, scripts_dir)
    except CommandValidationError as e:
        error_msg = f"命令验证失败: {str(e)}\n"
        logger.error(error_msg)
        if on_output:
            on_output(error_msg)
        return ScriptResult(returncode=1, output=error_msg)

    # 2. 构建执行命令 (使用参数列表，不使用 shell=True)
    if interpreter == "python" or interpreter == "python3":
        # Python 添加 -u 参数禁用缓冲，实现实时输出
        cmd = [interpreter, "-u", full_path]
    elif interpreter == "ts-node":
        cmd = ["npx", "ts-node", full_path]
    else:
        cmd = [interpreter, full_path]

    # 3. 构建安全的环境变量
    env = {}
    # 保留必要的系统环境变量
    for key in ['PATH', 'SYSTEMROOT', 'PATHEXT', 'TEMP', 'TMP', 'HOME', 'USER']:
        if key in os.environ:
            env[key] = os.environ[key]

    # 添加传入的环境变量（经过清理）
    if env_vars:
        safe_env = sanitize_env_vars(env_vars)
        env.update(safe_env)

    logger.info(f"执行命令: {' '.join(cmd)}")

    try:
        # 4. 使用 subprocess.Popen 执行命令（不使用 shell=True）
        process = subprocess.Popen(
            cmd,  # 参数列表形式，防止 shell 注入
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env=env,
            cwd=scripts_dir,
            encoding='utf-8',
            errors='replace',
            bufsize=1,
            universal_newlines=True,
            # 关键：不使用 shell=True
        )

        # 5. 读取输出，限制最大大小
        output_chunks = []
        total_size = 0
        truncated = False

        for line in iter(process.stdout.readline, ''):
            if not line:
                break
            total_size += len(line)
            if total_size > max_log_size:
                truncated = True
                break
            output_chunks.append(line)
            if on_output:
                try:
                    on_output(line)
                except Exception:
                    pass

        # 6. 等待进程结束，处理超时
        try:
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            logger.warning(f"脚本执行超时 ({timeout}s)，正在终止进程...")
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                logger.error("进程终止失败，强制杀死进程")
                process.kill()
                process.wait()
            output_chunks.append(f"\n[超时] 脚本执行超过 {timeout} 秒，已强制终止\n")

        output = "".join(output_chunks)
        if truncated:
            output += f"\n[截断] 日志输出超过 {max_log_size // 1024 // 1024}MB，已自动截断\n"

        return ScriptResult(
            returncode=process.returncode if process.returncode is not None else 1,
            output=output,
            process=process,
        )

    except FileNotFoundError:
        error_msg = f"运行环境未安装: {interpreter}\n"
        logger.error(error_msg)
        if on_output:
            on_output(error_msg)
        return ScriptResult(returncode=1, output=error_msg)
    except Exception as e:
        error_msg = f"脚本执行异常: {str(e)}\n"
        logger.error(error_msg, exc_info=True)
        if on_output:
            on_output(error_msg)
        return ScriptResult(returncode=1, output=error_msg)

