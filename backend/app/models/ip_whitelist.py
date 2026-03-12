"""IP 白名单模型"""

from datetime import datetime

from app.extensions import db


class IPWhitelist(db.Model):
    """IP 白名单表"""
    __tablename__ = "ip_whitelist"

    id = db.Column(db.Integer, primary_key=True)
    ip_address = db.Column(db.String(64), unique=True, nullable=False, index=True)
    description = db.Column(db.String(256), default="")
    enabled = db.Column(db.Boolean, default=True, index=True)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "ip_address": self.ip_address,
            "description": self.description,
            "enabled": self.enabled,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    @staticmethod
    def is_allowed(ip_address: str) -> bool:
        """检查 IP 是否在白名单中"""
        # 如果白名单为空，允许所有 IP
        count = IPWhitelist.query.filter_by(enabled=True).count()
        if count == 0:
            return True

        # 检查精确匹配
        if IPWhitelist.query.filter_by(ip_address=ip_address, enabled=True).first():
            return True

        # 检查 CIDR 匹配（简单实现，支持 /24 和 /16）
        parts = ip_address.split(".")
        if len(parts) == 4:
            # 检查 /24 网段
            subnet_24 = f"{parts[0]}.{parts[1]}.{parts[2]}.0/24"
            if IPWhitelist.query.filter_by(ip_address=subnet_24, enabled=True).first():
                return True

            # 检查 /16 网段
            subnet_16 = f"{parts[0]}.{parts[1]}.0.0/16"
            if IPWhitelist.query.filter_by(ip_address=subnet_16, enabled=True).first():
                return True

        return False
