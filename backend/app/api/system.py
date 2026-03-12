"""系统信息接口"""

import os
import platform
import logging
from datetime import datetime, timedelta

from flask import Blueprint, jsonify, current_app, request
from flask_jwt_extended import jwt_required
from sqlalchemy import func, cast, Date

from app.extensions import db
from app.models.task import Task
from app.models.log import TaskLog
from app.utils.validators import safe_strip, safe_int

logger = logging.getLogger(__name__)
system_bp = Blueprint("system", __name__)


@system_bp.route("/info", methods=["GET"])
@jwt_required()
def system_info():
    """获取系统信息（CPU/内存/磁盘）"""
    info = {
        "platform": platform.platform(),
        "python": platform.python_version(),
        "hostname": platform.node(),
    }

    # 尝试获取系统资源（psutil 可选）
    try:
        import psutil
        info["cpu_percent"] = psutil.cpu_percent(interval=0.5)
        info["cpu_count"] = psutil.cpu_count()

        mem = psutil.virtual_memory()
        info["memory_total"] = mem.total
        info["memory_used"] = mem.used
        info["memory_percent"] = mem.percent

        disk = psutil.disk_usage("/")
        info["disk_total"] = disk.total
        info["disk_used"] = disk.used
        info["disk_percent"] = disk.percent
    except ImportError:
        info["resource_note"] = "安装 psutil 可获取详细系统资源信息"

    return jsonify({"data": info})


@system_bp.route("/stats", methods=["GET"])
@jwt_required()
def dashboard_stats():
    """获取面板统计数据"""
    total_tasks = Task.query.count()
    enabled_tasks = Task.query.filter_by(status=Task.STATUS_ENABLED).count()
    disabled_tasks = Task.query.filter_by(status=Task.STATUS_DISABLED).count()
    running_tasks = Task.query.filter_by(status=Task.STATUS_RUNNING).count()

    total_logs = TaskLog.query.count()
    success_logs = TaskLog.query.filter_by(status=0).count()
    failed_logs = TaskLog.query.filter_by(status=1).count()

    # 今日执行数
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    today_logs = TaskLog.query.filter(TaskLog.started_at >= today_start).count()

    # 环境变量数
    from app.models.env_var import EnvVar
    env_count = EnvVar.query.count()

    # 订阅数
    try:
        from app.models.subscription import Subscription
        sub_count = Subscription.query.count()
    except Exception:
        sub_count = 0

    # 脚本目录大小
    scripts_dir = current_app.config["SCRIPTS_DIR"]
    scripts_count = 0
    if os.path.isdir(scripts_dir):
        for _, _, files in os.walk(scripts_dir):
            scripts_count += len(files)

    return jsonify({
        "data": {
            "tasks": {
                "total": total_tasks,
                "enabled": enabled_tasks,
                "disabled": disabled_tasks,
                "running": running_tasks,
            },
            "logs": {
                "total": total_logs,
                "success": success_logs,
                "failed": failed_logs,
                "success_rate": round(success_logs / total_logs * 100, 1) if total_logs > 0 else 0,
            },
            "today_logs": today_logs,
            "env_count": env_count,
            "sub_count": sub_count,
            "scripts_count": scripts_count,
        }
    })


@system_bp.route("/stats/trend", methods=["GET"])
@jwt_required()
def execution_trend():
    """获取最近30天执行趋势"""
    days = 30
    end_date = datetime.utcnow().date()
    start_date = end_date - timedelta(days=days - 1)

    # 按日期分组查询
    rows = (
        db.session.query(
            func.date(TaskLog.started_at).label("day"),
            func.count().label("total"),
            func.sum(db.case((TaskLog.status == 0, 1), else_=0)).label("success"),
            func.sum(db.case((TaskLog.status == 1, 1), else_=0)).label("failed"),
        )
        .filter(TaskLog.started_at >= datetime.combine(start_date, datetime.min.time()))
        .group_by(func.date(TaskLog.started_at))
        .all()
    )

    # 构建日期映射
    row_map = {}
    for r in rows:
        day_str = str(r.day)
        row_map[day_str] = {
            "date": day_str,
            "total": int(r.total or 0),
            "success": int(r.success or 0),
            "failed": int(r.failed or 0),
        }

    # 补齐所有日期
    trend = []
    for i in range(days):
        d = start_date + timedelta(days=i)
        ds = d.isoformat()
        trend.append(row_map.get(ds, {"date": ds, "total": 0, "success": 0, "failed": 0}))

    return jsonify({"data": trend})


@system_bp.route("/stats/duration", methods=["GET"])
@jwt_required()
def task_duration_stats():
    """获取任务执行时长统计（Top 10）"""
    # 查询平均执行时长最长的10个任务
    rows = (
        db.session.query(
            Task.id,
            Task.name,
            func.avg(TaskLog.duration).label("avg_duration"),
            func.count(TaskLog.id).label("exec_count"),
        )
        .join(TaskLog, Task.id == TaskLog.task_id)
        .filter(TaskLog.duration.isnot(None))
        .group_by(Task.id, Task.name)
        .order_by(func.avg(TaskLog.duration).desc())
        .limit(10)
        .all()
    )

    data = []
    for r in rows:
        data.append({
            "task_id": r.id,
            "task_name": r.name,
            "avg_duration": round(r.avg_duration, 2) if r.avg_duration else 0,
            "exec_count": r.exec_count,
        })

    return jsonify({"data": data})


@system_bp.route("/stats/task-success-rate", methods=["GET"])
@jwt_required()
def task_success_rate():
    """获取各任务成功率统计"""
    rows = (
        db.session.query(
            Task.id,
            Task.name,
            func.count(TaskLog.id).label("total"),
            func.sum(db.case((TaskLog.status == 0, 1), else_=0)).label("success"),
        )
        .join(TaskLog, Task.id == TaskLog.task_id)
        .group_by(Task.id, Task.name)
        .having(func.count(TaskLog.id) > 0)
        .order_by(func.count(TaskLog.id).desc())
        .limit(10)
        .all()
    )

    data = []
    for r in rows:
        total = r.total or 0
        success = r.success or 0
        data.append({
            "task_id": r.id,
            "task_name": r.name,
            "total": total,
            "success": success,
            "success_rate": round(success / total * 100, 1) if total > 0 else 0,
        })

    return jsonify({"data": data})


@system_bp.route("/backup", methods=["POST"])
@jwt_required()
def create_backup():
    """创建加密数据备份（SQLite 数据库 + 脚本目录 → 加密 tar.gz）

    请求体:
        password: 备份密码（必填，用于加密备份文件）
    """
    import tarfile
    import tempfile
    from datetime import datetime as dt
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    import base64

    data = request.get_json(silent=True) or {}
    password = safe_strip(data.get("password"))

    if not password:
        return jsonify({"error": "必须设置备份密码"}), 400

    if len(password) < 8:
        return jsonify({"error": "备份密码至少 8 个字符"}), 400

    data_dir = current_app.config["DATA_DIR"]
    scripts_dir = current_app.config["SCRIPTS_DIR"]
    db_path = os.path.join(data_dir, "daidai.db")

    # 备份文件名
    timestamp = dt.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = os.path.join(data_dir, "backups")
    os.makedirs(backup_dir, exist_ok=True)
    backup_name = f"daidai_backup_{timestamp}.tar.gz.enc"
    backup_path = os.path.join(backup_dir, backup_name)

    try:
        # 1. 创建临时 tar.gz 文件
        temp_tar = tempfile.NamedTemporaryFile(delete=False, suffix=".tar.gz")
        temp_tar_path = temp_tar.name
        temp_tar.close()

        with tarfile.open(temp_tar_path, "w:gz") as tar:
            # 备份数据库
            if os.path.isfile(db_path):
                tar.add(db_path, arcname="daidai.db")
            # 备份脚本目录
            if os.path.isdir(scripts_dir):
                tar.add(scripts_dir, arcname="scripts")
            # 备份密钥文件
            secret_file = os.path.join(data_dir, ".secret_key")
            if os.path.isfile(secret_file):
                tar.add(secret_file, arcname=".secret_key")
            encryption_secret = os.path.join(data_dir, ".encryption_secret")
            if os.path.isfile(encryption_secret):
                tar.add(encryption_secret, arcname=".encryption_secret")

        # 2. 使用密码加密 tar.gz 文件
        # 生成加密密钥
        salt = b"daidai-backup-salt-v1"  # 固定 salt
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        fernet = Fernet(key)

        # 读取并加密
        with open(temp_tar_path, 'rb') as f:
            plaintext = f.read()

        encrypted = fernet.encrypt(plaintext)

        # 写入加密文件
        with open(backup_path, 'wb') as f:
            f.write(encrypted)

        # 删除临时文件
        os.unlink(temp_tar_path)

        size = os.path.getsize(backup_path)
        return jsonify({
            "message": "加密备份创建成功",
            "data": {
                "filename": backup_name,
                "size": size,
                "created_at": timestamp,
                "encrypted": True
            },
            "warning": "请妥善保管备份密码，丢失后将无法恢复数据！"
        })
    except Exception as e:
        # 清理临时文件
        if 'temp_tar_path' in locals() and os.path.exists(temp_tar_path):
            os.unlink(temp_tar_path)
        logger.error(f"创建备份失败: {e}", exc_info=True)
        return jsonify({"error": f"备份失败: {str(e)}"}), 500


@system_bp.route("/backup/list", methods=["GET"])
@jwt_required()
def list_backups():
    """获取备份列表"""
    data_dir = current_app.config["DATA_DIR"]
    backup_dir = os.path.join(data_dir, "backups")

    if not os.path.isdir(backup_dir):
        return jsonify({"data": []})

    backups = []
    for f in sorted(os.listdir(backup_dir), reverse=True):
        if f.endswith(".tar.gz") or f.endswith(".tar.gz.enc"):
            path = os.path.join(backup_dir, f)
            backups.append({
                "filename": f,
                "size": os.path.getsize(path),
                "created_at": os.path.getmtime(path),
            })

    return jsonify({"data": backups})


@system_bp.route("/backup/download/<filename>", methods=["GET"])
@jwt_required()
def download_backup(filename: str):
    """下载备份文件"""
    import re
    from flask import send_file

    # 安全校验文件名（支持加密和非加密）
    if not re.match(r'^daidai_backup_\d{8}_\d{6}\.tar\.gz(\.enc)?$', filename):
        return jsonify({"error": "无效的文件名"}), 400

    data_dir = current_app.config["DATA_DIR"]
    backup_path = os.path.join(data_dir, "backups", filename)

    if not os.path.isfile(backup_path):
        return jsonify({"error": "备份文件不存在"}), 404

    return send_file(backup_path, as_attachment=True, download_name=filename)


@system_bp.route("/backup/<filename>", methods=["DELETE"])
@jwt_required()
def delete_backup(filename: str):
    """删除备份文件"""
    import re

    # 支持加密和非加密备份
    if not re.match(r'^daidai_backup_\d{8}_\d{6}\.tar\.gz(\.enc)?$', filename):
        return jsonify({"error": "无效的文件名"}), 400

    data_dir = current_app.config["DATA_DIR"]
    backup_path = os.path.join(data_dir, "backups", filename)

    if not os.path.isfile(backup_path):
        return jsonify({"error": "备份文件不存在"}), 404

    os.remove(backup_path)
    return jsonify({"message": "备份已删除"})


@system_bp.route("/restore", methods=["POST"])
@jwt_required()
def restore_backup():
    """从加密备份文件恢复数据

    请求体:
        filename: 备份文件名
        password: 备份密码（如果是加密备份）
    """
    import tarfile
    import tempfile
    from flask import request
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    import base64

    data = request.get_json(silent=True) or {}
    filename = data.get("filename", "")
    password = data.get("password", "")

    import re
    # 支持加密和非加密备份
    if not re.match(r'^daidai_backup_\d{8}_\d{6}\.tar\.gz(\.enc)?$', filename):
        return jsonify({"error": "无效的文件名"}), 400

    is_encrypted = filename.endswith('.enc')

    if is_encrypted and not password:
        return jsonify({"error": "加密备份需要提供密码"}), 400

    data_dir = current_app.config["DATA_DIR"]
    scripts_dir = current_app.config["SCRIPTS_DIR"]
    backup_path = os.path.join(data_dir, "backups", filename)

    if not os.path.isfile(backup_path):
        return jsonify({"error": "备份文件不存在"}), 404

    try:
        tar_path = backup_path

        # 如果是加密备份，先解密
        if is_encrypted:
            # 生成解密密钥
            salt = b"daidai-backup-salt-v1"
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=100000,
            )
            key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
            fernet = Fernet(key)

            # 读取并解密
            with open(backup_path, 'rb') as f:
                encrypted = f.read()

            try:
                decrypted = fernet.decrypt(encrypted)
            except Exception:
                return jsonify({"error": "密码错误或备份文件已损坏"}), 400

            # 写入临时文件
            temp_tar = tempfile.NamedTemporaryFile(delete=False, suffix=".tar.gz")
            temp_tar.write(decrypted)
            temp_tar.close()
            tar_path = temp_tar.name

        # 解压备份
        with tarfile.open(tar_path, "r:gz") as tar:
            # 恢复数据库
            if "daidai.db" in tar.getnames():
                tar.extract("daidai.db", path=data_dir)
            # 恢复脚本目录
            if "scripts" in tar.getnames():
                tar.extractall(path=data_dir, members=[m for m in tar.getmembers() if m.name.startswith("scripts")])
            # 恢复密钥文件
            if ".secret_key" in tar.getnames():
                tar.extract(".secret_key", path=data_dir)
            if ".encryption_secret" in tar.getnames():
                tar.extract(".encryption_secret", path=data_dir)

        # 清理临时文件
        if is_encrypted and 'temp_tar' in locals():
            os.unlink(temp_tar.name)

        return jsonify({"message": "数据恢复成功，请重启面板使其生效"})
    except Exception as e:
        # 清理临时文件
        if is_encrypted and 'temp_tar' in locals() and os.path.exists(temp_tar.name):
            os.unlink(temp_tar.name)
        logger.error(f"恢复备份失败: {e}", exc_info=True)
        return jsonify({"error": f"恢复失败: {str(e)}"}), 500


@system_bp.route("/resource-stream-token", methods=["POST"])
@jwt_required()
def get_resource_stream_token():
    """获取 SSE 资源监控的临时 Token（60 秒有效）

    由于浏览器 EventSource API 不支持自定义请求头，
    需要先调用此接口获取临时 Token，然后用于 SSE 连接
    """
    from flask_jwt_extended import get_jwt_identity
    from app.models.user import User
    from app.utils.sse_token import sse_token_manager

    identity = get_jwt_identity()
    user = User.query.filter_by(username=identity).first()

    if not user:
        return jsonify({"error": "用户不存在"}), 404

    # 生成 60 秒有效的临时 Token
    temp_token = sse_token_manager.generate_token(user.id, expires_in=60)

    return jsonify({
        "temp_token": temp_token,
        "expires_in": 60,
        "stream_url": f"/api/v1/system/resource-stream?token={temp_token}"
    })


@system_bp.route("/resource-stream", methods=["GET"])
def resource_stream():
    """SSE 推送系统资源实时数据（CPU/内存/磁盘），每 3 秒一次

    使用临时 Token 验证身份（通过 /resource-stream-token 接口获取）
    临时 Token 仅 60 秒有效，降低泄露风险
    """
    import json
    import time
    from flask import Response, request as req
    from app.utils.sse_token import sse_token_manager

    temp_token = req.args.get("token", "")
    if not temp_token:
        return jsonify({"error": "缺少 token"}), 401

    # 验证临时 Token
    user_id = sse_token_manager.verify_token(temp_token)
    if not user_id:
        return jsonify({"error": "无效或过期的 token"}), 401

    def generate():
        try:
            while True:
                data = {}
                try:
                    import psutil
                    data["cpu"] = psutil.cpu_percent(interval=1)
                    mem = psutil.virtual_memory()
                    data["memory"] = round(mem.percent, 1)
                    data["memory_used"] = round(mem.used / 1024 / 1024, 1)
                    data["memory_total"] = round(mem.total / 1024 / 1024, 1)
                    disk = psutil.disk_usage("/")
                    data["disk"] = round(disk.percent, 1)
                    data["ts"] = int(time.time())
                except ImportError:
                    data = {"cpu": 0, "memory": 0, "disk": 0, "ts": int(time.time())}
                yield f"data: {json.dumps(data)}\n\n"
                time.sleep(3)
        finally:
            # 连接关闭时撤销临时 Token
            sse_token_manager.revoke_token(temp_token)

    return Response(generate(), mimetype="text/event-stream", headers={
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
    })


PANEL_VERSION = "0.1.1"
GITHUB_REPO = "linzixuanzz/daidai-panel"  # 实际部署时替换


@system_bp.route("/version", methods=["GET"])
@jwt_required()
def get_version():
    """获取当前面板版本"""
    return jsonify({"version": PANEL_VERSION})


@system_bp.route("/check-update", methods=["GET"])
@jwt_required()
def check_update():
    """检查面板更新（从 GitHub Releases 获取最新版本）"""
    from flask import request as req
    import json
    from urllib.request import Request, urlopen
    from urllib.error import URLError

    try:
        api_url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
        r = Request(api_url, headers={"User-Agent": "DaidaiPanel", "Accept": "application/vnd.github.v3+json"})
        with urlopen(r, timeout=10) as resp:
            data = json.loads(resp.read().decode())

        latest = data.get("tag_name", "").lstrip("v")
        has_update = latest > PANEL_VERSION if latest else False

        return jsonify({
            "current": PANEL_VERSION,
            "latest": latest,
            "has_update": has_update,
            "release_url": data.get("html_url", ""),
            "release_notes": data.get("body", "")[:2000],
            "published_at": data.get("published_at", ""),
        })
    except URLError as e:
        return jsonify({"error": f"检查更新失败: {e.reason}", "current": PANEL_VERSION}), 500
    except Exception as e:
        return jsonify({"error": f"检查更新异常: {str(e)}", "current": PANEL_VERSION}), 500


@system_bp.route("/panel-log", methods=["GET"])
@jwt_required()
def panel_log():
    """查看面板自身运行日志

    查询参数:
        lines: 返回最后 N 行（默认 200，最大 2000）
        keyword: 关键字过滤（可选）
    """
    from flask import request
    import logging

    lines = min(safe_int(request.args.get("lines"), default=200), 2000)
    keyword = safe_strip(request.args.get("keyword", ""))

    log_dir = current_app.config["LOG_DIR"]
    log_file = os.path.join(log_dir, "daidai.log")

    if not os.path.isfile(log_file):
        return jsonify({"data": [], "total": 0})

    try:
        with open(log_file, "r", encoding="utf-8", errors="replace") as f:
            all_lines = f.readlines()

        # 取最后 N 行
        tail = all_lines[-lines:] if len(all_lines) > lines else all_lines

        if keyword:
            tail = [l for l in tail if keyword.lower() in l.lower()]

        return jsonify({
            "data": [l.rstrip("\n") for l in tail],
            "total": len(tail),
            "file_size": os.path.getsize(log_file),
        })
    except Exception as e:
        return jsonify({"error": f"读取日志失败: {str(e)}"}), 500
