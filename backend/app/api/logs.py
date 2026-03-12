"""日志接口"""

import os
import time
import logging

from flask import Blueprint, request, jsonify, Response, stream_with_context, current_app
from flask_jwt_extended import jwt_required, verify_jwt_in_request

from app.extensions import db
from app.models.log import TaskLog
from app.utils.validators import safe_strip, safe_int

logger = logging.getLogger(__name__)
logs_bp = Blueprint("logs", __name__)


def _log_to_dict_with_file_content(log: TaskLog) -> dict:
    """序列化日志，当 content 为空时从日志文件读取内容"""
    data = log.to_dict()
    if not data.get("content") and data.get("log_path"):
        log_dir = current_app.config.get("LOG_DIR", "")
        if not log_dir:
            logger.warning(f"LOG_DIR 未配置，无法读取日志文件")
            return data
        file_path = os.path.join(log_dir, data["log_path"])
        try:
            if os.path.isfile(file_path):
                with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                    data["content"] = f.read()
            else:
                logger.debug(f"日志文件不存在: {file_path}")
        except Exception as e:
            logger.error(f"读取日志文件失败: {file_path}, 错误: {e}")
    return data


@logs_bp.route("", methods=["GET"])
@jwt_required()
def list_logs():
    """获取日志列表

    查询参数:
        task_id: 按任务过滤
        status: 按状态过滤 (0=成功, 1=失败)
        keyword: 按日志内容关键字搜索
        page: 页码（默认 1）
        page_size: 每页数量（默认 20）
    """
    task_id = safe_int(request.args.get("task_id"), default=None)
    status = safe_int(request.args.get("status"), default=None)
    keyword = safe_strip(request.args.get("keyword", ""))
    page = safe_int(request.args.get("page"), default=1)
    page_size = safe_int(request.args.get("page_size"), default=20)

    query = TaskLog.query

    if task_id is not None:
        query = query.filter_by(task_id=task_id)
    if status is not None:
        query = query.filter_by(status=status)
    if keyword:
        query = query.filter(TaskLog.content.ilike(f"%{keyword}%"))

    query = query.order_by(TaskLog.started_at.desc())
    pagination = query.paginate(page=page, per_page=page_size, error_out=False)

    return jsonify({
        "data": [log.to_dict() for log in pagination.items],
        "total": pagination.total,
        "page": page,
        "page_size": page_size,
    })


@logs_bp.route("/<int:task_id>/stream", methods=["GET"])
def stream_log(task_id: int):
    """SSE 实时日志流

    通过 Server-Sent Events 推送正在运行的任务日志。
    URL 参数 token 用于认证（因为 EventSource 不支持 Header）。
    """
    # SSE 不能用 Header 传 JWT，改用 query 参数
    token = request.args.get("token", "")
    if not token:
        return jsonify({"error": "缺少认证 token"}), 401

    # 手动验证 JWT
    try:
        from flask_jwt_extended import decode_token
        decode_token(token)
    except Exception:
        return jsonify({"error": "无效的 token"}), 401

    from app.services.scheduler import get_live_log

    def generate():
        cursor = 0
        idle_count = 0  # 无新数据的轮次计数
        max_idle = 120  # 最多等待 60 秒 (120 * 0.5s)，防止日志清理后无限循环
        while True:
            lines, done = get_live_log(task_id)

            # 逐行发送，每行一个 SSE 事件（避免多行拼接被 SSE 协议截断）
            if cursor < len(lines):
                for line in lines[cursor:]:
                    # SSE data 字段不能包含裸换行，需要每行用 "data: " 前缀
                    safe_line = line.rstrip("\n")
                    yield f"data: {safe_line}\n\n"
                cursor = len(lines)
                idle_count = 0  # 有新数据，重置计数

            if done:
                yield "event: done\ndata: finished\n\n"
                break

            idle_count += 1
            if idle_count >= max_idle:
                # 超时：任务可能已完成且日志缓冲已被清理
                yield "event: done\ndata: finished\n\n"
                break

            time.sleep(0.5)

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@logs_bp.route("/<int:log_id>", methods=["GET"])
@jwt_required()
def get_log(log_id: int):
    """获取日志详情"""
    log = TaskLog.query.get(log_id)
    if not log:
        return jsonify({"error": "日志不存在"}), 404
    return jsonify({"data": _log_to_dict_with_file_content(log)})


@logs_bp.route("/<int:log_id>", methods=["DELETE"])
@jwt_required()
def delete_log(log_id: int):
    """删除日志"""
    log = TaskLog.query.get(log_id)
    if not log:
        return jsonify({"error": "日志不存在"}), 404

    db.session.delete(log)
    db.session.commit()
    return jsonify({"message": "日志删除成功"})


@logs_bp.route("/clean", methods=["DELETE"])
@jwt_required()
def clean_logs():
    """清理过期日志

    查询参数:
        days: 保留天数（默认 7）
    """
    from datetime import datetime, timedelta

    days = request.args.get("days", 7, type=int)
    cutoff = datetime.utcnow() - timedelta(days=days)

    count = TaskLog.query.filter(TaskLog.started_at < cutoff).delete()
    db.session.commit()

    return jsonify({"message": f"已清理 {count} 条过期日志"})
