"""用户模型"""

from datetime import datetime

from werkzeug.security import generate_password_hash, check_password_hash

from app.extensions import db


class User(db.Model):
    """用户表"""
    __tablename__ = "users"

    ROLE_ADMIN = "admin"
    ROLE_OPERATOR = "operator"
    ROLE_VIEWER = "viewer"
    VALID_ROLES = {ROLE_ADMIN, ROLE_OPERATOR, ROLE_VIEWER}

    # 角色权限层级：admin > operator > viewer
    ROLE_LEVEL = {ROLE_ADMIN: 3, ROLE_OPERATOR: 2, ROLE_VIEWER: 1}

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(16), nullable=False, default=ROLE_ADMIN)
    enabled = db.Column(db.Boolean, default=True)
    last_login_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def set_password(self, password: str) -> None:
        """设置密码（哈希存储）"""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        """校验密码"""
        return check_password_hash(self.password_hash, password)

    @property
    def is_admin(self) -> bool:
        return self.role == self.ROLE_ADMIN

    def has_permission(self, required_role: str) -> bool:
        """检查用户是否具有所需角色权限"""
        return self.ROLE_LEVEL.get(self.role, 0) >= self.ROLE_LEVEL.get(required_role, 0)

    def to_dict(self) -> dict:
        """序列化为字典（不包含密码）"""
        return {
            "id": self.id,
            "username": self.username,
            "role": self.role,
            "enabled": self.enabled,
            "last_login_at": self.last_login_at.isoformat() if self.last_login_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
