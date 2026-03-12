"""通知渠道管理接口"""

import json
import logging

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required

from app.extensions import db
from app.models.notification import NotifyChannel
from app.utils.validators import safe_strip

logger = logging.getLogger(__name__)
notify_bp = Blueprint("notifications", __name__)

VALID_TYPES = {
    "webhook", "email", "telegram",
    "dingtalk", "wecom", "bark",
    "pushplus", "serverchan", "feishu"
}


@notify_bp.route("", methods=["GET"])
@jwt_required()
def list_channels():
    """获取通知渠道列表"""
    channels = NotifyChannel.query.order_by(NotifyChannel.created_at.desc()).all()
    return jsonify({"data": [c.to_dict() for c in channels]})


@notify_bp.route("", methods=["POST"])
@jwt_required()
def create_channel():
    """创建通知渠道

    请求体:
        name: 渠道名称
        type: 类型（webhook / email / telegram）
        config: 配置对象
    """
    try:
        data = request.get_json(silent=True) or {}
        name = safe_strip(data.get("name"))
        ch_type = safe_strip(data.get("type"))
        config = data.get("config", {})

        if not name:
            return jsonify({"error": "名称不能为空"}), 400
        if ch_type not in VALID_TYPES:
            return jsonify({"error": f"类型必须是: {', '.join(VALID_TYPES)}"}), 400

        err = _validate_config(ch_type, config)
        if err:
            return jsonify({"error": err}), 400

        channel = NotifyChannel(
            name=name,
            type=ch_type,
            config=json.dumps(config, ensure_ascii=False),
        )
        db.session.add(channel)
        db.session.commit()

        return jsonify({"message": "创建成功", "data": channel.to_dict()}), 201
    except Exception as e:
        db.session.rollback()
        logger.error(f"创建通知渠道失败: {e}", exc_info=True)
        return jsonify({"error": f"创建失败: {str(e)}"}), 500


@notify_bp.route("/<int:ch_id>", methods=["PUT"])
@jwt_required()
def update_channel(ch_id: int):
    """更新通知渠道"""
    try:
        channel = NotifyChannel.query.get(ch_id)
        if not channel:
            return jsonify({"error": "渠道不存在"}), 404

        data = request.get_json(silent=True) or {}
        if "name" in data:
            channel.name = safe_strip(data["name"])
        if "type" in data:
            ch_type = safe_strip(data["type"])
            if ch_type not in VALID_TYPES:
                return jsonify({"error": f"类型必须是: {', '.join(VALID_TYPES)}"}), 400
            channel.type = ch_type
        if "config" in data:
            err = _validate_config(channel.type, data["config"])
            if err:
                return jsonify({"error": err}), 400
            channel.config = json.dumps(data["config"], ensure_ascii=False)
        if "enabled" in data:
            channel.enabled = data["enabled"]

        db.session.commit()
        return jsonify({"message": "更新成功", "data": channel.to_dict()})
    except Exception as e:
        db.session.rollback()
        logger.error(f"更新通知渠道失败: {e}", exc_info=True)
        return jsonify({"error": f"更新失败: {str(e)}"}), 500


@notify_bp.route("/<int:ch_id>", methods=["DELETE"])
@jwt_required()
def delete_channel(ch_id: int):
    """删除通知渠道"""
    try:
        channel = NotifyChannel.query.get(ch_id)
        if not channel:
            return jsonify({"error": "渠道不存在"}), 404

        db.session.delete(channel)
        db.session.commit()
        return jsonify({"message": "删除成功"})
    except Exception as e:
        db.session.rollback()
        logger.error(f"删除通知渠道失败: {e}", exc_info=True)
        return jsonify({"error": f"删除失败: {str(e)}"}), 500


@notify_bp.route("/<int:ch_id>/test", methods=["POST"])
@jwt_required()
def test_channel(ch_id: int):
    """测试通知渠道"""
    channel = NotifyChannel.query.get(ch_id)
    if not channel:
        return jsonify({"error": "渠道不存在"}), 404

    from app.services.notifier import send_notification
    success, msg = send_notification(
        channel,
        title="呆呆面板 - 测试通知",
        content="这是一条测试通知，如果您收到说明配置正确。",
    )

    if success:
        return jsonify({"message": "测试通知发送成功"})
    return jsonify({"error": f"发送失败: {msg}"}), 500


def _validate_config(ch_type: str, config: dict) -> str | None:
    """校验通知渠道配置"""
    if ch_type == "webhook":
        if not config.get("url"):
            return "WebHook 配置缺少 url"
    elif ch_type == "email":
        for key in ("smtp_host", "smtp_port", "username", "password", "to"):
            if not config.get(key):
                return f"邮件配置缺少 {key}"
    elif ch_type == "telegram":
        if not config.get("bot_token") or not config.get("chat_id"):
            return "Telegram 配置缺少 bot_token 或 chat_id"
    elif ch_type == "dingtalk":
        if not config.get("token"):
            return "钉钉配置缺少 token"
    elif ch_type == "wecom":
        if not config.get("key"):
            return "企业微信配置缺少 key"
    elif ch_type == "bark":
        if not config.get("device_key"):
            return "Bark 配置缺少 device_key"
    elif ch_type == "pushplus":
        if not config.get("token"):
            return "PushPlus 配置缺少 token"
    elif ch_type == "serverchan":
        if not config.get("send_key"):
            return "Server酱 配置缺少 send_key"
    elif ch_type == "feishu":
        if not config.get("webhook"):
            return "飞书配置缺少 webhook"
    return None
