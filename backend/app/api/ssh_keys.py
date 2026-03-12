"""SSH 密钥管理接口"""

import logging
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required

from app.extensions import db
from app.models.subscription import SSHKey
from app.services.git_service import generate_ssh_key_pair
from app.utils.crypto import encrypt_data, decrypt_data
from app.utils.validators import safe_strip, safe_str

logger = logging.getLogger(__name__)
ssh_keys_bp = Blueprint("ssh_keys", __name__)


@ssh_keys_bp.route("", methods=["GET"])
@jwt_required()
def list_ssh_keys():
    """获取 SSH 密钥列表（不包含私钥）"""
    keys = SSHKey.query.all()
    return jsonify({
        "data": [key.to_dict(include_private=False) for key in keys]
    })


@ssh_keys_bp.route("", methods=["POST"])
@jwt_required()
def create_ssh_key():
    """创建 SSH 密钥

    请求体:
        name: 密钥名称
        remarks: 备注（可选）
        auto_generate: 是否自动生成（默认 true）
        private_key: 私钥内容（auto_generate=false 时必填）
        public_key: 公钥内容（auto_generate=false 时必填）
    """
    try:
        data = request.get_json(silent=True) or {}
        name = safe_strip(data.get("name"))
        remarks = safe_str(data.get("remarks"))
        auto_generate = data.get("auto_generate", True)

        if not name:
            return jsonify({"error": "密钥名称不能为空"}), 400

        # 检查名称是否重复
        existing = SSHKey.query.filter_by(name=name).first()
        if existing:
            return jsonify({"error": "密钥名称已存在"}), 400

        if auto_generate:
            # 自动生成密钥对
            private_key, public_key = generate_ssh_key_pair()
        else:
            # 使用用户提供的密钥
            private_key = safe_strip(data.get("private_key"))
            public_key = safe_strip(data.get("public_key"))

            if not private_key or not public_key:
                return jsonify({"error": "请提供私钥和公钥"}), 400

        # 加密存储私钥
        encrypted_private_key = encrypt_data(private_key)

        # 创建密钥记录
        ssh_key = SSHKey(
            name=name,
            private_key=encrypted_private_key,
            public_key=public_key,
            remarks=remarks,
        )
        db.session.add(ssh_key)
        db.session.commit()

        return jsonify({
            "message": "创建成功",
            "data": ssh_key.to_dict(include_private=False)
        }), 201

    except Exception as e:
        db.session.rollback()
        logger.error(f"创建 SSH 密钥失败: {e}", exc_info=True)
        return jsonify({"error": f"创建失败: {str(e)}"}), 500


@ssh_keys_bp.route("/<int:key_id>", methods=["GET"])
@jwt_required()
def get_ssh_key(key_id: int):
    """获取 SSH 密钥详情（包含私钥）"""
    ssh_key = SSHKey.query.get(key_id)
    if not ssh_key:
        return jsonify({"error": "SSH 密钥不存在"}), 404

    # 解密私钥
    try:
        decrypted_private_key = decrypt_data(ssh_key.private_key)
        result = ssh_key.to_dict(include_private=True)
        result["private_key"] = decrypted_private_key
        return jsonify({"data": result})
    except Exception as e:
        return jsonify({"error": f"解密失败: {str(e)}"}), 500


@ssh_keys_bp.route("/<int:key_id>", methods=["PUT"])
@jwt_required()
def update_ssh_key(key_id: int):
    """更新 SSH 密钥

    请求体:
        name: 密钥名称（可选）
        remarks: 备注（可选）
    """
    try:
        ssh_key = SSHKey.query.get(key_id)
        if not ssh_key:
            return jsonify({"error": "SSH 密钥不存在"}), 404

        data = request.get_json(silent=True) or {}

        if "name" in data:
            name = safe_strip(data["name"])
            if not name:
                return jsonify({"error": "密钥名称不能为空"}), 400

            # 检查名称是否重复
            existing = SSHKey.query.filter(
                SSHKey.name == name,
                SSHKey.id != key_id
            ).first()
            if existing:
                return jsonify({"error": "密钥名称已存在"}), 400

            ssh_key.name = name

        if "remarks" in data:
            ssh_key.remarks = safe_str(data["remarks"])

        db.session.commit()
        return jsonify({
            "message": "更新成功",
            "data": ssh_key.to_dict(include_private=False)
        })
    except Exception as e:
        db.session.rollback()
        logger.error(f"更新 SSH 密钥失败: {e}", exc_info=True)
        return jsonify({"error": f"更新失败: {str(e)}"}), 500


@ssh_keys_bp.route("/<int:key_id>", methods=["DELETE"])
@jwt_required()
def delete_ssh_key(key_id: int):
    """删除 SSH 密钥"""
    try:
        ssh_key = SSHKey.query.get(key_id)
        if not ssh_key:
            return jsonify({"error": "SSH 密钥不存在"}), 404

        db.session.delete(ssh_key)
        db.session.commit()
        return jsonify({"message": "删除成功"})
    except Exception as e:
        db.session.rollback()
        logger.error(f"删除 SSH 密钥失败: {e}", exc_info=True)
        return jsonify({"error": f"删除失败: {str(e)}"}), 500
    if not ssh_key:
        return jsonify({"error": "SSH 密钥不存在"}), 404

    # 检查是否被订阅使用
    from app.models.subscription import Subscription
    using_subs = Subscription.query.filter_by(ssh_key_id=key_id).count()
    if using_subs > 0:
        return jsonify({
            "error": f"该密钥正被 {using_subs} 个订阅使用，无法删除"
        }), 400

    db.session.delete(ssh_key)
    db.session.commit()
    return jsonify({"message": "删除成功"})
