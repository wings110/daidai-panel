"""SSE 临时 Token 管理"""

import secrets
from datetime import datetime, timedelta
from typing import Optional


class SSETokenManager:
    """SSE 临时 Token 管理器（内存存储，短期有效）"""

    def __init__(self):
        # {temp_token: (user_id, expires_at)}
        self._tokens: dict[str, tuple[int, datetime]] = {}

    def generate_token(self, user_id: int, expires_in: int = 60) -> str:
        """生成临时 Token

        Args:
            user_id: 用户 ID
            expires_in: 有效期（秒），默认 60 秒

        Returns:
            str: 临时 Token
        """
        # 清理过期 Token
        self._cleanup_expired()

        # 生成新 Token
        temp_token = secrets.token_urlsafe(32)
        expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
        self._tokens[temp_token] = (user_id, expires_at)

        return temp_token

    def verify_token(self, temp_token: str) -> Optional[int]:
        """验证临时 Token

        Args:
            temp_token: 临时 Token

        Returns:
            Optional[int]: 用户 ID，如果 Token 无效或过期则返回 None
        """
        if temp_token not in self._tokens:
            return None

        user_id, expires_at = self._tokens[temp_token]

        # 检查是否过期
        if datetime.utcnow() > expires_at:
            del self._tokens[temp_token]
            return None

        return user_id

    def revoke_token(self, temp_token: str) -> None:
        """撤销临时 Token"""
        self._tokens.pop(temp_token, None)

    def _cleanup_expired(self) -> None:
        """清理过期 Token"""
        now = datetime.utcnow()
        expired_tokens = [
            token for token, (_, expires_at) in self._tokens.items()
            if now > expires_at
        ]
        for token in expired_tokens:
            del self._tokens[token]


# 全局单例
sse_token_manager = SSETokenManager()
