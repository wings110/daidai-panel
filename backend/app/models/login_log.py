"""登录日志模型"""

from datetime import datetime

from app.extensions import db


class LoginLog(db.Model):
    """登录日志表"""
    __tablename__ = "login_logs"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    username = db.Column(db.String(64), nullable=False, index=True)
    ip_address = db.Column(db.String(64), nullable=False, index=True)
    user_agent = db.Column(db.String(512), default="")
    login_type = db.Column(db.String(32), default="password")  # password, 2fa, api
    status = db.Column(db.Integer, default=0)  # 0=成功, 1=失败
    failure_reason = db.Column(db.String(256), default="")
    location = db.Column(db.String(128), default="")  # IP 地理位置
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "username": self.username,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "login_type": self.login_type,
            "status": self.status,
            "failure_reason": self.failure_reason,
            "location": self.location,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
