"""系统配置接口"""

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required

from app.extensions import db
from app.models.system_config import SystemConfig, DEFAULT_CONFIGS
from app.utils.permissions import require_admin

config_bp = Blueprint("config", __name__)


@config_bp.route("", methods=["GET"])
@jwt_required()
def get_all_configs():
    """获取全部系统配置"""
    configs = SystemConfig.query.all()
    existing_keys = {c.key for c in configs}
    result = {c.key: c.to_dict() for c in configs}

    # 补充未入库的默认配置
    for key, default_val in DEFAULT_CONFIGS.items():
        if key not in existing_keys:
            result[key] = {
                "key": key,
                "value": default_val,
                "description": "",
                "updated_at": None,
            }

    return jsonify({"data": result})


@config_bp.route("", methods=["PUT"])
@jwt_required()
@require_admin
def update_configs():
    """批量更新配置

    请求体: { "configs": { "key1": "value1", "key2": "value2", ... } }
    """
    data = request.get_json(silent=True) or {}
    configs = data.get("configs", {})

    if not isinstance(configs, dict):
        return jsonify({"error": "configs 必须是对象"}), 400

    for key, value in configs.items():
        if key not in DEFAULT_CONFIGS:
            continue  # 跳过未知配置项
        SystemConfig.set(key, str(value))

    db.session.commit()
    return jsonify({"message": "配置已保存"})


@config_bp.route("/<key>", methods=["GET"])
@jwt_required()
def get_config(key: str):
    """获取单项配置"""
    value = SystemConfig.get(key)
    return jsonify({"key": key, "value": value})
