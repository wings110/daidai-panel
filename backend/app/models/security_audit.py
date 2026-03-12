"""安全审计日志模型"""

from datetime import datetime
from app.extensions import db


class SecurityAudit(db.Model):
    """安全审计日志表"""
    __tablename__ = "security_audits"

    id = db.Column(db.Integer, primary_key=True)
    event_type = db.Column(db.String(64), index=True, nullable=False)  # SECRET_ACCESS, SECRET_ACCESS_FAILED, etc.
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    resource_type = db.Column(db.String(64), nullable=True)  # open_app, task, script, etc.
    resource_id = db.Column(db.Integer, nullable=True)
    description = db.Column(db.String(512), nullable=True)
    ip_address = db.Column(db.String(45), index=True, nullable=True)
    user_agent = db.Column(db.String(512), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    # 关联用户
    user = db.relationship("User", backref="security_audits")

    def to_dict(self) -> dict:
        """序列化为字典"""
        return {
            "id": self.id,
            "event_type": self.event_type,
            "user_id": self.user_id,
            "username": self.user.username if self.user else None,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "description": self.description,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
