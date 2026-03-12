"""开放 API 应用模型"""

import uuid
from datetime import datetime

from app.extensions import db
from app.utils.crypto import encrypt_secret, decrypt_secret


class OpenApp(db.Model):
    """开放 API 应用表"""
    __tablename__ = "open_apps"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False)
    client_id = db.Column(db.String(64), unique=True, nullable=False, index=True)
    client_secret_encrypted = db.Column(db.Text, nullable=False)  # 改为加密存储
    scopes = db.Column(db.Text, default="[]")
    token_expiry = db.Column(db.Integer, default=2592000)  # 30 天
    enabled = db.Column(db.Boolean, default=True)
    last_used_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关联调用日志
    call_logs = db.relationship("ApiCallLog", backref="app", lazy="dynamic", cascade="all, delete-orphan")

    @staticmethod
    def generate_client_id() -> str:
        return uuid.uuid4().hex

    @staticmethod
    def generate_client_secret() -> str:
        return uuid.uuid4().hex + uuid.uuid4().hex[:16]

    def set_secret(self, secret: str) -> None:
        """设置加密的 Secret"""
        self.client_secret_encrypted = encrypt_secret(secret)

    def get_secret(self) -> str:
        """获取解密的 Secret"""
        return decrypt_secret(self.client_secret_encrypted)

    def check_secret(self, secret: str) -> bool:
        """验证 Secret"""
        try:
            return self.get_secret() == secret
        except Exception:
            return False

    def to_dict(self, include_secret: bool = False) -> dict:
        import json
        d = {
            "id": self.id,
            "name": self.name,
            "client_id": self.client_id,
            "scopes": json.loads(self.scopes) if self.scopes else [],
            "token_expiry": self.token_expiry,
            "enabled": self.enabled,
            "last_used_at": self.last_used_at.isoformat() if self.last_used_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
        return d


class ApiCallLog(db.Model):
    """API 调用日志表"""
    __tablename__ = "api_call_logs"

    id = db.Column(db.Integer, primary_key=True)
    app_id = db.Column(db.Integer, db.ForeignKey("open_apps.id"), nullable=False, index=True)
    method = db.Column(db.String(8), nullable=False)
    path = db.Column(db.String(256), nullable=False)
    status_code = db.Column(db.Integer)
    ip = db.Column(db.String(64))
    called_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "app_id": self.app_id,
            "app_name": self.app.name if self.app else None,
            "method": self.method,
            "path": self.path,
            "status_code": self.status_code,
            "ip": self.ip,
            "called_at": self.called_at.isoformat() if self.called_at else None,
        }
