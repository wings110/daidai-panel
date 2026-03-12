"""JWT Token 黑名单模型"""

from datetime import datetime
from app.extensions import db


class TokenBlocklist(db.Model):
    """JWT Token 黑名单表"""
    __tablename__ = "token_blocklist"

    id = db.Column(db.Integer, primary_key=True)
    jti = db.Column(db.String(36), unique=True, nullable=False, index=True)  # JWT ID
    token_type = db.Column(db.String(16), nullable=False)  # access 或 refresh
    user_id = db.Column(db.Integer, nullable=True)
    revoked_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)  # Token 过期时间

    def __repr__(self):
        return f"<TokenBlocklist {self.jti}>"
