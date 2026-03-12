"""订阅管理模型"""

from datetime import datetime

from app.extensions import db


class Subscription(db.Model):
    """订阅表 - 定时从远程仓库拉取脚本（参考青龙）"""
    __tablename__ = "subscriptions"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False)
    url = db.Column(db.String(1024), nullable=False)
    sub_type = db.Column(db.String(16), default="git")  # git | file
    branch = db.Column(db.String(64), default="main")
    schedule = db.Column(db.String(64), default="0 0 * * *")  # Cron 表达式
    whitelist = db.Column(db.Text, default="")  # 只拉取匹配的文件，逗号分隔 glob
    blacklist = db.Column(db.Text, default="")  # 排除的文件
    target_dir = db.Column(db.String(256), default="")  # 存放子目录
    enabled = db.Column(db.Boolean, default=True)

    # SSH 密钥支持（参考青龙）
    use_ssh_key = db.Column(db.Boolean, default=False)  # 是否使用 SSH 密钥
    ssh_key_id = db.Column(db.Integer, db.ForeignKey("ssh_keys.id"), nullable=True)  # SSH 密钥 ID

    # 订阅钩子（参考青龙）
    sub_before = db.Column(db.Text, nullable=True)  # 拉取前执行的脚本
    sub_after = db.Column(db.Text, nullable=True)  # 拉取后执行的脚本

    # 拉取选项
    pull_option = db.Column(db.String(16), default="merge")  # merge | rebase | force

    last_pull_at = db.Column(db.DateTime, nullable=True)
    last_pull_status = db.Column(db.Integer, default=-1)  # -1=未执行, 0=成功, 1=失败
    last_pull_message = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关联 SSH 密钥
    ssh_key = db.relationship("SSHKey", backref="subscriptions", lazy=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "url": self.url,
            "sub_type": self.sub_type or "git",
            "branch": self.branch,
            "schedule": self.schedule,
            "whitelist": self.whitelist,
            "blacklist": self.blacklist,
            "target_dir": self.target_dir,
            "enabled": self.enabled,
            "use_ssh_key": self.use_ssh_key,
            "ssh_key_id": self.ssh_key_id,
            "sub_before": self.sub_before,
            "sub_after": self.sub_after,
            "pull_option": self.pull_option,
            "last_pull_at": self.last_pull_at.isoformat() if self.last_pull_at else None,
            "last_pull_status": self.last_pull_status,
            "last_pull_message": self.last_pull_message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class SSHKey(db.Model):
    """SSH 密钥表（参考青龙）"""
    __tablename__ = "ssh_keys"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False)
    private_key = db.Column(db.Text, nullable=False)  # 加密存储
    public_key = db.Column(db.Text, nullable=False)
    remarks = db.Column(db.String(256), default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self, include_private: bool = False) -> dict:
        result = {
            "id": self.id,
            "name": self.name,
            "public_key": self.public_key,
            "remarks": self.remarks,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
        if include_private:
            result["private_key"] = self.private_key
        return result
