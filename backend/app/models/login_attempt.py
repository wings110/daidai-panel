"""登录尝试记录模型 - 用于持久化登录失败锁定"""

from datetime import datetime
from app.extensions import db


class LoginAttempt(db.Model):
    """登录尝试记录表"""
    __tablename__ = "login_attempts"

    id = db.Column(db.Integer, primary_key=True)
    ip_address = db.Column(db.String(45), index=True, nullable=False)  # 支持 IPv6
    username = db.Column(db.String(128), index=True, nullable=True)
    success = db.Column(db.Boolean, default=False, nullable=False)
    failure_reason = db.Column(db.String(256), nullable=True)
    user_agent = db.Column(db.String(512), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    def to_dict(self) -> dict:
        """序列化为字典"""
        return {
            "id": self.id,
            "ip_address": self.ip_address,
            "username": self.username,
            "success": self.success,
            "failure_reason": self.failure_reason,
            "user_agent": self.user_agent,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
