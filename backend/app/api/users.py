"""用户管理接口（仅管理员可用）"""

import logging
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required

from app.extensions import db
from app.models.user import User
from app.utils.permissions import require_admin
from app.utils.validators import safe_strip

logger = logging.getLogger(__name__)
users_bp = Blueprint("users", __name__)


@users_bp.route("", methods=["GET"])
@jwt_required()
@require_admin
def list_users():
    """获取用户列表"""
    users = User.query.order_by(User.created_at.desc()).all()
    return jsonify({"data": [u.to_dict() for u in users]})


@users_bp.route("", methods=["POST"])
@jwt_required()
@require_admin
def create_user():
    """创建用户

    请求体:
        username: 用户名
        password: 密码
        role: 角色（admin / operator / viewer）
    """
    try:
        data = request.get_json(silent=True) or {}
        username = safe_strip(data.get("username"))
        password = safe_strip(data.get("password"))
        role = safe_strip(data.get("role", User.ROLE_VIEWER))

        if not username or not password:
            return jsonify({"error": "用户名和密码不能为空"}), 400
        if len(username) < 3:
            return jsonify({"error": "用户名至少 3 个字符"}), 400
        if len(password) < 8:
            return jsonify({"error": "密码至少 8 个字符"}), 400
        if role not in User.VALID_ROLES:
            return jsonify({"error": f"角色必须是: {', '.join(User.VALID_ROLES)}"}), 400

        if User.query.filter_by(username=username).first():
            return jsonify({"error": "用户名已存在"}), 409

        user = User(username=username, role=role)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        return jsonify({"message": "创建成功", "data": user.to_dict()}), 201
    except Exception as e:
        db.session.rollback()
        logger.error(f"创建用户失败: {e}", exc_info=True)
        return jsonify({"error": f"创建失败: {str(e)}"}), 500


@users_bp.route("/<int:user_id>", methods=["PUT"])
@jwt_required()
@require_admin
def update_user(user_id: int):
    """更新用户信息（管理员不能修改自己的角色）"""
    try:
        from app.utils.permissions import get_current_user
        user = User.query.get(user_id)
        if not user:
            return jsonify({"error": "用户不存在"}), 404

        current = get_current_user()
        data = request.get_json(silent=True) or {}

        if "username" in data:
            new_name = safe_strip(data["username"])
            if len(new_name) < 3:
                return jsonify({"error": "用户名至少 3 个字符"}), 400
            existing = User.query.filter_by(username=new_name).first()
            if existing and existing.id != user_id:
                return jsonify({"error": "用户名已存在"}), 409
            user.username = new_name

        if "role" in data:
            role = safe_strip(data["role"])
            if role not in User.VALID_ROLES:
                return jsonify({"error": f"角色必须是: {', '.join(User.VALID_ROLES)}"}), 400
            if current and current.id == user_id:
                return jsonify({"error": "不能修改自己的角色"}), 400
            user.role = role

        if "enabled" in data:
            if current and current.id == user_id:
                return jsonify({"error": "不能禁用自己"}), 400
            user.enabled = data["enabled"]

        if "password" in data:
            pw = safe_strip(data["password"])
            if len(pw) < 8:
                return jsonify({"error": "密码至少 8 个字符"}), 400
            user.set_password(pw)

        db.session.commit()
        return jsonify({"message": "更新成功", "data": user.to_dict()})
    except Exception as e:
        db.session.rollback()
        logger.error(f"更新用户失败: {e}", exc_info=True)
        return jsonify({"error": f"更新失败: {str(e)}"}), 500


@users_bp.route("/<int:user_id>", methods=["DELETE"])
@jwt_required()
@require_admin
def delete_user(user_id: int):
    """删除用户（不能删除自己）"""
    try:
        from app.utils.permissions import get_current_user
        current = get_current_user()
        if current and current.id == user_id:
            return jsonify({"error": "不能删除自己"}), 400

        user = User.query.get(user_id)
        if not user:
            return jsonify({"error": "用户不存在"}), 404

        db.session.delete(user)
        db.session.commit()
        return jsonify({"message": "删除成功"})
    except Exception as e:
        db.session.rollback()
        logger.error(f"删除用户失败: {e}", exc_info=True)
        return jsonify({"error": f"删除失败: {str(e)}"}), 500
