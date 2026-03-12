"""Git 仓库管理服务（参考青龙面板）"""

import os
import logging
import tempfile
import shutil
from typing import Optional, List, Tuple
from pathlib import Path
import subprocess

logger = logging.getLogger(__name__)


class GitService:
    """Git 仓库操作服务"""

    def __init__(self, scripts_dir: str):
        self.scripts_dir = scripts_dir

    def clone_or_pull(
        self,
        repo_url: str,
        target_dir: str,
        branch: str = "main",
        ssh_key_path: Optional[str] = None,
        pull_option: str = "merge",
    ) -> Tuple[bool, str]:
        """克隆或拉取 Git 仓库

        Args:
            repo_url: 仓库 URL
            target_dir: 目标目录（相对于 scripts_dir）
            branch: 分支名
            ssh_key_path: SSH 私钥路径（可选）
            pull_option: 拉取选项 (merge/rebase/force)

        Returns:
            (是否成功, 消息)
        """
        full_target_dir = os.path.join(self.scripts_dir, target_dir)

        # 构建 Git 环境变量
        env = os.environ.copy()
        if ssh_key_path:
            # 使用 SSH 密钥
            env['GIT_SSH_COMMAND'] = f'ssh -i {ssh_key_path} -o StrictHostKeyChecking=no'

        try:
            if os.path.exists(os.path.join(full_target_dir, '.git')):
                # 仓库已存在，执行拉取
                return self._pull_repo(full_target_dir, branch, pull_option, env)
            else:
                # 仓库不存在，执行克隆
                return self._clone_repo(repo_url, full_target_dir, branch, env)
        except Exception as e:
            logger.error(f"Git 操作失败: {e}")
            return False, f"Git 操作失败: {str(e)}"

    def _clone_repo(
        self,
        repo_url: str,
        target_dir: str,
        branch: str,
        env: dict,
    ) -> Tuple[bool, str]:
        """克隆仓库"""
        try:
            # 确保父目录存在
            os.makedirs(os.path.dirname(target_dir), exist_ok=True)

            # 执行克隆
            cmd = ['git', 'clone', '--branch', branch, '--depth', '1', repo_url, target_dir]
            result = subprocess.run(
                cmd,
                env=env,
                capture_output=True,
                text=True,
                timeout=300,
            )

            if result.returncode == 0:
                logger.info(f"克隆仓库成功: {repo_url} -> {target_dir}")
                return True, f"克隆成功，分支: {branch}"
            else:
                error_msg = result.stderr or result.stdout
                logger.error(f"克隆仓库失败: {error_msg}")
                return False, f"克隆失败: {error_msg}"

        except subprocess.TimeoutExpired:
            return False, "克隆超时（5分钟）"
        except Exception as e:
            return False, f"克隆异常: {str(e)}"

    def _pull_repo(
        self,
        repo_dir: str,
        branch: str,
        pull_option: str,
        env: dict,
    ) -> Tuple[bool, str]:
        """拉取仓库更新"""
        try:
            # 切换到仓库目录
            original_dir = os.getcwd()
            os.chdir(repo_dir)

            try:
                # 1. 获取远程更新
                result = subprocess.run(
                    ['git', 'fetch', 'origin', branch],
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
                if result.returncode != 0:
                    return False, f"fetch 失败: {result.stderr}"

                # 2. 根据 pull_option 执行不同操作
                if pull_option == "force":
                    # 强制重置到远程分支
                    result = subprocess.run(
                        ['git', 'reset', '--hard', f'origin/{branch}'],
                        env=env,
                        capture_output=True,
                        text=True,
                        timeout=30,
                    )
                elif pull_option == "rebase":
                    # 变基
                    result = subprocess.run(
                        ['git', 'rebase', f'origin/{branch}'],
                        env=env,
                        capture_output=True,
                        text=True,
                        timeout=60,
                    )
                else:
                    # 默认合并
                    result = subprocess.run(
                        ['git', 'merge', f'origin/{branch}'],
                        env=env,
                        capture_output=True,
                        text=True,
                        timeout=60,
                    )

                if result.returncode == 0:
                    # 获取最新提交信息
                    commit_result = subprocess.run(
                        ['git', 'log', '-1', '--pretty=format:%h %s'],
                        capture_output=True,
                        text=True,
                        timeout=10,
                    )
                    commit_msg = commit_result.stdout.strip() if commit_result.returncode == 0 else ""
                    logger.info(f"拉取仓库成功: {repo_dir}")
                    return True, f"拉取成功 ({pull_option})\n最新提交: {commit_msg}"
                else:
                    error_msg = result.stderr or result.stdout
                    return False, f"拉取失败: {error_msg}"

            finally:
                os.chdir(original_dir)

        except subprocess.TimeoutExpired:
            return False, "拉取超时"
        except Exception as e:
            return False, f"拉取异常: {str(e)}"

    def filter_files(
        self,
        repo_dir: str,
        whitelist: str = "",
        blacklist: str = "",
    ) -> List[str]:
        """根据白名单和黑名单过滤文件

        Args:
            repo_dir: 仓库目录
            whitelist: 白名单 glob 模式，逗号分隔
            blacklist: 黑名单 glob 模式，逗号分隔

        Returns:
            符合条件的文件列表（相对路径）
        """
        import fnmatch

        all_files = []
        for root, dirs, files in os.walk(repo_dir):
            # 跳过 .git 目录
            if '.git' in dirs:
                dirs.remove('.git')

            for file in files:
                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, repo_dir)
                all_files.append(rel_path)

        # 应用白名单
        if whitelist:
            patterns = [p.strip() for p in whitelist.split(',') if p.strip()]
            filtered = []
            for file in all_files:
                if any(fnmatch.fnmatch(file, pattern) for pattern in patterns):
                    filtered.append(file)
            all_files = filtered

        # 应用黑名单
        if blacklist:
            patterns = [p.strip() for p in blacklist.split(',') if p.strip()]
            filtered = []
            for file in all_files:
                if not any(fnmatch.fnmatch(file, pattern) for pattern in patterns):
                    filtered.append(file)
            all_files = filtered

        return all_files

    def copy_files(
        self,
        repo_dir: str,
        target_dir: str,
        files: List[str],
    ) -> Tuple[int, int]:
        """复制文件到目标目录

        Args:
            repo_dir: 源仓库目录
            target_dir: 目标目录（相对于 scripts_dir）
            files: 要复制的文件列表（相对路径）

        Returns:
            (成功数量, 失败数量)
        """
        full_target_dir = os.path.join(self.scripts_dir, target_dir)
        os.makedirs(full_target_dir, exist_ok=True)

        success_count = 0
        fail_count = 0

        for file in files:
            try:
                src_path = os.path.join(repo_dir, file)
                dst_path = os.path.join(full_target_dir, file)

                # 确保目标目录存在
                os.makedirs(os.path.dirname(dst_path), exist_ok=True)

                # 复制文件
                shutil.copy2(src_path, dst_path)
                success_count += 1
            except Exception as e:
                logger.error(f"复制文件失败 {file}: {e}")
                fail_count += 1

        return success_count, fail_count


def generate_ssh_key_pair() -> Tuple[str, str]:
    """生成 SSH 密钥对

    Returns:
        (私钥, 公钥)
    """
    try:
        # 创建临时目录
        with tempfile.TemporaryDirectory() as temp_dir:
            key_path = os.path.join(temp_dir, 'id_rsa')

            # 生成密钥对
            result = subprocess.run(
                [
                    'ssh-keygen',
                    '-t', 'rsa',
                    '-b', '4096',
                    '-f', key_path,
                    '-N', '',  # 无密码
                    '-C', 'daidai-panel',
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode != 0:
                raise Exception(f"生成密钥失败: {result.stderr}")

            # 读取密钥
            with open(key_path, 'r') as f:
                private_key = f.read()
            with open(f"{key_path}.pub", 'r') as f:
                public_key = f.read()

            return private_key, public_key

    except Exception as e:
        logger.error(f"生成 SSH 密钥对失败: {e}")
        raise


def save_ssh_key_to_file(private_key: str, key_id: int, data_dir: str) -> str:
    """保存 SSH 私钥到文件

    Args:
        private_key: 私钥内容
        key_id: 密钥 ID
        data_dir: 数据目录

    Returns:
        密钥文件路径
    """
    ssh_dir = os.path.join(data_dir, 'ssh_keys')
    os.makedirs(ssh_dir, exist_ok=True)

    key_path = os.path.join(ssh_dir, f'id_rsa_{key_id}')

    # 写入私钥
    with open(key_path, 'w') as f:
        f.write(private_key)

    # 设置权限（仅所有者可读写）
    os.chmod(key_path, 0o600)

    return key_path
