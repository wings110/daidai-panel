"""定时任务接口"""

import os
import re
import logging

from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required

from app.extensions import db
from app.models.task import Task
from app.utils.command_validator import validate_command, CommandValidationError
from app.utils.validators import safe_strip, safe_int, safe_bool

logger = logging.getLogger(__name__)
tasks_bp = Blueprint("tasks", __name__)


@tasks_bp.route("", methods=["GET"])
@jwt_required()
def list_tasks():
    """获取任务列表，支持搜索和过滤

    查询参数:
        keyword: 搜索关键词（名称/命令）
        status: 状态过滤 (0/1/2)
        label: 标签过滤
        page: 页码（默认 1）
        page_size: 每页数量（默认 20）
    """
    keyword = safe_strip(request.args.get("keyword", ""))
    status = safe_int(request.args.get("status"), default=None)
    label = safe_strip(request.args.get("label", ""))
    page = request.args.get("page", 1, type=int)
    page_size = request.args.get("page_size", 20, type=int)

    query = Task.query

    if keyword:
        query = query.filter(
            db.or_(
                Task.name.ilike(f"%{keyword}%"),
                Task.command.ilike(f"%{keyword}%"),
            )
        )
    if status is not None:
        query = query.filter_by(status=status)
    if label:
        query = query.filter(Task.labels.ilike(f"%{label}%"))

    query = query.order_by(Task.is_pinned.desc(), Task.sort_order.asc(), Task.created_at.desc())
    pagination = query.paginate(page=page, per_page=page_size, error_out=False)

    return jsonify({
        "data": [t.to_dict() for t in pagination.items],
        "total": pagination.total,
        "page": page,
        "page_size": page_size,
    })


@tasks_bp.route("", methods=["POST"])
@jwt_required()
def create_task():
    """创建定时任务

    请求体:
        name: 任务名称
        command: 脚本文件路径
        cron_expression: Cron 表达式
        timeout: 超时时间（秒，可选）
        max_retries: 最大重试次数（可选）
        retry_interval: 重试间隔秒数（可选）
        notify_on_failure: 失败通知开关（可选）
        labels: 标签列表（可选）
    """
    try:
        data = request.get_json(silent=True) or {}

        # 参数校验 - 使用安全的类型转换
        name = safe_strip(data.get("name"))
        command = safe_strip(data.get("command"))
        cron_expression = safe_strip(data.get("cron_expression"))

        if not name:
            return jsonify({"error": "任务名称不能为空"}), 400
        if not command:
            return jsonify({"error": "执行命令不能为空"}), 400

        # 使用安全的命令验证器
        try:
            scripts_dir = current_app.config.get("SCRIPTS_DIR", os.path.abspath("./data/scripts"))
            validate_command(command, scripts_dir)
        except CommandValidationError as e:
            return jsonify({"error": str(e)}), 400

        if not _validate_cron(cron_expression):
            return jsonify({"error": "无效的 Cron 表达式"}), 400

        labels = data.get("labels", [])
        if isinstance(labels, list):
            labels = ",".join(labels)

        task = Task(
            name=name,
            command=command,
            cron_expression=cron_expression,
            timeout=safe_int(data.get("timeout"), default=300),
            max_retries=safe_int(data.get("max_retries"), default=0),
            retry_interval=safe_int(data.get("retry_interval"), default=60),
            notify_on_failure=safe_bool(data.get("notify_on_failure"), default=True),
            depends_on=data.get("depends_on") or None,
            labels=labels,
        )
        db.session.add(task)
        db.session.commit()

        # 注册到调度器
        from app.services.scheduler import add_job
        add_job(task)

        return jsonify({"message": "任务创建成功", "data": task.to_dict()}), 201
    except Exception as e:
        db.session.rollback()
        logger.error(f"创建任务失败: {e}", exc_info=True)
        return jsonify({"error": f"创建失败: {str(e)}"}), 500


@tasks_bp.route("/<int:task_id>", methods=["PUT"])
@jwt_required()
def update_task(task_id: int):
    """更新定时任务"""
    try:
        task = Task.query.get(task_id)
        if not task:
            return jsonify({"error": "任务不存在"}), 404

        data = request.get_json(silent=True) or {}

        if "name" in data:
            task.name = safe_strip(data["name"])
        if "command" in data:
            command = safe_strip(data["command"])
            # 使用安全的命令验证器
            try:
                scripts_dir = current_app.config.get("SCRIPTS_DIR", os.path.abspath("./data/scripts"))
                validate_command(command, scripts_dir)
            except CommandValidationError as e:
                return jsonify({"error": str(e)}), 400
            task.command = command
        if "cron_expression" in data:
            cron = safe_strip(data["cron_expression"])
            if not _validate_cron(cron):
                return jsonify({"error": "无效的 Cron 表达式"}), 400
            task.cron_expression = cron
        if "timeout" in data:
            task.timeout = safe_int(data["timeout"], default=300)
        if "max_retries" in data:
            task.max_retries = safe_int(data["max_retries"], default=0)
        if "retry_interval" in data:
            task.retry_interval = safe_int(data["retry_interval"], default=60)
        if "notify_on_failure" in data:
            task.notify_on_failure = safe_bool(data["notify_on_failure"], default=True)
        if "depends_on" in data:
            task.depends_on = data["depends_on"] or None
        if "labels" in data:
            labels = data["labels"]
            task.labels = ",".join(labels) if isinstance(labels, list) else labels

        db.session.commit()

        # 更新调度器
        from app.services.scheduler import update_job
        update_job(task)

        return jsonify({"message": "任务更新成功", "data": task.to_dict()})
    except Exception as e:
        db.session.rollback()
        logger.error(f"更新任务失败: {e}", exc_info=True)
        return jsonify({"error": f"更新失败: {str(e)}"}), 500


@tasks_bp.route("/<int:task_id>", methods=["DELETE"])
@jwt_required()
def delete_task(task_id: int):
    """删除定时任务"""
    task = Task.query.get(task_id)
    if not task:
        return jsonify({"error": "任务不存在"}), 404

    # 从调度器移除
    from app.services.scheduler import remove_job
    remove_job(task_id)

    db.session.delete(task)
    db.session.commit()

    return jsonify({"message": "任务删除成功"})


@tasks_bp.route("/<int:task_id>/run", methods=["PUT"])
@jwt_required()
def run_task(task_id: int):
    """手动执行任务"""
    task = Task.query.get(task_id)
    if not task:
        return jsonify({"error": "任务不存在"}), 404
    if task.status == Task.STATUS_RUNNING:
        return jsonify({"error": "任务正在运行中"}), 400

    from app.services.scheduler import run_task_now
    run_task_now(task)

    return jsonify({"message": f"任务 [{task.name}] 已触发执行"})


@tasks_bp.route("/<int:task_id>/stop", methods=["PUT"])
@jwt_required()
def stop_task(task_id: int):
    """停止运行中的任务"""
    task = Task.query.get(task_id)
    if not task:
        return jsonify({"error": "任务不存在"}), 404

    from app.services.scheduler import stop_running_task
    stopped = stop_running_task(task_id)

    if stopped:
        return jsonify({"message": f"任务 [{task.name}] 已停止"})
    return jsonify({"error": "任务未在运行"}), 400


@tasks_bp.route("/<int:task_id>/latest-log", methods=["GET"])
@jwt_required()
def get_latest_log(task_id: int):
    """获取任务的最新日志"""
    from app.models.log import TaskLog

    task = Task.query.get(task_id)
    if not task:
        return jsonify({"error": "任务不存在"}), 404

    # 查询最新的日志记录
    latest_log = TaskLog.query.filter_by(task_id=task_id)\
        .order_by(TaskLog.started_at.desc())\
        .first()

    if not latest_log:
        return jsonify({"error": "暂无日志记录"}), 404

    from app.api.logs import _log_to_dict_with_file_content
    return jsonify({"data": _log_to_dict_with_file_content(latest_log)})


@tasks_bp.route("/<int:task_id>/enable", methods=["PUT"])
@jwt_required()
def enable_task(task_id: int):
    """启用任务"""
    task = Task.query.get(task_id)
    if not task:
        return jsonify({"error": "任务不存在"}), 404

    task.status = Task.STATUS_ENABLED
    db.session.commit()

    from app.services.scheduler import add_job
    add_job(task)

    return jsonify({"message": f"任务 [{task.name}] 已启用", "data": task.to_dict()})


@tasks_bp.route("/<int:task_id>/disable", methods=["PUT"])
@jwt_required()
def disable_task(task_id: int):
    """禁用任务"""
    task = Task.query.get(task_id)
    if not task:
        return jsonify({"error": "任务不存在"}), 404

    task.status = Task.STATUS_DISABLED
    db.session.commit()

    from app.services.scheduler import remove_job
    remove_job(task_id)

    return jsonify({"message": f"任务 [{task.name}] 已禁用", "data": task.to_dict()})


@tasks_bp.route("/<int:task_id>/pin", methods=["PUT"])
@jwt_required()
def pin_task(task_id: int):
    """置顶任务"""
    task = Task.query.get(task_id)
    if not task:
        return jsonify({"error": "任务不存在"}), 404

    task.is_pinned = True
    db.session.commit()

    return jsonify({"message": f"任务 [{task.name}] 已置顶", "data": task.to_dict()})


@tasks_bp.route("/<int:task_id>/unpin", methods=["PUT"])
@jwt_required()
def unpin_task(task_id: int):
    """取消置顶任务"""
    task = Task.query.get(task_id)
    if not task:
        return jsonify({"error": "任务不存在"}), 404

    task.is_pinned = False
    db.session.commit()

    return jsonify({"message": f"任务 [{task.name}] 已取消置顶", "data": task.to_dict()})


@tasks_bp.route("/<int:task_id>/copy", methods=["POST"])
@jwt_required()
def copy_task(task_id: int):
    """复制任务"""
    task = Task.query.get(task_id)
    if not task:
        return jsonify({"error": "任务不存在"}), 404

    # 创建新任务，复制所有字段
    new_task = Task(
        name=f"{task.name} (副本)",
        command=task.command,
        cron_expression=task.cron_expression,
        status=Task.STATUS_DISABLED,  # 复制的任务默认禁用
        labels=task.labels,
        timeout=task.timeout,
        max_retries=task.max_retries,
        retry_interval=task.retry_interval,
        notify_on_failure=task.notify_on_failure,
        depends_on=task.depends_on,
        is_pinned=False,  # 复制的任务不置顶
    )
    db.session.add(new_task)
    db.session.commit()

    return jsonify({"message": "任务复制成功", "data": new_task.to_dict()}), 201


@tasks_bp.route("/batch", methods=["PUT"])
@jwt_required()
def batch_operation():
    """批量操作任务

    请求体:
        ids: 任务 ID 列表
        action: 操作类型 (enable/disable/delete/run/pin/unpin)
    """
    data = request.get_json(silent=True) or {}
    ids = data.get("ids", [])
    action = data.get("action", "")

    if not ids or not isinstance(ids, list):
        return jsonify({"error": "请选择要操作的任务"}), 400
    if action not in ("enable", "disable", "delete", "run", "pin", "unpin"):
        return jsonify({"error": "无效的操作类型"}), 400

    tasks = Task.query.filter(Task.id.in_(ids)).all()

    from app.services.scheduler import add_job, remove_job, run_task_now

    count = 0
    try:
        for task in tasks:
            if action == "enable":
                task.status = Task.STATUS_ENABLED
                add_job(task)
            elif action == "disable":
                task.status = Task.STATUS_DISABLED
                remove_job(task.id)
            elif action == "delete":
                remove_job(task.id)
                db.session.delete(task)
            elif action == "run":
                if task.status != Task.STATUS_RUNNING:
                    run_task_now(task)
            elif action == "pin":
                task.is_pinned = True
            elif action == "unpin":
                task.is_pinned = False
            count += 1

        # 统一提交事务
        db.session.commit()
        return jsonify({"message": f"成功操作 {count} 个任务"})
    except Exception as e:
        # 回滚事务
        db.session.rollback()
        return jsonify({"error": f"批量操作失败: {str(e)}"}), 500


@tasks_bp.route("/<int:task_id>/live-logs", methods=["GET"])
@jwt_required()
def get_task_live_logs(task_id: int):
    """获取任务的实时日志

    返回:
        logs: 日志行列表
        done: 是否执行完成
    """
    task = Task.query.get(task_id)
    if not task:
        return jsonify({"error": "任务不存在"}), 404

    from app.services.scheduler import get_live_log
    logs, done = get_live_log(task_id)

    return jsonify({
        "logs": logs,
        "done": done,
        "status": task.status,
    })


@tasks_bp.route("/<int:task_id>/log-files", methods=["GET"])
@jwt_required()
def list_task_log_files(task_id: int):
    """获取任务的所有日志文件列表"""
    from flask import current_app
    from app.services.log_manager import list_log_files

    task = Task.query.get(task_id)
    if not task:
        return jsonify({"error": "任务不存在"}), 404

    log_files = list_log_files(task_id, current_app.config["LOG_DIR"])
    return jsonify({"data": log_files})


@tasks_bp.route("/<int:task_id>/log-files/<path:filename>", methods=["GET"])
@jwt_required()
def get_log_file_content(task_id: int, filename: str):
    """获取指定日志文件的内容"""
    from flask import current_app
    from app.services.log_manager import read_log_file

    task = Task.query.get(task_id)
    if not task:
        return jsonify({"error": "任务不存在"}), 404

    log_path = f"task_{task_id}/{filename}"
    content = read_log_file(log_path, current_app.config["LOG_DIR"])

    return jsonify({
        "filename": filename,
        "content": content,
    })


@tasks_bp.route("/<int:task_id>/log-files/<path:filename>", methods=["DELETE"])
@jwt_required()
def delete_log_file_api(task_id: int, filename: str):
    """删除指定日志文件"""
    from flask import current_app
    from app.services.log_manager import delete_log_file

    task = Task.query.get(task_id)
    if not task:
        return jsonify({"error": "任务不存在"}), 404

    log_path = f"task_{task_id}/{filename}"
    success = delete_log_file(log_path, current_app.config["LOG_DIR"])

    if success:
        return jsonify({"message": "日志文件删除成功"})
    return jsonify({"error": "删除失败"}), 500


@tasks_bp.route("/<int:task_id>/log-files/<path:filename>/download", methods=["GET"])
@jwt_required()
def download_log_file(task_id: int, filename: str):
    """下载日志文件"""
    from flask import current_app, send_file
    import os

    task = Task.query.get(task_id)
    if not task:
        return jsonify({"error": "任务不存在"}), 404

    log_path = f"task_{task_id}/{filename}"
    full_path = os.path.join(current_app.config["LOG_DIR"], log_path)

    if not os.path.exists(full_path):
        return jsonify({"error": "日志文件不存在"}), 404

    return send_file(
        full_path,
        as_attachment=True,
        download_name=filename,
        mimetype='text/plain'
    )


@tasks_bp.route("/clean-logs", methods=["DELETE"])
@jwt_required()
def clean_old_logs():
    """清理旧日志文件"""
    from flask import current_app
    from app.services.log_manager import clean_old_logs

    days = request.args.get("days", 7, type=int)
    if days < 1:
        return jsonify({"error": "保留天数必须大于 0"}), 400

    deleted_count = clean_old_logs(current_app.config["LOG_DIR"], days)
    return jsonify({"message": f"成功清理 {deleted_count} 个日志文件"})


@tasks_bp.route("/export", methods=["GET"])
@jwt_required()
def export_tasks():
    """导出所有任务为 JSON"""
    tasks = Task.query.all()
    tasks_data = []

    for task in tasks:
        task_dict = task.to_dict()
        # 移除不需要导出的字段
        task_dict.pop('id', None)
        task_dict.pop('created_at', None)
        task_dict.pop('updated_at', None)
        task_dict.pop('last_run_at', None)
        task_dict.pop('last_run_status', None)
        task_dict.pop('is_pinned', None)
        task_dict.pop('pid', None)
        task_dict.pop('log_path', None)
        task_dict.pop('last_running_time', None)
        tasks_data.append(task_dict)

    return jsonify({"data": tasks_data})


@tasks_bp.route("/import", methods=["POST"])
@jwt_required()
def import_tasks():
    """导入任务"""
    data = request.get_json(silent=True) or {}
    tasks_data = data.get("tasks", [])

    if not isinstance(tasks_data, list):
        return jsonify({"error": "任务数据格式错误"}), 400

    imported_count = 0
    errors = []

    for task_data in tasks_data:
        try:
            # 验证必需字段
            if not task_data.get("name") or not task_data.get("command") or not task_data.get("cron_expression"):
                errors.append(f"任务 {task_data.get('name', '未命名')} 缺少必需字段")
                continue

            # 检查命令格式
            try:
                scripts_dir = current_app.config.get("SCRIPTS_DIR", os.path.abspath("./data/scripts"))
                validate_command(task_data["command"], scripts_dir)
            except CommandValidationError:
                errors.append(f"任务 {task_data['name']} 命令格式错误")
                continue

            # 检查 Cron 表达式
            if not _validate_cron(task_data["cron_expression"]):
                errors.append(f"任务 {task_data['name']} Cron 表达式无效")
                continue

            # 创建任务
            labels = task_data.get("labels", [])
            if isinstance(labels, list):
                labels = ",".join(labels)

            task = Task(
                name=task_data["name"],
                command=task_data["command"],
                cron_expression=task_data["cron_expression"],
                status=task_data.get("status", Task.STATUS_DISABLED),  # 默认禁用
                timeout=task_data.get("timeout", 300),
                max_retries=task_data.get("max_retries", 0),
                retry_interval=task_data.get("retry_interval", 60),
                notify_on_failure=task_data.get("notify_on_failure", True),
                depends_on=task_data.get("depends_on"),
                labels=labels,
            )
            db.session.add(task)
            imported_count += 1

        except Exception as e:
            errors.append(f"任务 {task_data.get('name', '未命名')} 导入失败: {str(e)}")

    try:
        db.session.commit()
        result = {"message": f"成功导入 {imported_count} 个任务"}
        if errors:
            result["errors"] = errors
        return jsonify(result), 201 if imported_count > 0 else 400
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"导入失败: {str(e)}"}), 500


def _validate_cron(expression: str) -> bool:
    """校验 Cron 表达式格式（支持 5 位和 6 位）"""
    from app.utils.cron_parser import validate_cron_expression

    valid, _ = validate_cron_expression(expression)
    return valid


# ==================== Cron 表达式辅助工具 ====================

@tasks_bp.route("/cron/parse", methods=["POST"])
@jwt_required()
def parse_cron():
    """解析 Cron 表达式，返回描述和下次执行时间

    请求体:
        expression: Cron 表达式

    响应:
        description: 人类可读描述
        next_run_times: 未来 5 次执行时间
        is_valid: 是否有效
        format: 格式（5位/6位）
    """
    data = request.get_json(silent=True) or {}
    expression = safe_strip(data.get("expression"))

    if not expression:
        return jsonify({"error": "表达式不能为空"}), 400

    from app.utils.cron_parser import CronParser
    from apscheduler.triggers.cron import CronTrigger
    from datetime import datetime

    # 验证表达式
    valid, error, result = CronParser.parse(expression)
    if not valid:
        return jsonify({
            "is_valid": False,
            "error": error
        })

    # 获取描述
    description = CronParser.get_description(expression)

    # 计算下次执行时间
    try:
        trigger_kwargs = CronParser.to_apscheduler_trigger(expression)
        if not trigger_kwargs:
            return jsonify({
                "is_valid": False,
                "error": "无法转换为调度器参数"
            })

        trigger = CronTrigger(**trigger_kwargs)

        now = datetime.now()
        next_times = []
        current = now

        for _ in range(5):
            next_time = trigger.get_next_fire_time(None, current)
            if next_time:
                next_times.append(next_time.isoformat())
                current = next_time
            else:
                break

        return jsonify({
            "is_valid": True,
            "description": description,
            "next_run_times": next_times,
            "format": "6位（秒 分 时 日 月 周）" if result['has_second'] else "5位（分 时 日 月 周）"
        })
    except Exception as e:
        return jsonify({
            "is_valid": False,
            "error": f"计算执行时间失败: {str(e)}"
        })


@tasks_bp.route("/cron/templates", methods=["GET"])
@jwt_required()
def cron_templates():
    """获取常用 Cron 表达式模板"""
    templates = [
        {"name": "每分钟", "expression": "* * * * *", "description": "每分钟执行一次", "category": "高频"},
        {"name": "每5分钟", "expression": "*/5 * * * *", "description": "每5分钟执行一次", "category": "高频"},
        {"name": "每10分钟", "expression": "*/10 * * * *", "description": "每10分钟执行一次", "category": "高频"},
        {"name": "每30分钟", "expression": "*/30 * * * *", "description": "每30分钟执行一次", "category": "高频"},
        {"name": "每小时", "expression": "0 * * * *", "description": "每小时执行一次", "category": "常用"},
        {"name": "每天凌晨", "expression": "0 0 * * *", "description": "每天 00:00 执行", "category": "每天"},
        {"name": "每天早上6点", "expression": "0 6 * * *", "description": "每天 06:00 执行", "category": "每天"},
        {"name": "每天早上9点", "expression": "0 9 * * *", "description": "每天 09:00 执行", "category": "每天"},
        {"name": "每天中午12点", "expression": "0 12 * * *", "description": "每天 12:00 执行", "category": "每天"},
        {"name": "每天下午6点", "expression": "0 18 * * *", "description": "每天 18:00 执行", "category": "每天"},
        {"name": "每天晚上11点", "expression": "0 23 * * *", "description": "每天 23:00 执行", "category": "每天"},
        {"name": "工作日早上9点", "expression": "0 9 * * 1-5", "description": "周一到周五 09:00 执行", "category": "工作日"},
        {"name": "工作日晚上6点", "expression": "0 18 * * 1-5", "description": "周一到周五 18:00 执行", "category": "工作日"},
        {"name": "周末早上10点", "expression": "0 10 * * 0,6", "description": "周六和周日 10:00 执行", "category": "周末"},
        {"name": "每周一早上9点", "expression": "0 9 * * 1", "description": "每周一 09:00 执行", "category": "每周"},
        {"name": "每周五晚上6点", "expression": "0 18 * * 5", "description": "每周五 18:00 执行", "category": "每周"},
        {"name": "每月1号凌晨", "expression": "0 0 1 * *", "description": "每月1号 00:00 执行", "category": "每月"},
        {"name": "每月15号中午", "expression": "0 12 15 * *", "description": "每月15号 12:00 执行", "category": "每月"},
        {"name": "每30秒（6位）", "expression": "*/30 * * * * *", "description": "每30秒执行一次", "category": "秒级"},
        {"name": "每天9点整（6位）", "expression": "0 0 9 * * *", "description": "每天 09:00:00 执行", "category": "秒级"},
    ]

    return jsonify({"data": templates})


# ==================== 批量操作 ====================

@tasks_bp.route("/batch/enable", methods=["PUT"])
@jwt_required()
def batch_enable():
    """批量启用任务"""
    data = request.get_json(silent=True) or {}
    task_ids = data.get("task_ids", [])

    if not task_ids:
        return jsonify({"error": "任务ID列表不能为空"}), 400

    tasks = Task.query.filter(Task.id.in_(task_ids)).all()
    from app.services.scheduler import add_job

    success_count = 0
    for task in tasks:
        if task.status != Task.STATUS_ENABLED:
            task.status = Task.STATUS_ENABLED
            add_job(task)
            success_count += 1

    db.session.commit()
    return jsonify({"message": f"成功启用 {success_count} 个任务", "success_count": success_count})


@tasks_bp.route("/batch/disable", methods=["PUT"])
@jwt_required()
def batch_disable():
    """批量禁用任务"""
    data = request.get_json(silent=True) or {}
    task_ids = data.get("task_ids", [])

    if not task_ids:
        return jsonify({"error": "任务ID列表不能为空"}), 400

    tasks = Task.query.filter(Task.id.in_(task_ids)).all()
    from app.services.scheduler import remove_job

    success_count = 0
    for task in tasks:
        if task.status != Task.STATUS_DISABLED:
            task.status = Task.STATUS_DISABLED
            remove_job(task.id)
            success_count += 1

    db.session.commit()
    return jsonify({"message": f"成功禁用 {success_count} 个任务", "success_count": success_count})


@tasks_bp.route("/batch/delete", methods=["DELETE"])
@jwt_required()
def batch_delete():
    """批量删除任务"""
    data = request.get_json(silent=True) or {}
    task_ids = data.get("task_ids", [])

    if not task_ids:
        return jsonify({"error": "任务ID列表不能为空"}), 400

    from app.services.scheduler import remove_job
    tasks = Task.query.filter(Task.id.in_(task_ids)).all()

    for task in tasks:
        remove_job(task.id)
        db.session.delete(task)

    db.session.commit()
    return jsonify({"message": f"成功删除 {len(tasks)} 个任务", "count": len(tasks)})


@tasks_bp.route("/batch/run", methods=["POST"])
@jwt_required()
def batch_run():
    """批量运行任务"""
    data = request.get_json(silent=True) or {}
    task_ids = data.get("task_ids", [])

    if not task_ids:
        return jsonify({"error": "任务ID列表不能为空"}), 400
    if len(task_ids) > 10:
        return jsonify({"error": "单次最多运行 10 个任务"}), 400

    tasks = Task.query.filter(Task.id.in_(task_ids)).all()
    from app.services.scheduler import run_task_now

    for task in tasks:
        run_task_now(task)

    return jsonify({"message": f"成功启动 {len(tasks)} 个任务", "count": len(tasks)})


# ==================== 任务统计 ====================

@tasks_bp.route("/<int:task_id>/stats", methods=["GET"])
@jwt_required()
def task_stats(task_id: int):
    """获取任务执行统计"""
    task = Task.query.get(task_id)
    if not task:
        return jsonify({"error": "任务不存在"}), 404

    days = request.args.get("days", 7, type=int)

    from datetime import datetime, timedelta
    from app.models.log import TaskLog
    from sqlalchemy import func

    start_date = datetime.utcnow() - timedelta(days=days)

    total_runs = TaskLog.query.filter(
        TaskLog.task_id == task_id,
        TaskLog.started_at >= start_date
    ).count()

    success_runs = TaskLog.query.filter(
        TaskLog.task_id == task_id,
        TaskLog.started_at >= start_date,
        TaskLog.status == TaskLog.STATUS_SUCCESS
    ).count()

    failed_runs = TaskLog.query.filter(
        TaskLog.task_id == task_id,
        TaskLog.started_at >= start_date,
        TaskLog.status == TaskLog.STATUS_FAILED
    ).count()

    avg_duration = db.session.query(func.avg(TaskLog.duration)).filter(
        TaskLog.task_id == task_id,
        TaskLog.started_at >= start_date,
        TaskLog.duration.isnot(None)
    ).scalar() or 0

    max_duration = db.session.query(func.max(TaskLog.duration)).filter(
        TaskLog.task_id == task_id,
        TaskLog.started_at >= start_date,
        TaskLog.duration.isnot(None)
    ).scalar() or 0

    min_duration = db.session.query(func.min(TaskLog.duration)).filter(
        TaskLog.task_id == task_id,
        TaskLog.started_at >= start_date,
        TaskLog.duration.isnot(None)
    ).scalar() or 0

    recent_logs = TaskLog.query.filter(
        TaskLog.task_id == task_id
    ).order_by(TaskLog.started_at.desc()).limit(10).all()

    return jsonify({
        "task_id": task_id,
        "task_name": task.name,
        "period_days": days,
        "stats": {
            "total_runs": total_runs,
            "success_runs": success_runs,
            "failed_runs": failed_runs,
            "success_rate": round(success_runs / total_runs * 100, 2) if total_runs > 0 else 0,
            "avg_duration": round(avg_duration, 2),
            "max_duration": round(max_duration, 2),
            "min_duration": round(min_duration, 2),
        },
        "recent_logs": [
            {
                "id": log.id,
                "started_at": log.started_at.isoformat() if log.started_at else None,
                "ended_at": log.ended_at.isoformat() if log.ended_at else None,
                "status": log.status,
                "duration": log.duration,
            }
            for log in recent_logs
        ]
    })

