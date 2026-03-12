"""资源监控服务 - 定期检查 CPU/内存/磁盘并触发告警通知"""

import logging

import psutil

from app.models.system_config import SystemConfig

logger = logging.getLogger(__name__)


def check_resource_alerts() -> None:
    """检查系统资源是否超过告警阈值，超限则发送通知"""
    if not SystemConfig.get_bool("notify_on_resource_warn"):
        return

    cpu_warn = SystemConfig.get_int("cpu_warn", 80)
    mem_warn = SystemConfig.get_int("memory_warn", 80)
    disk_warn = SystemConfig.get_int("disk_warn", 90)

    alerts: list[str] = []

    # CPU
    cpu_percent = psutil.cpu_percent(interval=1)
    if cpu_percent >= cpu_warn:
        alerts.append(f"CPU 使用率 {cpu_percent:.1f}%（阈值 {cpu_warn}%）")

    # 内存
    mem = psutil.virtual_memory()
    if mem.percent >= mem_warn:
        alerts.append(f"内存使用率 {mem.percent:.1f}%（阈值 {mem_warn}%）")

    # 磁盘
    disk = psutil.disk_usage("/")
    if disk.percent >= disk_warn:
        alerts.append(f"磁盘使用率 {disk.percent:.1f}%（阈值 {disk_warn}%）")

    if not alerts:
        return

    # 发送告警通知
    try:
        from app.services.notifier import send_task_failure_notification
        from app.models.notification import NotifyChannel

        channels = NotifyChannel.query.filter_by(enabled=True).all()
        if not channels:
            logger.warning("资源告警触发但无可用通知渠道")
            return

        title = "⚠ 系统资源告警"
        content = "以下资源超过告警阈值：\n" + "\n".join(f"• {a}" for a in alerts)

        from app.services.notifier import send_notification
        for ch in channels:
            ok, msg = send_notification(ch, title, content)
            if not ok:
                logger.error(f"资源告警通知发送失败 [{ch.name}]: {msg}")
            else:
                logger.info(f"资源告警通知已发送 [{ch.name}]")

    except Exception as e:
        logger.error(f"资源告警通知异常: {e}")
