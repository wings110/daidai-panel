"""系统维护任务 - 自动清理日志等"""

import logging
from datetime import datetime
from flask import Flask

logger = logging.getLogger(__name__)

# 全局调度器实例（避免重复创建）
_maintenance_scheduler = None


def init_maintenance_tasks(app: Flask) -> None:
    """初始化系统维护任务"""
    global _maintenance_scheduler

    # 如果调度器已经启动，不重复创建
    if _maintenance_scheduler is not None:
        logger.info("系统维护任务调度器已存在，跳过初始化")
        return

    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.cron import CronTrigger

    _maintenance_scheduler = BackgroundScheduler()

    # 每天凌晨 3 点清理旧日志
    _maintenance_scheduler.add_job(
        func=_clean_old_logs_task,
        trigger=CronTrigger(hour=3, minute=0),
        id='clean_old_logs',
        args=[app],
        replace_existing=True,
    )

    # 每天凌晨 4 点清理旧的登录日志
    _maintenance_scheduler.add_job(
        func=_clean_old_login_logs_task,
        trigger=CronTrigger(hour=4, minute=0),
        id='clean_old_login_logs',
        args=[app],
        replace_existing=True,
    )

    # 每天凌晨 5 点清理过期的平台 Token
    _maintenance_scheduler.add_job(
        func=_clean_expired_platform_tokens_task,
        trigger=CronTrigger(hour=5, minute=0),
        id='clean_expired_platform_tokens',
        args=[app],
        replace_existing=True,
    )

    _maintenance_scheduler.start()
    logger.info("系统维护任务已启动")


def _clean_old_logs_task(app: Flask) -> None:
    """清理旧日志任务（日志文件 + 数据库记录）"""
    with app.app_context():
        from app.extensions import db
        from app.services.log_manager import clean_old_logs
        from app.models.system_config import SystemConfig
        from app.models.log import TaskLog
        from datetime import timedelta

        log_dir = app.config["LOG_DIR"]
        retention_days = SystemConfig.get_int("log_retention_days", 3)

        try:
            # 清理日志文件
            deleted_files = clean_old_logs(log_dir, retention_days)
            # 清理数据库中的旧日志记录
            cutoff_date = datetime.utcnow() - timedelta(days=retention_days)
            deleted_records = TaskLog.query.filter(
                TaskLog.started_at < cutoff_date
            ).delete()
            db.session.commit()
            logger.info(f"自动清理日志完成，删除了 {deleted_files} 个文件、{deleted_records} 条数据库记录")
        except Exception as e:
            db.session.rollback()
            logger.error(f"自动清理日志失败: {e}")


def _clean_old_login_logs_task(app: Flask) -> None:
    """清理旧登录日志任务"""
    with app.app_context():
        from app.extensions import db
        from app.models.login_log import LoginLog
        from app.models.system_config import SystemConfig
        from datetime import timedelta

        retention_days = SystemConfig.get_int("login_log_retention_days", 90)
        cutoff_date = datetime.utcnow() - timedelta(days=retention_days)

        try:
            deleted_count = LoginLog.query.filter(
                LoginLog.created_at < cutoff_date
            ).delete()
            db.session.commit()
            logger.info(f"自动清理登录日志完成，删除了 {deleted_count} 条记录")
        except Exception as e:
            db.session.rollback()
            logger.error(f"自动清理登录日志失败: {e}")


def _clean_expired_platform_tokens_task(app: Flask) -> None:
    """清理过期的平台 Token 任务"""
    with app.app_context():
        from app.api.platform_tokens import cleanup_expired_tokens

        try:
            deleted_count = cleanup_expired_tokens()
            if deleted_count > 0:
                logger.info(f"自动清理过期平台 Token 完成，删除了 {deleted_count} 个 Token")
        except Exception as e:
            logger.error(f"自动清理过期平台 Token 失败: {e}")

