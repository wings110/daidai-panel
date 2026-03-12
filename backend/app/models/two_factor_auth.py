"""2FA（双因素认证）模型"""

from datetime import datetime

from app.extensions import db


class TwoFactorAuth(db.Model):
    """双因素认证表"""
    __tablename__ = "two_factor_auth"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), unique=True, nullable=False, index=True)
    secret = db.Column(db.String(32), nullable=False)  # TOTP secret
    enabled = db.Column(db.Boolean, default=False, index=True)
    backup_codes = db.Column(db.Text, default="")  # JSON 格式的备用码列表
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "enabled": self.enabled,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    @staticmethod
    def generate_secret() -> str:
        """生成 TOTP secret"""
        import pyotp
        return pyotp.random_base32()

    def get_totp_uri(self, username: str, issuer: str = "DaiDai Panel") -> str:
        """获取 TOTP URI（用于生成二维码）"""
        import pyotp
        return pyotp.totp.TOTP(self.secret).provisioning_uri(
            name=username,
            issuer_name=issuer
        )

    def verify_token(self, token: str) -> bool:
        """验证 TOTP token"""
        import pyotp
        totp = pyotp.TOTP(self.secret)
        return totp.verify(token, valid_window=1)

    def generate_backup_codes(self, count: int = 10) -> list:
        """生成备用码"""
        import secrets
        import json
        codes = [secrets.token_hex(4).upper() for _ in range(count)]
        self.backup_codes = json.dumps(codes)
        db.session.commit()
        return codes

    def verify_backup_code(self, code: str) -> bool:
        """验证并使用备用码"""
        import json
        if not self.backup_codes:
            return False

        codes = json.loads(self.backup_codes)
        code = code.upper()
        if code in codes:
            codes.remove(code)
            self.backup_codes = json.dumps(codes)
            db.session.commit()
            return True
        return False
