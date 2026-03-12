"""脚本版本历史模型"""

from datetime import datetime

from app.extensions import db


class ScriptVersion(db.Model):
    """脚本版本历史表"""
    __tablename__ = "script_versions"

    id = db.Column(db.Integer, primary_key=True)
    script_path = db.Column(db.String(512), nullable=False, index=True)
    content = db.Column(db.Text, nullable=False)
    version = db.Column(db.Integer, nullable=False, default=1)
    message = db.Column(db.String(256), default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "script_path": self.script_path,
            "version": self.version,
            "message": self.message,
            "content_length": len(self.content) if self.content else 0,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
