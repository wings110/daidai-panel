"""登录安全服务"""

import logging
from datetime import datetime, timedelta
from flask import request

from app.extensions import db
from app.models.login_log import LoginLog
from app.models.ip_whitelist import IPWhitelist

logger = logging.getLogger(__name__)


def get_client_ip() -> str:
    """获取客户端 IP 地址"""
    if request.headers.get('X-Forwarded-For'):
        return request.headers.get('X-Forwarded-For').split(',')[0].strip()
    elif request.headers.get('X-Real-IP'):
        return request.headers.get('X-Real-IP')
    return request.remote_addr or "unknown"


def get_user_agent() -> str:
    """获取用户代理"""
    return request.headers.get('User-Agent', '')[:512]


def log_login_attempt(username: str, user_id: int = None, success: bool = True,
                      failure_reason: str = "", login_type: str = "password"):
    """记录登录尝试"""
    try:
        ip_address = get_client_ip()
        user_agent = get_user_agent()
        location = get_ip_location(ip_address)

        log = LoginLog(
            user_id=user_id,
            username=username,
            ip_address=ip_address,
            user_agent=user_agent,
            login_type=login_type,
            status=0 if success else 1,
            failure_reason=failure_reason,
            location=location,
        )
        db.session.add(log)
        db.session.commit()
    except Exception as e:
        logger.error(f"记录登录日志失败: {e}")


def check_ip_whitelist() -> tuple[bool, str]:
    """检查 IP 白名单"""
    ip_address = get_client_ip()
    if not IPWhitelist.is_allowed(ip_address):
        return False, f"IP {ip_address} 不在白名单中"
    return True, ""


def detect_suspicious_login(username: str) -> tuple[bool, str]:
    """检测可疑登录"""
    ip_address = get_client_ip()

    # 检查短时间内失败次数
    time_threshold = datetime.utcnow() - timedelta(minutes=15)
    failed_attempts = LoginLog.query.filter(
        LoginLog.username == username,
        LoginLog.status == 1,
        LoginLog.created_at >= time_threshold
    ).count()

    if failed_attempts >= 5:
        return True, f"15分钟内失败登录次数过多（{failed_attempts}次）"

    # 检查是否来自新 IP
    recent_success = LoginLog.query.filter(
        LoginLog.username == username,
        LoginLog.status == 0,
        LoginLog.created_at >= datetime.utcnow() - timedelta(days=30)
    ).order_by(LoginLog.created_at.desc()).limit(10).all()

    known_ips = {log.ip_address for log in recent_success}
    if known_ips and ip_address not in known_ips:
        return True, f"来自新 IP 地址: {ip_address}"

    return False, ""


def get_ip_location(ip_address: str) -> str:
    """获取 IP 地理位置（简单实现）"""
    # 这里可以集成第三方 IP 地理位置服务
    # 如：ip-api.com, ipinfo.io 等
    if ip_address.startswith("127.") or ip_address == "localhost":
        return "本地"
    elif ip_address.startswith("192.168.") or ip_address.startswith("10."):
        return "内网"
    return "未知"


def check_login_rate_limit(username: str) -> tuple[bool, str]:
    """检查登录频率限制"""
    time_threshold = datetime.utcnow() - timedelta(minutes=5)
    attempts = LoginLog.query.filter(
        LoginLog.username == username,
        LoginLog.created_at >= time_threshold
    ).count()

    if attempts >= 10:
        return False, "登录尝试过于频繁，请5分钟后再试"
    return True, ""


def get_recent_login_logs(user_id: int, limit: int = 10):
    """获取最近的登录日志"""
    return LoginLog.query.filter_by(user_id=user_id).order_by(
        LoginLog.created_at.desc()
    ).limit(limit).all()


def clean_old_login_logs(days: int = 90):
    """清理旧的登录日志"""
    cutoff_date = datetime.utcnow() - timedelta(days=days)
    deleted = LoginLog.query.filter(LoginLog.created_at < cutoff_date).delete()
    db.session.commit()
    return deleted
