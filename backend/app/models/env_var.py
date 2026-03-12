"""环境变量模型"""

from datetime import datetime

from app.extensions import db

# Position 排序系统常量（参考青龙）
INIT_POSITION = 10000.0
MAX_POSITION = float(9007199254740991)  # Number.MAX_SAFE_INTEGER
MIN_POSITION = 1.0


class EnvVar(db.Model):
    """环境变量表"""
    __tablename__ = "env_vars"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False, index=True)
    value = db.Column(db.Text, nullable=False, default="")
    remarks = db.Column(db.String(256), default="")
    enabled = db.Column(db.Boolean, default=True)

    # Position 排序系统（参考青龙，使用浮点数）
    position = db.Column(db.Float, default=INIT_POSITION, index=True)

    # 保留旧字段以兼容，但不再使用
    sort_order = db.Column(db.Integer, default=0)

    group = db.Column(db.String(64), default="", index=True)  # 分组
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "value": self.value,
            "remarks": self.remarks,
            "enabled": self.enabled,
            "position": self.position,
            "sort_order": self.sort_order,  # 保留以兼容前端
            "group": self.group,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
