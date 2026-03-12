"""定时任务模型"""

from datetime import datetime

from app.extensions import db


class Task(db.Model):
    """定时任务表"""
    __tablename__ = "tasks"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False)
    command = db.Column(db.Text, nullable=False)
    cron_expression = db.Column(db.String(64), nullable=False)
    status = db.Column(db.Float, nullable=False, default=1)  # 0=禁用, 0.5=排队中, 1=启用, 2=运行中
    labels = db.Column(db.String(256), default="")
    last_run_at = db.Column(db.DateTime, nullable=True)
    last_run_status = db.Column(db.Integer, nullable=True)  # 0=成功, 1=失败
    timeout = db.Column(db.Integer, default=300)
    max_retries = db.Column(db.Integer, default=0)
    retry_interval = db.Column(db.Integer, default=60)
    notify_on_failure = db.Column(db.Boolean, default=True)
    depends_on = db.Column(db.Integer, db.ForeignKey("tasks.id"), nullable=True)  # 前置任务 ID
    sort_order = db.Column(db.Integer, default=0)

    # 新增字段（参考青龙）
    is_pinned = db.Column(db.Boolean, default=False)  # 是否置顶
    pid = db.Column(db.Integer, nullable=True)  # 进程 ID
    log_path = db.Column(db.String(256), nullable=True)  # 当前日志文件路径
    last_running_time = db.Column(db.Float, nullable=True)  # 上次运行时长（秒）

    # 任务钩子（参考青龙）
    task_before = db.Column(db.Text, nullable=True)  # 任务执行前的脚本
    task_after = db.Column(db.Text, nullable=True)  # 任务执行后的脚本

    # 多实例支持
    allow_multiple_instances = db.Column(db.Boolean, default=False)  # 是否允许多实例运行

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关联日志
    logs = db.relationship("TaskLog", backref="task", lazy="dynamic", cascade="all, delete-orphan")

    # 状态常量
    STATUS_DISABLED = 0
    STATUS_QUEUED = 0.5
    STATUS_ENABLED = 1
    STATUS_RUNNING = 2

    RUN_SUCCESS = 0
    RUN_FAILED = 1

    def to_dict(self) -> dict:
        """序列化为字典"""
        return {
            "id": self.id,
            "name": self.name,
            "command": self.command,
            "cron_expression": self.cron_expression,
            "status": self.status,
            "labels": self.labels.split(",") if self.labels else [],
            "last_run_at": self.last_run_at.isoformat() if self.last_run_at else None,
            "last_run_status": self.last_run_status,
            "timeout": self.timeout,
            "max_retries": self.max_retries,
            "retry_interval": self.retry_interval,
            "notify_on_failure": self.notify_on_failure,
            "depends_on": self.depends_on,
            "sort_order": self.sort_order,
            "is_pinned": self.is_pinned,
            "pid": self.pid,
            "log_path": self.log_path,
            "last_running_time": self.last_running_time,
            "task_before": self.task_before,
            "task_after": self.task_after,
            "allow_multiple_instances": self.allow_multiple_instances,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
