"""日志文件管理器 - 参考青龙面板实现"""
import os
import threading
from datetime import datetime
from typing import Optional, Callable


class LogStreamManager:
    """管理日志文件写入流，避免频繁打开文件"""

    def __init__(self, max_file_size: int = 10 * 1024 * 1024):  # 默认 10MB
        self._streams = {}  # {file_path: file_handle}
        self._file_sizes = {}  # {file_path: current_size}
        self._lock = threading.Lock()
        self._max_file_size = max_file_size

    def write(self, file_path: str, data: str) -> None:
        """写入数据到日志文件（带大小限制）"""
        with self._lock:
            if file_path not in self._streams:
                # 确保目录存在
                os.makedirs(os.path.dirname(file_path), exist_ok=True)
                # 创建文件流
                self._streams[file_path] = open(file_path, 'a', encoding='utf-8', buffering=1)
                # 初始化文件大小
                self._file_sizes[file_path] = os.path.getsize(file_path) if os.path.exists(file_path) else 0

            # 检查文件大小限制
            data_size = len(data.encode('utf-8'))
            current_size = self._file_sizes.get(file_path, 0)

            if current_size + data_size > self._max_file_size:
                # 超过大小限制，写入截断提示
                truncate_msg = f"\n\n[日志已截断] 文件大小超过 {self._max_file_size / 1024 / 1024:.1f}MB 限制\n"
                stream = self._streams[file_path]
                stream.write(truncate_msg)
                stream.flush()
                # 关闭流，不再写入
                self.close_stream(file_path)
                return

            # 正常写入
            stream = self._streams[file_path]
            stream.write(data)
            stream.flush()
            self._file_sizes[file_path] = current_size + data_size

    def close_stream(self, file_path: str) -> None:
        """关闭指定文件的流"""
        with self._lock:
            if file_path in self._streams:
                self._streams[file_path].close()
                del self._streams[file_path]
            if file_path in self._file_sizes:
                del self._file_sizes[file_path]

    def close_all(self) -> None:
        """关闭所有流"""
        with self._lock:
            for stream in self._streams.values():
                stream.close()
            self._streams.clear()
            self._file_sizes.clear()

    def set_max_file_size(self, size: int) -> None:
        """设置最大文件大小"""
        with self._lock:
            self._max_file_size = size


# 全局单例
log_stream_manager = LogStreamManager()


def get_log_path(task_id: int, log_dir: str) -> str:
    """
    获取任务日志文件路径
    格式：logs/task_{task_id}/YYYY-MM-DD-HH-mm-ss-SSS.log
    """
    task_log_dir = os.path.join(log_dir, f"task_{task_id}")
    os.makedirs(task_log_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d-%H-%M-%S-%f")[:-3]  # 毫秒
    log_filename = f"{timestamp}.log"
    return os.path.join(task_log_dir, log_filename)


def get_relative_log_path(task_id: int) -> str:
    """获取相对日志路径（用于存储到数据库）"""
    timestamp = datetime.now().strftime("%Y-%m-%d-%H-%M-%S-%f")[:-3]
    return f"task_{task_id}/{timestamp}.log"


def read_log_file(log_path: str, log_dir: str) -> str:
    """读取日志文件内容"""
    full_path = os.path.join(log_dir, log_path)
    if not os.path.exists(full_path):
        return ""

    try:
        with open(full_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        return f"读取日志失败: {str(e)}"


def list_log_files(task_id: int, log_dir: str) -> list:
    """列出任务的所有日志文件"""
    task_log_dir = os.path.join(log_dir, f"task_{task_id}")
    if not os.path.exists(task_log_dir):
        return []

    log_files = []
    for filename in sorted(os.listdir(task_log_dir), reverse=True):
        if filename.endswith('.log'):
            file_path = os.path.join(task_log_dir, filename)
            stat = os.stat(file_path)
            log_files.append({
                'filename': filename,
                'path': f"task_{task_id}/{filename}",
                'size': stat.st_size,
                'created_at': datetime.fromtimestamp(stat.st_ctime).isoformat(),
            })

    return log_files


def delete_log_file(log_path: str, log_dir: str) -> bool:
    """删除日志文件"""
    full_path = os.path.join(log_dir, log_path)
    if os.path.exists(full_path):
        try:
            os.remove(full_path)
            return True
        except Exception:
            return False
    return False


def clean_old_logs(log_dir: str, days: int = 7) -> int:
    """清理指定天数之前的日志文件

    Args:
        log_dir: 日志目录
        days: 保留天数，默认 7 天

    Returns:
        删除的文件数量
    """
    import time

    if not os.path.exists(log_dir):
        return 0

    cutoff_time = time.time() - (days * 24 * 60 * 60)
    deleted_count = 0

    # 遍历所有任务目录
    for task_dir in os.listdir(log_dir):
        task_path = os.path.join(log_dir, task_dir)
        if not os.path.isdir(task_path) or not task_dir.startswith('task_'):
            continue

        # 遍历任务目录下的日志文件
        for filename in os.listdir(task_path):
            if not filename.endswith('.log'):
                continue

            file_path = os.path.join(task_path, filename)
            try:
                # 检查文件修改时间
                if os.path.getmtime(file_path) < cutoff_time:
                    os.remove(file_path)
                    deleted_count += 1
            except Exception:
                continue

        # 如果任务目录为空，删除目录
        try:
            if not os.listdir(task_path):
                os.rmdir(task_path)
        except Exception:
            pass

    return deleted_count

