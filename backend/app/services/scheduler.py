"""调度器服务 - APScheduler 管理定时任务"""

import logging
import os
import threading
from datetime import datetime
from typing import Optional, Dict, Callable

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

# 全局调度器实例
_scheduler: Optional[BackgroundScheduler] = None
# 正在运行的任务进程 {task_id: subprocess.Popen}
_running_processes: Dict[int, object] = {}
_process_lock = threading.Lock()
# 并发控制信号量
_task_semaphore: Optional[threading.Semaphore] = None

# 实时日志缓冲 {task_id: [line1, line2, ...]}
_live_logs: dict[int, list[str]] = {}
# 任务完成标记 {task_id: True}
_live_done: dict[int, bool] = {}
_log_lock = threading.Lock()


def get_live_log(task_id: int) -> tuple[list[str], bool]:
    """获取任务的实时日志和完成状态（线程安全）"""
    with _log_lock:
        # 返回副本，避免外部修改
        return _live_logs.get(task_id, [])[:], _live_done.get(task_id, False)


def init_scheduler(app) -> None:
    """初始化调度器并加载所有已启用任务"""
    global _scheduler, _task_semaphore

    # 如果调度器已经启动，不重复创建
    if _scheduler is not None:
        logger.info("任务调度器已存在，跳过初始化")
        return

    _scheduler = BackgroundScheduler()
    _scheduler.start()

    # 初始化并发控制
    with app.app_context():
        from app.models.system_config import SystemConfig
        max_concurrent = SystemConfig.get_int("max_concurrent_tasks", 5)
        _task_semaphore = threading.Semaphore(max(1, max_concurrent))

    with app.app_context():
        from app.models.task import Task
        tasks = Task.query.filter_by(status=Task.STATUS_ENABLED).all()
        for task in tasks:
            add_job(task)
        logger.info(f"调度器已启动，加载了 {len(tasks)} 个任务")


def shutdown_scheduler() -> None:
    """优雅关闭调度器，等待运行中任务完成"""
    global _scheduler
    if _scheduler:
        _scheduler.shutdown(wait=False)  # 不再接受新任务
        logger.info("调度器已停止接受新任务")

        # 等待所有运行中进程结束（最多 60 秒）
        import time
        waited = 0
        while waited < 60:
            with _process_lock:
                running = {tid: p for tid, p in _running_processes.items() if p.poll() is None}
            if not running:
                break
            logger.info(f"等待 {len(running)} 个运行中任务完成...")
            time.sleep(2)
            waited += 2

        # 超时仍在运行的强制终止
        with _process_lock:
            for tid, p in list(_running_processes.items()):
                if p.poll() is None:
                    p.terminate()
                    logger.warning(f"任务 ID={tid} 被强制终止（优雅停机超时）")
            _running_processes.clear()

        logger.info("调度器已完全关闭")


def add_job(task) -> None:
    """添加/更新定时任务到调度器"""
    if not _scheduler:
        return

    job_id = f"task_{task.id}"

    # 如果已存在则先移除
    if _scheduler.get_job(job_id):
        _scheduler.remove_job(job_id)

    if task.status != 1:  # 非启用状态不添加
        return

    try:
        trigger = _parse_cron(task.cron_expression)
        _scheduler.add_job(
            func=_execute_task,
            trigger=trigger,
            id=job_id,
            args=[task.id],
            replace_existing=True,
            misfire_grace_time=60,
        )
        logger.info(f"任务 [{task.name}] 已添加到调度器，Cron: {task.cron_expression}")
    except Exception as e:
        logger.error(f"添加任务 [{task.name}] 到调度器失败: {e}")


def update_job(task) -> None:
    """更新调度器中的任务"""
    add_job(task)


def remove_job(task_id: int) -> None:
    """从调度器移除任务"""
    if not _scheduler:
        return

    job_id = f"task_{task_id}"
    if _scheduler.get_job(job_id):
        _scheduler.remove_job(job_id)
        logger.info(f"任务 ID={task_id} 已从调度器移除")


def run_task_now(task) -> None:
    """立即执行任务（在新线程中）"""
    thread = threading.Thread(
        target=_execute_task,
        args=[task.id],
        daemon=True,
    )
    thread.start()


def stop_running_task(task_id: int) -> bool:
    """停止正在运行的任务"""
    with _process_lock:
        process = _running_processes.get(task_id)
        if process and process.poll() is None:
            process.terminate()
            logger.info(f"任务 ID={task_id} 已被终止")
            return True
    return False


def _execute_task(task_id: int) -> None:
    """执行任务的核心逻辑（在独立线程中运行）"""
    from flask import current_app
    try:
        app = current_app._get_current_object()
    except RuntimeError:
        from wsgi import app

    # 并发控制：超过并发数则排队等待
    if _task_semaphore:
        _task_semaphore.acquire()

    try:
        _execute_task_inner(task_id, app)
    except Exception as e:
        # 捕获 _execute_task_inner 中未处理的异常
        # 确保任务状态被正确重置，日志中记录错误
        logger.error(f"任务 ID={task_id} 执行时发生未捕获异常: {e}", exc_info=True)
        try:
            with app.app_context():
                from app.extensions import db
                from app.models.task import Task
                from app.models.log import TaskLog

                task = Task.query.get(task_id)
                if task and task.status == Task.STATUS_RUNNING:
                    task.status = Task.STATUS_ENABLED
                    task.last_run_status = Task.RUN_FAILED
                    task.pid = None
                    task.log_path = None
                    db.session.commit()

                # 写入错误到实时日志，让前端能看到
                error_msg = f"[系统错误] 任务执行异常: {str(e)}\n"
                with _log_lock:
                    _live_logs.setdefault(task_id, []).append(error_msg)
                    _live_done[task_id] = True

                # 清理运行中进程记录
                with _process_lock:
                    _running_processes.pop(task_id, None)
        except Exception as cleanup_error:
            logger.error(f"任务 ID={task_id} 异常恢复失败: {cleanup_error}")
    finally:
        if _task_semaphore:
            _task_semaphore.release()


def _execute_task_inner(task_id: int, app) -> None:
    """任务执行的内部逻辑"""
    from app.services.script_runner import run_command
    from app.services.log_manager import log_stream_manager, get_relative_log_path

    with app.app_context():
        from app.extensions import db
        from app.models.task import Task
        from app.models.log import TaskLog
        from app.models.env_var import EnvVar

        task = Task.query.get(task_id)
        if not task:
            logger.error(f"任务 ID={task_id} 不存在")
            return

        # 检查是否允许多实例运行
        if not task.allow_multiple_instances:
            with _process_lock:
                if task_id in _running_processes:
                    process = _running_processes[task_id]
                    if process and process.poll() is None:
                        logger.warning(f"任务 [{task.name}] 已在运行中，跳过本次执行")
                        return

        # 检查前置任务依赖
        if task.depends_on:
            dep_task = Task.query.get(task.depends_on)
            if dep_task and dep_task.last_run_status != Task.RUN_SUCCESS:
                logger.warning(
                    f"任务 [{task.name}] 的前置任务 [{dep_task.name}] "
                    f"最近一次未成功执行，跳过本次运行"
                )
                # 记录跳过日志
                skip_log = TaskLog(
                    task_id=task.id,
                    started_at=datetime.utcnow(),
                    ended_at=datetime.utcnow(),
                    status=1,
                    duration=0,
                    content=f"跳过执行：前置任务 [{dep_task.name}] 最近一次未成功",
                )
                db.session.add(skip_log)
                db.session.commit()
                return

        # 加载系统配置
        from app.models.system_config import SystemConfig
        random_delay_max = SystemConfig.get_int("random_delay", 0)
        delay_extensions = SystemConfig.get("random_delay_extensions").split()
        global_timeout = SystemConfig.get_int("command_timeout", 300)
        max_log_size = SystemConfig.get_int("max_log_content_size", 102400)

        # 随机延迟执行
        if random_delay_max > 0:
            ext = task.command.rsplit(".", 1)[-1] if "." in task.command else ""
            should_delay = not delay_extensions or ext in delay_extensions
            if should_delay:
                import random
                delay = random.randint(1, random_delay_max)
                logger.info(f"任务 [{task.name}] 随机延迟 {delay}s")
                import time
                time.sleep(delay)

        # 加载已启用的环境变量
        enabled_envs = EnvVar.query.filter_by(enabled=True).all()
        env_vars = {e.name: e.value for e in enabled_envs}

        # 确定超时时间：任务级 > 全局默认
        timeout = task.timeout if task.timeout else global_timeout

        # 获取日志文件路径
        log_path = get_relative_log_path(task.id)
        absolute_log_path = os.path.join(app.config["LOG_DIR"], log_path)

        # 创建日志记录，初始状态为"执行中"
        log_entry = TaskLog(
            task_id=task.id,
            started_at=datetime.utcnow(),
            status=TaskLog.STATUS_RUNNING,
            log_path=log_path  # 保存日志文件路径
        )
        db.session.add(log_entry)

        # 标记为运行中
        task.status = Task.STATUS_RUNNING
        task.last_run_at = datetime.utcnow()
        task.log_path = log_path
        db.session.commit()

        # 初始化实时日志缓冲（线程安全）
        with _log_lock:
            _live_logs[task_id] = []
            _live_done[task_id] = False

        # 推送任务开始状态
        try:
            from app.services.websocket_service import emit_task_status
            emit_task_status(task_id, 'started', task_name=task.name)
        except Exception:
            pass

        def _on_output(line: str) -> None:
            # 写入日志文件
            log_stream_manager.write(absolute_log_path, line)
            # 同时写入实时日志缓冲
            with _log_lock:
                _live_logs.setdefault(task_id, []).append(line)
            # 通过 WebSocket 推送实时日志
            try:
                from app.services.websocket_service import emit_task_log
                emit_task_log(task_id, line)
            except Exception:
                pass  # WebSocket 推送失败不影响任务执行


        def _format_local_time(dt=None):
            """格式化为本地时间字符串"""
            import time as _time
            if dt is None:
                return _time.strftime("%Y-%m-%d %H:%M:%S")
            return dt.strftime("%Y-%m-%d %H:%M:%S")

        def _format_duration(seconds):
            """格式化耗时"""
            if seconds < 60:
                return f"{seconds:.0f} 秒"
            elif seconds < 3600:
                return f"{int(seconds // 60)} 分 {int(seconds % 60)} 秒"
            else:
                return f"{int(seconds // 3600)} 时 {int((seconds % 3600) // 60)} 分 {int(seconds % 60)} 秒"

        # 写入开始执行时间戳
        _on_output(f"## 开始执行...  {_format_local_time()}\n\n")

        # 执行任务前钩子
        if task.task_before:
            _on_output(f"[钩子] 执行 task_before...\n")
            _run_inline_script(task.task_before, app.config["SCRIPTS_DIR"], env_vars, _on_output)

        # 执行全局前置钩子 task_before.sh
        _run_hook_script("task_before.sh", app.config["SCRIPTS_DIR"], env_vars, _on_output)

        retries = 0
        success = False
        start_time = datetime.utcnow()

        while retries <= task.max_retries:
            try:
                result = run_command(
                    command=task.command,
                    scripts_dir=app.config["SCRIPTS_DIR"],
                    timeout=timeout,
                    env_vars=env_vars,
                    max_log_size=app.config["MAX_LOG_SIZE"],
                    on_output=_on_output,
                )

                with _process_lock:
                    if result.process is not None:
                        _running_processes[task_id] = result.process
                        task.pid = result.process.pid
                        db.session.commit()

                # 日志内容已经写入文件，不再存储到数据库
                log_entry.status = TaskLog.STATUS_SUCCESS if result.returncode == 0 else TaskLog.STATUS_FAILED

                if result.returncode == 0:
                    success = True
                    break
                else:
                    retries += 1
                    if retries <= task.max_retries:
                        logger.info(
                            f"任务 [{task.name}] 失败，{task.retry_interval}s 后重试"
                            f"（{retries}/{task.max_retries}）"
                        )
                        import time
                        time.sleep(task.retry_interval)

            except Exception as e:
                error_msg = f"执行异常: {str(e)}\n"
                _on_output(error_msg)
                log_entry.status = TaskLog.STATUS_FAILED
                retries += 1
                if retries <= task.max_retries:
                    import time
                    time.sleep(task.retry_interval)

        # 执行任务后钩子
        if task.task_after:
            _on_output(f"[钩子] 执行 task_after...\n")
            _run_inline_script(task.task_after, app.config["SCRIPTS_DIR"], env_vars, _on_output)

        # 执行全局后置钩子 task_after.sh / extra.sh
        _run_hook_script("task_after.sh", app.config["SCRIPTS_DIR"], env_vars, _on_output)
        _run_hook_script("extra.sh", app.config["SCRIPTS_DIR"], env_vars, _on_output)

        # 更新任务状态
        ended_at = datetime.utcnow()
        duration = (ended_at - start_time).total_seconds()

        # 写入执行结束时间戳
        _on_output(f"\n## 执行结束...  {_format_local_time()}  耗时 {_format_duration(duration)}\n")

        task.status = Task.STATUS_ENABLED
        task.last_run_status = Task.RUN_SUCCESS if success else Task.RUN_FAILED
        task.last_running_time = duration
        task.pid = None
        task.log_path = None

        log_entry.ended_at = ended_at
        log_entry.duration = duration

        with _process_lock:
            _running_processes.pop(task_id, None)

        # 关闭日志文件流
        log_stream_manager.close_stream(absolute_log_path)

        db.session.commit()
        logger.info(
            f"任务 [{task.name}] 执行完成，"
            f"状态={'成功' if success else '失败'}，"
            f"耗时 {duration:.1f}s"
        )

        # 推送任务完成状态
        try:
            from app.services.websocket_service import emit_task_status
            status = 'completed' if success else 'failed'
            emit_task_status(
                task_id,
                status,
                task_name=task.name,
                duration=duration,
                exit_code=log_entry.exit_code
            )
        except Exception:
            pass

        # 标记实时日志完成，清理缓冲（线程安全）
        with _log_lock:
            _live_done[task_id] = True


        def _cleanup_live_log():
            import time
            # 60 秒后清理日志内容（释放内存）
            time.sleep(60)
            with _log_lock:
                _live_logs.pop(task_id, None)
            # 5 分钟后清理完成标记（让 SSE 有足够时间检测到 done）
            time.sleep(240)
            with _log_lock:
                _live_done.pop(task_id, None)

        threading.Thread(target=_cleanup_live_log, daemon=True).start()

        # 任务失败时触发通知
        if not success and task.notify_on_failure:
            try:
                from app.services.notifier import send_task_failure_notification
                send_task_failure_notification(
                    task_name=task.name,
                    error_msg=f"查看日志: {log_path}",
                )
            except Exception as e:
                logger.error(f"发送失败通知异常: {e}")


def _run_hook_script(
    script_name: str, scripts_dir: str,
    env_vars: Optional[dict] = None,
    on_output: Optional[Callable] = None,
) -> None:
    """执行自定义钩子脚本（如 task_before.sh），文件不存在则静默跳过"""
    import subprocess
    from pathlib import Path
    from app.utils.command_validator import sanitize_env_vars

    full_path = Path(scripts_dir) / script_name
    if not full_path.is_file():
        return

    # 验证脚本在允许的目录内
    try:
        scripts_base = Path(scripts_dir).resolve()
        resolved_path = full_path.resolve()
        if not str(resolved_path).startswith(str(scripts_base)):
            logger.warning(f"钩子脚本路径非法: {script_name}")
            return
    except Exception as e:
        logger.warning(f"钩子脚本路径验证失败: {e}")
        return

    try:
        # 构建安全的环境变量
        env = {}
        for key in ['PATH', 'SYSTEMROOT', 'PATHEXT', 'TEMP', 'TMP', 'HOME', 'USER']:
            if key in os.environ:
                env[key] = os.environ[key]

        if env_vars:
            safe_env = sanitize_env_vars(env_vars)
            env.update(safe_env)

        # 使用参数列表执行，不使用 shell=True
        process = subprocess.Popen(
            ["bash", str(resolved_path)],  # 使用绝对路径
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env=env,
            cwd=str(scripts_base),
            encoding='utf-8',
            errors='replace',
        )
        for line in iter(process.stdout.readline, ''):
            if not line:
                break
            if on_output:
                try:
                    on_output(line)
                except Exception:
                    pass
        process.wait(timeout=60)
    except subprocess.TimeoutExpired:
        logger.warning(f"钩子脚本 {script_name} 执行超时")
        process.kill()
    except Exception as e:
        logger.warning(f"钩子脚本 {script_name} 执行失败: {e}")


def _run_inline_script(
    script_content: str, scripts_dir: str,
    env_vars: Optional[dict] = None,
    on_output: Optional[Callable] = None,
) -> None:
    """执行内联脚本（任务级钩子）"""
    import subprocess
    import tempfile
    from pathlib import Path
    from app.utils.command_validator import sanitize_env_vars

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

        # 构建安全的环境变量
        env = {}
        for key in ['PATH', 'SYSTEMROOT', 'PATHEXT', 'TEMP', 'TMP', 'HOME', 'USER']:
            if key in os.environ:
                env[key] = os.environ[key]

        if env_vars:
            safe_env = sanitize_env_vars(env_vars)
            env.update(safe_env)

        # 执行临时脚本
        process = subprocess.Popen(
            ["bash", tmp_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env=env,
            cwd=scripts_dir,
            encoding='utf-8',
            errors='replace',
        )
        for line in iter(process.stdout.readline, ''):
            if not line:
                break
            if on_output:
                try:
                    on_output(line)
                except Exception:
                    pass
        process.wait(timeout=60)

    except subprocess.TimeoutExpired:
        logger.warning("内联脚本执行超时")
        process.kill()
    except Exception as e:
        logger.warning(f"内联脚本执行失败: {e}")
    finally:
        # 清理临时文件
        try:
            if 'tmp_path' in locals():
                os.unlink(tmp_path)
        except Exception:
            pass


def _parse_cron(expression: str) -> CronTrigger:
    """解析 Cron 表达式为 APScheduler CronTrigger（支持 5 位和 6 位）"""
    from app.utils.cron_parser import CronParser

    # 使用新的 Cron 解析器
    trigger_kwargs = CronParser.to_apscheduler_trigger(expression)
    if not trigger_kwargs:
        # 解析失败，尝试原有逻辑（向后兼容）
        parts = expression.strip().split()

        if len(parts) == 5:
            return CronTrigger(
                minute=parts[0],
                hour=parts[1],
                day=parts[2],
                month=parts[3],
                day_of_week=parts[4],
            )
        elif len(parts) == 6:
            return CronTrigger(
                second=parts[0],
                minute=parts[1],
                hour=parts[2],
                day=parts[3],
                month=parts[4],
                day_of_week=parts[5],
            )
        else:
            raise ValueError(f"无效的 Cron 表达式: {expression}")

    return CronTrigger(**trigger_kwargs)

