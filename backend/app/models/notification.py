"""通知渠道模型"""

from datetime import datetime

from app.extensions import db


class NotifyChannel(db.Model):
    """通知渠道表"""
    __tablename__ = "notify_channels"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False)
    type = db.Column(db.String(32), nullable=False)  # webhook / email / telegram
    config = db.Column(db.Text, nullable=False, default="{}")
    enabled = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # config 结构示例:
    # webhook: {"url": "https://...", "method": "POST", "headers": {}}
    # email:   {"smtp_host": "", "smtp_port": 465, "username": "", "password": "", "to": ""}
    # telegram: {"bot_token": "", "chat_id": ""}

    def to_dict(self) -> dict:
        import json
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "config": json.loads(self.config) if self.config else {},
            "enabled": self.enabled,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
