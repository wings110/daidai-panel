"""呆呆面板 - Application Factory"""

import os

from flask import Flask

from app.config import ProductionConfig
from app.extensions import db, migrate, jwt, cors, limiter


def create_app(config_class: type = ProductionConfig) -> Flask:
    """创建并配置 Flask 应用实例

    默认使用生产环境配置
    """
    app = Flask(__name__)
    app.config.from_object(config_class)

    # 初始化扩展
    _init_extensions(app)

    # 初始化 WebSocket
    _init_websocket(app)

    # 注册蓝图
    _register_blueprints(app)

    # 注册全局钩子
    _register_hooks(app)

    # 注册全局错误处理器
    _register_error_handlers(app)

    # 确保必要目录存在
    _ensure_directories(app)

    # 配置文件日志
    _setup_logging(app)

    # 初始化 Swagger 文档
    _init_swagger(app)

    # 初始化系统维护任务
    _init_maintenance_tasks(app)

    # 创建数据库表 & 初始化默认配置
    with app.app_context():
        # 导入所有模型以确保 SQLAlchemy 知道它们
        from app.models.user import User
        from app.models.task import Task
        from app.models.env_var import EnvVar
        from app.models.open_app import OpenApp, ApiCallLog
        from app.models.subscription import Subscription
        from app.models.system_config import SystemConfig
        from app.models.two_factor_auth import TwoFactorAuth
        from app.models.notification import NotifyChannel
        from app.models.script_version import ScriptVersion
        from app.models.sub_log import SubLog
        from app.models.log import TaskLog
        from app.models.login_log import LoginLog
        from app.models.user_session import UserSession
        from app.models.ip_whitelist import IPWhitelist
        # 导入新增的安全相关模型
        from app.models.token_blocklist import TokenBlocklist
        from app.models.security_audit import SecurityAudit
        from app.models.login_attempt import LoginAttempt
        # 导入多平台 Token 管理模型
        from app.models.platform_token import Platform, PlatformToken, PlatformTokenLog

        db.create_all()
        SystemConfig.init_defaults()

    return app


def _init_extensions(app: Flask) -> None:
    """初始化所有 Flask 扩展"""
    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    cors.init_app(app)
    limiter.init_app(app)


def _init_websocket(app: Flask) -> None:
    """初始化 WebSocket 服务"""
    from app.services.websocket_service import init_socketio
    socketio = init_socketio(app)
    # 将 socketio 实例存储到 app 中，供 wsgi.py 使用
    app.socketio = socketio



def _register_blueprints(app: Flask) -> None:
    """注册所有 API 蓝图（带版本控制）"""
    from app.api.auth import auth_bp
    from app.api.tasks import tasks_bp
    from app.api.logs import logs_bp
    from app.api.scripts import scripts_bp
    from app.api.envs import envs_bp
    from app.api.open_api import open_api_bp
    from app.api.system import system_bp
    from app.api.subscriptions import subs_bp
    from app.api.notifications import notify_bp
    from app.api.deps import deps_bp
    from app.api.users import users_bp
    from app.api.config import config_bp
    from app.api.security import security_bp
    from app.api.api_meta import api_meta_bp
    from app.api.ssh_keys import ssh_keys_bp
    from app.api.platform_tokens import platform_token_bp

    # API v1 版本（推荐使用）
    app.register_blueprint(auth_bp, url_prefix="/api/v1/auth")
    app.register_blueprint(tasks_bp, url_prefix="/api/v1/tasks")
    app.register_blueprint(logs_bp, url_prefix="/api/v1/logs")
    app.register_blueprint(scripts_bp, url_prefix="/api/v1/scripts")
    app.register_blueprint(envs_bp, url_prefix="/api/v1/envs")
    app.register_blueprint(open_api_bp, url_prefix="/api/v1/open")
    app.register_blueprint(system_bp, url_prefix="/api/v1/system")
    app.register_blueprint(subs_bp, url_prefix="/api/v1/subscriptions")
    app.register_blueprint(notify_bp, url_prefix="/api/v1/notifications")
    app.register_blueprint(deps_bp, url_prefix="/api/v1/deps")
    app.register_blueprint(users_bp, url_prefix="/api/v1/users")
    app.register_blueprint(config_bp, url_prefix="/api/v1/config")
    app.register_blueprint(security_bp, url_prefix="/api/v1/security")
    app.register_blueprint(ssh_keys_bp, url_prefix="/api/v1/ssh-keys")
    app.register_blueprint(platform_token_bp, url_prefix="/api/v1/platform-tokens")
    app.register_blueprint(api_meta_bp, url_prefix="/api/v1")

    # 向后兼容：保留无版本前缀的路由（标记为已弃用）
    # 这些路由将在未来版本中移除
    app.register_blueprint(auth_bp, url_prefix="/api/auth", name="auth_legacy")
    app.register_blueprint(tasks_bp, url_prefix="/api/tasks", name="tasks_legacy")
    app.register_blueprint(logs_bp, url_prefix="/api/logs", name="logs_legacy")
    app.register_blueprint(scripts_bp, url_prefix="/api/scripts", name="scripts_legacy")
    app.register_blueprint(envs_bp, url_prefix="/api/envs", name="envs_legacy")
    app.register_blueprint(open_api_bp, url_prefix="/api/open", name="open_api_legacy")
    app.register_blueprint(system_bp, url_prefix="/api/system", name="system_legacy")
    app.register_blueprint(subs_bp, url_prefix="/api/subscriptions", name="subs_legacy")
    app.register_blueprint(notify_bp, url_prefix="/api/notifications", name="notify_legacy")
    app.register_blueprint(deps_bp, url_prefix="/api/deps", name="deps_legacy")
    app.register_blueprint(users_bp, url_prefix="/api/users", name="users_legacy")
    app.register_blueprint(config_bp, url_prefix="/api/config", name="config_legacy")
    app.register_blueprint(security_bp, url_prefix="/api/security", name="security_legacy")
    app.register_blueprint(ssh_keys_bp, url_prefix="/api/ssh-keys", name="ssh_keys_legacy")
    app.register_blueprint(platform_token_bp, url_prefix="/api/platform-tokens", name="platform_token_legacy")
    app.register_blueprint(api_meta_bp, url_prefix="/api", name="api_meta_legacy")


def _register_hooks(app: Flask) -> None:
    """注册全局请求钩子"""
    from app.hooks import register_hooks
    register_hooks(app)


def _register_error_handlers(app: Flask) -> None:
    """注册全局错误处理器"""
    import logging
    from werkzeug.exceptions import HTTPException
    from app.utils.errors import APIError
    from app.utils.response import error_response

    logger = logging.getLogger(__name__)

    @app.errorhandler(APIError)
    def handle_api_error(e: APIError):
        """处理业务异常"""
        return error_response(e.message, code=e.code, **e.data)

    @app.errorhandler(HTTPException)
    def handle_http_exception(e: HTTPException):
        """处理HTTP异常"""
        return error_response(e.description or str(e), code=e.code)

    @app.errorhandler(Exception)
    def handle_unexpected_error(e: Exception):
        """处理未预期的异常"""
        logger.exception("Unexpected error occurred")
        # 生产环境不暴露详细错误信息
        if app.config.get("DEBUG"):
            return error_response(f"服务器内部错误: {str(e)}", code=500)
        return error_response("服务器内部错误，请稍后重试", code=500)


def _ensure_directories(app: Flask) -> None:
    """确保数据目录和脚本目录存在"""
    os.makedirs(app.config["DATA_DIR"], exist_ok=True)
    os.makedirs(app.config["SCRIPTS_DIR"], exist_ok=True)
    os.makedirs(app.config["LOG_DIR"], exist_ok=True)


def _init_swagger(app: Flask) -> None:
    """初始化 Flasgger Swagger 文档"""
    try:
        from app.utils.swagger_config import init_swagger
        init_swagger(app)
    except ImportError:
        pass  # flasgger 未安装时静默跳过


def _setup_logging(app: Flask) -> None:
    """配置文件日志（RotatingFileHandler）"""
    import logging
    from logging.handlers import RotatingFileHandler

    log_file = os.path.join(app.config["LOG_DIR"], "daidai.log")
    handler = RotatingFileHandler(
        log_file, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    handler.setLevel(logging.INFO)
    handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))

    # 添加到 root logger
    root_logger = logging.getLogger()
    root_logger.addHandler(handler)
    root_logger.setLevel(logging.INFO)


def _init_maintenance_tasks(app: Flask) -> None:
    """初始化系统维护任务"""
    from app.services.maintenance import init_maintenance_tasks
    init_maintenance_tasks(app)
