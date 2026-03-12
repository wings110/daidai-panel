"""系统配置模型 - KV 存储"""

from datetime import datetime

from app.extensions import db


# 默认配置项及其默认值
DEFAULT_CONFIGS = {
    # 订阅相关
    "auto_add_cron": "true",           # 订阅拉取时自动为新脚本创建定时任务
    "auto_del_cron": "true",           # 订阅拉取时自动删除已失效脚本的定时任务
    "default_cron_rule": "0 9 * * *",  # 匹配不到定时规则时的默认 Cron
    "repo_file_extensions": "py js sh ts",  # 拉取脚本的文件后缀

    # 代理
    "proxy_url": "",                   # HTTP/SOCKS5 代理，如 http://127.0.0.1:7890

    # 资源告警阈值（百分比）
    "cpu_warn": "80",
    "memory_warn": "80",
    "disk_warn": "90",

    # 任务执行
    "command_timeout": "300",          # 全局默认超时（秒）
    "max_concurrent_tasks": "5",       # 最大并发执行任务数
    "max_log_content_size": "102400",  # 单条任务日志最大字符数（默认 100KB）
    "log_retention_days": "3",         # 日志保留天数（自动清理）
    "random_delay": "",               # 随机延迟最大秒数，空表示不延迟
    "random_delay_extensions": "",    # 需要随机延迟的文件后缀，空表示全部

    # 通知
    "notify_on_resource_warn": "true",  # 资源超限时是否发送通知
    "notify_on_login": "false",          # 登录成功时是否发送通知

    # 软件包镜像源
    "python_registry": "",               # Python 包镜像源（如 https://pypi.tuna.tsinghua.edu.cn/simple）
    "node_registry": "",                 # Node 包镜像源（如 https://registry.npmmirror.com）

    # 极验验证码
    "geetest_enabled": "false",          # 是否启用极验验证码
    "geetest_captcha_id": "",            # 极验 Captcha ID
    "geetest_captcha_key": "",           # 极验 Captcha Key
}


class SystemConfig(db.Model):
    """系统配置表（Key-Value 形式）"""
    __tablename__ = "system_configs"

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(64), unique=True, nullable=False, index=True)
    value = db.Column(db.Text, default="")
    description = db.Column(db.String(256), default="")
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "value": self.value,
            "description": self.description,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    @staticmethod
    def get(key: str, default: str = "") -> str:
        """获取配置值"""
        cfg = SystemConfig.query.filter_by(key=key).first()
        if cfg:
            return cfg.value
        return DEFAULT_CONFIGS.get(key, default)

    @staticmethod
    def get_bool(key: str) -> bool:
        """获取布尔型配置"""
        return SystemConfig.get(key).lower() in ("true", "1", "yes")

    @staticmethod
    def get_int(key: str, default: int = 0) -> int:
        """获取整数型配置"""
        val = SystemConfig.get(key)
        try:
            return int(val) if val else default
        except ValueError:
            return default

    @staticmethod
    def set(key: str, value: str, description: str = "") -> None:
        """设置配置值"""
        cfg = SystemConfig.query.filter_by(key=key).first()
        if cfg:
            cfg.value = value
            if description:
                cfg.description = description
        else:
            cfg = SystemConfig(key=key, value=value, description=description)
            db.session.add(cfg)

    @staticmethod
    def init_defaults() -> None:
        """初始化默认配置（只创建不存在的项）"""
        descriptions = {
            "auto_add_cron": "订阅拉取时自动为新脚本创建定时任务",
            "auto_del_cron": "订阅拉取时自动删除已失效脚本的定时任务",
            "default_cron_rule": "匹配不到定时规则时的默认 Cron 表达式",
            "repo_file_extensions": "拉取脚本的文件后缀（空格分隔）",
            "proxy_url": "HTTP/SOCKS5 代理地址",
            "cpu_warn": "CPU 使用率告警阈值（%）",
            "memory_warn": "内存使用率告警阈值（%）",
            "disk_warn": "磁盘使用率告警阈值（%）",
            "command_timeout": "全局默认任务超时时间（秒）",
            "max_concurrent_tasks": "最大并发执行任务数",
            "max_log_content_size": "单条任务日志最大字符数",
            "log_retention_days": "日志保留天数（自动清理超过该天数的日志）",
            "random_delay": "任务随机延迟最大秒数（空=不延迟）",
            "random_delay_extensions": "需要随机延迟的文件后缀（空格分隔，空=全部）",
            "notify_on_resource_warn": "资源超限时是否发送通知",
            "notify_on_login": "登录成功时是否发送通知",
            "python_registry": "Python 包镜像源地址",
            "node_registry": "Node 包镜像源地址",
            "geetest_enabled": "是否启用极验验证码",
            "geetest_captcha_id": "极验 Captcha ID",
            "geetest_captcha_key": "极验 Captcha Key",
        }
        for key, default_val in DEFAULT_CONFIGS.items():
            existing = SystemConfig.query.filter_by(key=key).first()
            if not existing:
                cfg = SystemConfig(
                    key=key,
                    value=default_val,
                    description=descriptions.get(key, ""),
                )
                db.session.add(cfg)
        db.session.commit()
