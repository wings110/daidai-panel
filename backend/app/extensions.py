"""呆呆面板 - Flask 扩展初始化"""

from datetime import datetime, timedelta
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_jwt_extended import JWTManager
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

db = SQLAlchemy()
migrate = Migrate()
jwt = JWTManager()
cors = CORS()
limiter = Limiter(key_func=get_remote_address)


# ---------- Token 黑名单（持久化到数据库）----------

def add_token_to_blocklist(jti: str, expires_in: int = 3600, token_type: str = "access", user_id: int = None) -> None:
    """将 Token JTI 加入黑名单（持久化到数据库）

    Args:
        jti: Token 的唯一标识
        expires_in: 过期时间（秒）
        token_type: Token 类型（access 或 refresh）
        user_id: 用户 ID
    """
    from app.models.token_blocklist import TokenBlocklist

    expires_at = datetime.utcnow() + timedelta(seconds=expires_in)

    # 检查是否已存在
    existing = TokenBlocklist.query.filter_by(jti=jti).first()
    if existing:
        return  # 已在黑名单中

    blocklist_entry = TokenBlocklist(
        jti=jti,
        token_type=token_type,
        user_id=user_id,
        expires_at=expires_at
    )
    db.session.add(blocklist_entry)
    db.session.commit()


def is_token_blocked(jti: str) -> bool:
    """检查 Token 是否在黑名单中（从数据库查询）"""
    from app.models.token_blocklist import TokenBlocklist

    blocked = TokenBlocklist.query.filter_by(jti=jti).first()
    return blocked is not None


def cleanup_expired_tokens() -> int:
    """清理已过期的黑名单 Token（定期任务）

    Returns:
        int: 清理的记录数
    """
    from app.models.token_blocklist import TokenBlocklist

    now = datetime.utcnow()
    expired = TokenBlocklist.query.filter(TokenBlocklist.expires_at < now).all()
    count = len(expired)

    for token in expired:
        db.session.delete(token)

    db.session.commit()
    return count


@jwt.token_in_blocklist_loader
def check_if_token_revoked(_jwt_header, jwt_payload: dict) -> bool:
    """JWT 扩展回调：检查 Token 是否被撤销"""
    return is_token_blocked(jwt_payload["jti"])

