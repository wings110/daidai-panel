"""任务日志模型"""

from datetime import datetime

from app.extensions import db


class TaskLog(db.Model):
    """任务执行日志表"""
    __tablename__ = "task_logs"

    # 状态常量
    STATUS_RUNNING = 2  # 执行中
    STATUS_SUCCESS = 0  # 成功
    STATUS_FAILED = 1   # 失败

    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey("tasks.id"), nullable=False, index=True)
    content = db.Column(db.Text, default="")  # 保留用于兼容，实际日志存储在文件中
    status = db.Column(db.Integer, nullable=True)  # 0=成功, 1=失败, 2=执行中
    duration = db.Column(db.Float, nullable=True)
    log_path = db.Column(db.String(256), nullable=True)  # 日志文件路径
    started_at = db.Column(db.DateTime, default=datetime.utcnow)
    ended_at = db.Column(db.DateTime, nullable=True)

    def to_dict(self) -> dict:
        """序列化为字典"""
        return {
            "id": self.id,
            "task_id": self.task_id,
            "task_name": self.task.name if self.task else None,
            "content": self.content,
            "status": self.status,
            "duration": self.duration,
            "log_path": self.log_path,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
        }
