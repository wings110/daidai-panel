"""呆呆面板 - 配置文件"""

import os
import secrets
from datetime import timedelta

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _get_or_generate_secret(key_name: str, key_file: str) -> str:
    """获取或生成密钥

    Args:
        key_name: 环境变量名
        key_file: 密钥文件路径

    Returns:
        密钥字符串
    """
    # 优先从环境变量读取
    secret = os.environ.get(key_name)
    if secret:
        return secret

    # 从文件读取
    if os.path.exists(key_file):
        with open(key_file, 'r') as f:
            return f.read().strip()

    # 生成新密钥并保存
    secret = secrets.token_urlsafe(32)
    os.makedirs(os.path.dirname(key_file), exist_ok=True)
    with open(key_file, 'w') as f:
        f.write(secret)
    return secret


class Config:
    """基础配置"""

    # 数据目录
    DATA_DIR = os.environ.get("DAIDAI_DATA_DIR", os.path.join(BASE_DIR, "data"))
    SCRIPTS_DIR = os.environ.get("DAIDAI_SCRIPTS_DIR", os.path.join(DATA_DIR, "scripts"))
    LOG_DIR = os.environ.get("DAIDAI_LOG_DIR", os.path.join(DATA_DIR, "logs"))

    # 数据库
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        f"sqlite:///{os.path.join(DATA_DIR, 'daidai.db')}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # JWT - 自动生成并持久化
    JWT_SECRET_KEY = _get_or_generate_secret(
        "JWT_SECRET_KEY",
        os.path.join(DATA_DIR, ".jwt_secret")
    )
    # 延长 Token 有效期，避免用户长时间不操作被退出
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(days=20)  # 参考青龙面板，20天有效期
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=60)  # 刷新令牌 60 天
    JWT_TOKEN_LOCATION = ["headers"]

    # Flask Secret Key - 自动生成并持久化
    SECRET_KEY = _get_or_generate_secret(
        "SECRET_KEY",
        os.path.join(DATA_DIR, ".flask_secret")
    )

    # CORS
    CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "http://localhost:5173").split(",")

    # 限流
    RATELIMIT_DEFAULT = "200/minute"
    RATELIMIT_STORAGE_URI = "memory://"

    # 默认管理员
    DEFAULT_ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
    DEFAULT_ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")

    # 脚本执行
    SCRIPT_TIMEOUT = int(os.environ.get("SCRIPT_TIMEOUT", "300"))
    MAX_LOG_SIZE = int(os.environ.get("MAX_LOG_SIZE", str(10 * 1024 * 1024)))  # 10MB


class DevelopmentConfig(Config):
    """开发环境配置"""
    DEBUG = True


class ProductionConfig(Config):
    """生产环境配置"""
    DEBUG = False
    RATELIMIT_DEFAULT = "100/minute"

