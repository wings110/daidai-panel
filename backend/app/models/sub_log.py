"""订阅拉取日志模型"""

from datetime import datetime

from app.extensions import db


class SubLog(db.Model):
    """订阅拉取日志表"""
    __tablename__ = "sub_logs"

    id = db.Column(db.Integer, primary_key=True)
    sub_id = db.Column(db.Integer, db.ForeignKey("subscriptions.id"), nullable=False, index=True)
    sub_name = db.Column(db.String(128), default="")
    status = db.Column(db.Integer, default=0)  # 0=成功, 1=失败
    message = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    subscription = db.relationship("Subscription", backref=db.backref("logs", lazy="dynamic"))

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "sub_id": self.sub_id,
            "sub_name": self.sub_name,
            "status": self.status,
            "message": self.message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
