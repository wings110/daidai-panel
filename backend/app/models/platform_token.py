"""平台 Token 管理模型（参考青龙面板）"""

import uuid
from datetime import datetime, timedelta
from typing import Optional

from app.extensions import db
from app.utils.crypto import encrypt_data, decrypt_data


class Platform(db.Model):
    """平台表 - 管理不同的应用平台"""
    __tablename__ = "platforms"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False, unique=True)  # 平台名称（如：移动端、Web端、第三方集成）
    description = db.Column(db.Text, default="")
    max_tokens = db.Column(db.Integer, default=5)  # 每个平台最多允许的活跃 Token 数
    enabled = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关联 Token
    tokens = db.relationship("PlatformToken", backref="platform", lazy="dynamic", cascade="all, delete-orphan")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "max_tokens": self.max_tokens,
            "enabled": self.enabled,
            "active_tokens_count": self.tokens.filter_by(enabled=True).count(),
            "total_tokens_count": self.tokens.count(),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class PlatformToken(db.Model):
    """平台 Token 表 - 每个平台可以有多个 Token"""
    __tablename__ = "platform_tokens"

    id = db.Column(db.Integer, primary_key=True)
    platform_id = db.Column(db.Integer, db.ForeignKey("platforms.id"), nullable=False, index=True)
    name = db.Column(db.String(128), nullable=False)  # Token 名称（如：生产环境、测试环境）
    token = db.Column(db.String(128), unique=True, nullable=False, index=True)  # Token 值
    token_encrypted = db.Column(db.Text, nullable=False)  # 加密存储的 Token
    scopes = db.Column(db.Text, default="[]")  # 权限范围 JSON 数组
    expires_at = db.Column(db.DateTime, nullable=True)  # 过期时间（None 表示永不过期）
    enabled = db.Column(db.Boolean, default=True)
    last_used_at = db.Column(db.DateTime, nullable=True)
    last_used_ip = db.Column(db.String(64), nullable=True)
    remarks = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关联调用日志
    call_logs = db.relationship("PlatformTokenLog", backref="token", lazy="dynamic", cascade="all, delete-orphan")

    @staticmethod
    def generate_token() -> str:
        """生成 Token（格式：daidai_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx）"""
        return f"daidai_{uuid.uuid4().hex}"

    def set_token(self, token: str) -> None:
        """设置 Token（明文存储用于查询，加密存储用于验证）"""
        self.token = token
        self.token_encrypted = encrypt_data(token)

    def verify_token(self, token: str) -> bool:
        """验证 Token"""
        try:
            stored_token = decrypt_data(self.token_encrypted)
            return stored_token == token
        except Exception:
            return False

    def is_expired(self) -> bool:
        """检查是否过期"""
        if not self.expires_at:
            return False
        return datetime.utcnow() > self.expires_at

    def is_valid(self) -> bool:
        """检查 Token 是否有效（启用且未过期）"""
        return self.enabled and not self.is_expired()

    def to_dict(self, include_token: bool = False) -> dict:
        import json
        d = {
            "id": self.id,
            "platform_id": self.platform_id,
            "platform_name": self.platform.name if self.platform else None,
            "name": self.name,
            "scopes": json.loads(self.scopes) if self.scopes else [],
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "is_expired": self.is_expired(),
            "enabled": self.enabled,
            "last_used_at": self.last_used_at.isoformat() if self.last_used_at else None,
            "last_used_ip": self.last_used_ip,
            "remarks": self.remarks,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
        if include_token:
            d["token"] = self.token
        return d


class PlatformTokenLog(db.Model):
    """平台 Token 调用日志表"""
    __tablename__ = "platform_token_logs"

    id = db.Column(db.Integer, primary_key=True)
    token_id = db.Column(db.Integer, db.ForeignKey("platform_tokens.id"), nullable=False, index=True)
    method = db.Column(db.String(8), nullable=False)
    path = db.Column(db.String(256), nullable=False)
    status_code = db.Column(db.Integer)
    ip = db.Column(db.String(64))
    user_agent = db.Column(db.String(512))
    called_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "token_id": self.token_id,
            "token_name": self.token.name if self.token else None,
            "platform_name": self.token.platform.name if self.token and self.token.platform else None,
            "method": self.method,
            "path": self.path,
            "status_code": self.status_code,
            "ip": self.ip,
            "user_agent": self.user_agent,
            "called_at": self.called_at.isoformat() if self.called_at else None,
        }
