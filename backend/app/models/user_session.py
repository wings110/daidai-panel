"""会话管理模型"""

from datetime import datetime, timedelta

from app.extensions import db


class UserSession(db.Model):
    """用户会话表"""
    __tablename__ = "user_sessions"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    session_token = db.Column(db.String(256), unique=True, nullable=False, index=True)
    ip_address = db.Column(db.String(64), nullable=False)
    user_agent = db.Column(db.String(512), default="")
    last_activity = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    expires_at = db.Column(db.DateTime, nullable=False, index=True)
    is_active = db.Column(db.Boolean, default=True, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "last_activity": self.last_activity.isoformat() if self.last_activity else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    @staticmethod
    def create_session(user_id: int, ip_address: str, user_agent: str, expires_in_days: int = 30):
        """创建新会话"""
        import secrets
        session_token = secrets.token_urlsafe(32)
        expires_at = datetime.utcnow() + timedelta(days=expires_in_days)

        session = UserSession(
            user_id=user_id,
            session_token=session_token,
            ip_address=ip_address,
            user_agent=user_agent,
            expires_at=expires_at,
        )
        db.session.add(session)
        db.session.commit()
        return session

    @staticmethod
    def get_active_session(session_token: str):
        """获取活跃会话"""
        return UserSession.query.filter_by(
            session_token=session_token,
            is_active=True
        ).filter(
            UserSession.expires_at > datetime.utcnow()
        ).first()

    def update_activity(self):
        """更新最后活动时间"""
        self.last_activity = datetime.utcnow()
        db.session.commit()

    def revoke(self):
        """撤销会话"""
        self.is_active = False
        db.session.commit()
