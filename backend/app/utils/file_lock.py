"""文件锁工具 - 参考青龙面板实现

防止并发写入导致的数据损坏
"""

import os
import time
import fcntl
import logging
from typing import Optional
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class FileLock:
    """文件锁实现（基于 fcntl）"""

    def __init__(self, lock_file: str, timeout: int = 10):
        """
        Args:
            lock_file: 锁文件路径
            timeout: 获取锁的超时时间（秒）
        """
        self.lock_file = lock_file
        self.timeout = timeout
        self.fd: Optional[int] = None

    def acquire(self) -> bool:
        """获取锁"""
        # 确保锁文件目录存在
        os.makedirs(os.path.dirname(self.lock_file), exist_ok=True)

        # 打开锁文件
        self.fd = os.open(self.lock_file, os.O_CREAT | os.O_RDWR)

        start_time = time.time()
        while True:
            try:
                # 尝试获取排他锁（非阻塞）
                fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                logger.debug(f"获取文件锁成功: {self.lock_file}")
                return True
            except (IOError, OSError):
                # 锁被占用，检查超时
                if time.time() - start_time >= self.timeout:
                    logger.warning(f"获取文件锁超时: {self.lock_file}")
                    os.close(self.fd)
                    self.fd = None
                    return False
                # 等待一小段时间后重试
                time.sleep(0.1)

    def release(self) -> None:
        """释放锁"""
        if self.fd is not None:
            try:
                fcntl.flock(self.fd, fcntl.LOCK_UN)
                os.close(self.fd)
                logger.debug(f"释放文件锁: {self.lock_file}")
            except Exception as e:
                logger.error(f"释放文件锁失败: {e}")
            finally:
                self.fd = None

    def __enter__(self):
        """上下文管理器入口"""
        if not self.acquire():
            raise TimeoutError(f"无法获取文件锁: {self.lock_file}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.release()


@contextmanager
def file_lock(file_path: str, timeout: int = 10):
    """文件锁上下文管理器

    用法:
        with file_lock('/path/to/file.txt'):
            # 在这里安全地写入文件
            with open('/path/to/file.txt', 'w') as f:
                f.write('data')
    """
    lock_file = f"{file_path}.lock"
    lock = FileLock(lock_file, timeout)

    try:
        if not lock.acquire():
            raise TimeoutError(f"无法获取文件锁: {lock_file}")
        yield
    finally:
        lock.release()
        # 清理锁文件
        try:
            if os.path.exists(lock_file):
                os.remove(lock_file)
        except Exception:
            pass


def write_file_with_lock(file_path: str, content: str, timeout: int = 10) -> bool:
    """带锁的文件写入（参考青龙）

    Args:
        file_path: 文件路径
        content: 文件内容
        timeout: 锁超时时间

    Returns:
        是否写入成功
    """
    try:
        with file_lock(file_path, timeout):
            # 确保目录存在
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            # 写入文件
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
        return True
    except Exception as e:
        logger.error(f"写入文件失败 {file_path}: {e}")
        return False


def read_file_with_lock(file_path: str, timeout: int = 10) -> Optional[str]:
    """带锁的文件读取

    Args:
        file_path: 文件路径
        timeout: 锁超时时间

    Returns:
        文件内容，失败返回 None
    """
    try:
        with file_lock(file_path, timeout):
            if not os.path.exists(file_path):
                return None
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
    except Exception as e:
        logger.error(f"读取文件失败 {file_path}: {e}")
        return None
