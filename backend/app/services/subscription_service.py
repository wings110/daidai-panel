"""订阅执行服务（参考青龙面板）"""

import os
import logging
import tempfile
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


def execute_subscription(sub_id: int, app) -> None:
    """执行订阅拉取任务

    Args:
        sub_id: 订阅 ID
        app: Flask 应用实例
    """
    with app.app_context():
        from app.extensions import db
        from app.models.subscription import Subscription
        from app.models.sub_log import SubLog
        from app.services.git_service import GitService, save_ssh_key_to_file

        sub = Subscription.query.get(sub_id)
        if not sub:
            logger.error(f"订阅 ID={sub_id} 不存在")
            return

        if not sub.enabled:
            logger.info(f"订阅 [{sub.name}] 已禁用，跳过执行")
            return

        # 创建日志记录
        log_entry = SubLog(
            sub_id=sub.id,
            started_at=datetime.utcnow(),
            status=SubLog.STATUS_RUNNING,
        )
        db.session.add(log_entry)
        db.session.commit()

        log_messages = []

        def _log(msg: str):
            """记录日志"""
            log_messages.append(msg)
            logger.info(f"[订阅 {sub.name}] {msg}")

        try:
            # 执行订阅前钩子
            if sub.sub_before:
                _log("执行 sub_before 钩子...")
                _run_subscription_hook(sub.sub_before, app.config["SCRIPTS_DIR"], _log)

            # 准备 SSH 密钥
            ssh_key_path = None
            if sub.use_ssh_key and sub.ssh_key:
                ssh_key_path = save_ssh_key_to_file(
                    sub.ssh_key.private_key,
                    sub.ssh_key.id,
                    app.config["DATA_DIR"]
                )
                _log(f"使用 SSH 密钥: {sub.ssh_key.name}")

            # 执行 Git 操作
            git_service = GitService(app.config["SCRIPTS_DIR"])

            if sub.sub_type == "git":
                # Git 仓库订阅
                _log(f"开始拉取 Git 仓库: {sub.url}")
                _log(f"分支: {sub.branch}, 拉取选项: {sub.pull_option}")

                # 使用临时目录克隆/拉取
                with tempfile.TemporaryDirectory() as temp_dir:
                    success, message = git_service.clone_or_pull(
                        repo_url=sub.url,
                        target_dir=temp_dir,
                        branch=sub.branch,
                        ssh_key_path=ssh_key_path,
                        pull_option=sub.pull_option,
                    )

                    if not success:
                        raise Exception(message)

                    _log(message)

                    # 过滤文件
                    _log("过滤文件...")
                    files = git_service.filter_files(
                        repo_dir=temp_dir,
                        whitelist=sub.whitelist,
                        blacklist=sub.blacklist,
                    )
                    _log(f"匹配到 {len(files)} 个文件")

                    if files:
                        # 复制文件到目标目录
                        _log(f"复制文件到: {sub.target_dir or '根目录'}")
                        success_count, fail_count = git_service.copy_files(
                            repo_dir=temp_dir,
                            target_dir=sub.target_dir,
                            files=files,
                        )
                        _log(f"复制完成: 成功 {success_count}, 失败 {fail_count}")

                        if fail_count > 0:
                            _log(f"警告: {fail_count} 个文件复制失败")
                    else:
                        _log("没有匹配的文件需要复制")

            else:
                # 文件订阅（HTTP/HTTPS）
                _log(f"开始下载文件: {sub.url}")
                # TODO: 实现 HTTP 文件下载
                raise NotImplementedError("文件订阅功能尚未实现")

            # 执行订阅后钩子
            if sub.sub_after:
                _log("执行 sub_after 钩子...")
                _run_subscription_hook(sub.sub_after, app.config["SCRIPTS_DIR"], _log)

            # 更新订阅状态
            sub.last_pull_at = datetime.utcnow()
            sub.last_pull_status = 0  # 成功
            sub.last_pull_message = "\n".join(log_messages)

            log_entry.status = SubLog.STATUS_SUCCESS
            log_entry.ended_at = datetime.utcnow()
            log_entry.message = "\n".join(log_messages)

            db.session.commit()
            _log("订阅执行成功")

        except Exception as e:
            error_msg = f"订阅执行失败: {str(e)}"
            _log(error_msg)
            logger.error(error_msg, exc_info=True)

            # 更新订阅状态
            sub.last_pull_at = datetime.utcnow()
            sub.last_pull_status = 1  # 失败
            sub.last_pull_message = "\n".join(log_messages)

            log_entry.status = SubLog.STATUS_FAILED
            log_entry.ended_at = datetime.utcnow()
            log_entry.message = "\n".join(log_messages)

            db.session.commit()


def _run_subscription_hook(script_content: str, scripts_dir: str, log_func) -> None:
    """执行订阅钩子脚本"""
    import subprocess
    import tempfile

    if not script_content or not script_content.strip():
        return

    try:
        # 创建临时脚本文件
        with tempfile.NamedTemporaryFile(
            mode='w',
            suffix='.sh',
            delete=False,
            dir=scripts_dir,
            encoding='utf-8'
        ) as tmp_file:
            tmp_file.write(script_content)
            tmp_path = tmp_file.name

        # 执行脚本
        process = subprocess.Popen(
            ["bash", tmp_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            cwd=scripts_dir,
            encoding='utf-8',
            errors='replace',
        )

        for line in iter(process.stdout.readline, ''):
            if not line:
                break
            log_func(line.rstrip())

        process.wait(timeout=60)

        if process.returncode != 0:
            log_func(f"钩子脚本执行失败，退出码: {process.returncode}")

    except subprocess.TimeoutExpired:
        log_func("钩子脚本执行超时")
        process.kill()
    except Exception as e:
        log_func(f"钩子脚本执行异常: {e}")
    finally:
        # 清理临时文件
        try:
            if 'tmp_path' in locals():
                os.unlink(tmp_path)
        except Exception:
            pass
