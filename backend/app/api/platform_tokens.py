"""平台 Token 管理接口（参考青龙面板）"""

import json
import logging
from datetime import datetime, timedelta

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

from app.extensions import db, limiter
from app.models.platform_token import Platform, PlatformToken, PlatformTokenLog
from app.models.user import User
from app.utils.validators import safe_strip, safe_str, safe_int

logger = logging.getLogger(__name__)
platform_token_bp = Blueprint("platform_token", __name__)

VALID_SCOPES = ["tasks", "scripts", "envs", "logs", "system", "subscriptions", "notifications"]


# ==================== 平台管理 ====================

@platform_token_bp.route("/platforms", methods=["GET"])
@jwt_required()
def list_platforms():
    """获取平台列表"""
    platforms = Platform.query.order_by(Platform.created_at.desc()).all()
    return jsonify({"data": [p.to_dict() for p in platforms]})


@platform_token_bp.route("/platforms", methods=["POST"])
@jwt_required()
def create_platform():
    """创建平台

    请求体:
        name: 平台名称
        description: 平台描述（可选）
        max_tokens: 最大 Token 数（可选，默认 5）
    """
    try:
        # 验证管理员权限
        current_username = get_jwt_identity()
        user = User.query.filter_by(username=current_username).first()
        if not user or user.role != 'admin':
            return jsonify({"error": "需要管理员权限"}), 403

        data = request.get_json(silent=True) or {}
        name = safe_strip(data.get("name"))
        if not name:
            return jsonify({"error": "平台名称不能为空"}), 400

        # 检查名称是否重复
        existing = Platform.query.filter_by(name=name).first()
        if existing:
            return jsonify({"error": "平台名称已存在"}), 400

        platform = Platform(
            name=name,
            description=safe_str(data.get("description")),
            max_tokens=safe_int(data.get("max_tokens"), default=5),
        )
        db.session.add(platform)
        db.session.commit()

        return jsonify({"message": "平台创建成功", "data": platform.to_dict()}), 201
    except Exception as e:
        db.session.rollback()
        logger.error(f"创建平台失败: {e}", exc_info=True)
        return jsonify({"error": f"创建失败: {str(e)}"}), 500


@platform_token_bp.route("/platforms/<int:platform_id>", methods=["PUT"])
@jwt_required()
def update_platform(platform_id: int):
    """更新平台"""
    try:
        # 验证管理员权限
        current_username = get_jwt_identity()
        user = User.query.filter_by(username=current_username).first()
        if not user or user.role != 'admin':
            return jsonify({"error": "需要管理员权限"}), 403

        platform = Platform.query.get(platform_id)
        if not platform:
            return jsonify({"error": "平台不存在"}), 404

        data = request.get_json(silent=True) or {}

        if "name" in data:
            name = safe_strip(data["name"])
            if not name:
                return jsonify({"error": "平台名称不能为空"}), 400
            # 检查名称是否重复
            existing = Platform.query.filter(
                Platform.name == name,
                Platform.id != platform_id
            ).first()
            if existing:
                return jsonify({"error": "平台名称已存在"}), 400
            platform.name = name

        if "description" in data:
            platform.description = safe_str(data["description"])
        if "max_tokens" in data:
            platform.max_tokens = safe_int(data["max_tokens"], default=5)
        if "enabled" in data:
            platform.enabled = data["enabled"]

        db.session.commit()
        return jsonify({"message": "更新成功", "data": platform.to_dict()})
    except Exception as e:
        db.session.rollback()
        logger.error(f"更新平台失败: {e}", exc_info=True)
        return jsonify({"error": f"更新失败: {str(e)}"}), 500


@platform_token_bp.route("/platforms/<int:platform_id>", methods=["DELETE"])
@jwt_required()
def delete_platform(platform_id: int):
    """删除平台（会同时删除所有关联的 Token）"""
    # 验证管理员权限
    current_username = get_jwt_identity()
    user = User.query.filter_by(username=current_username).first()
    if not user or user.role != 'admin':
        return jsonify({"error": "需要管理员权限"}), 403

    platform = Platform.query.get(platform_id)
    if not platform:
        return jsonify({"error": "平台不存在"}), 404

    token_count = platform.tokens.count()
    db.session.delete(platform)
    db.session.commit()

    return jsonify({
        "message": f"平台删除成功，同时删除了 {token_count} 个 Token"
    })


# ==================== Token 管理 ====================

@platform_token_bp.route("/platforms/<int:platform_id>/tokens", methods=["GET"])
@jwt_required()
def list_tokens(platform_id: int):
    """获取平台的 Token 列表"""
    platform = Platform.query.get(platform_id)
    if not platform:
        return jsonify({"error": "平台不存在"}), 404

    tokens = PlatformToken.query.filter_by(platform_id=platform_id)\
        .order_by(PlatformToken.created_at.desc()).all()

    return jsonify({"data": [t.to_dict() for t in tokens]})


@platform_token_bp.route("/platforms/<int:platform_id>/tokens", methods=["POST"])
@jwt_required()
def create_token(platform_id: int):
    """创建 Token

    请求体:
        name: Token 名称
        scopes: 权限范围列表（可选）
        expires_in_days: 有效天数（可选，0 表示永不过期）
        remarks: 备注（可选）
    """
    try:
        platform = Platform.query.get(platform_id)
        if not platform:
            return jsonify({"error": "平台不存在"}), 404

        if not platform.enabled:
            return jsonify({"error": "平台已禁用"}), 403

        # 检查 Token 数量限制
        active_tokens = platform.tokens.filter_by(enabled=True).count()
        if active_tokens >= platform.max_tokens:
            return jsonify({
                "error": f"该平台最多允许 {platform.max_tokens} 个活跃 Token，请先禁用或删除旧 Token"
            }), 400

        data = request.get_json(silent=True) or {}
        name = safe_strip(data.get("name"))
        if not name:
            return jsonify({"error": "Token 名称不能为空"}), 400

        # 验证权限范围
        scopes = data.get("scopes", [])
        for s in scopes:
            if s not in VALID_SCOPES:
                return jsonify({"error": f"无效的权限范围: {s}"}), 400

        # 计算过期时间
        expires_in_days = safe_int(data.get("expires_in_days"), default=0)
        expires_at = None
        if expires_in_days > 0:
            expires_at = datetime.utcnow() + timedelta(days=expires_in_days)

        # 生成 Token
        token_value = PlatformToken.generate_token()

        token = PlatformToken(
            platform_id=platform_id,
            name=name,
            scopes=json.dumps(scopes),
            expires_at=expires_at,
            remarks=safe_str(data.get("remarks")),
        )
        token.set_token(token_value)
        db.session.add(token)
        db.session.commit()

        result = token.to_dict(include_token=True)
        return jsonify({
            "message": "Token 创建成功",
            "data": result,
            "warning": "请妥善保管 Token，创建后将无法再次查看完整 Token"
        }), 201
    except Exception as e:
        db.session.rollback()
        logger.error(f"创建 Token 失败: {e}", exc_info=True)
        return jsonify({"error": f"创建失败: {str(e)}"}), 500


@platform_token_bp.route("/tokens/<int:token_id>", methods=["GET"])
@jwt_required()
def get_token(token_id: int):
    """获取 Token 详情（不包含完整 Token 值）"""
    token = PlatformToken.query.get(token_id)
    if not token:
        return jsonify({"error": "Token 不存在"}), 404

    return jsonify({"data": token.to_dict()})


@platform_token_bp.route("/tokens/<int:token_id>", methods=["PUT"])
@jwt_required()
def update_token(token_id: int):
    """更新 Token

    请求体:
        name: Token 名称（可选）
        scopes: 权限范围列表（可选）
        enabled: 是否启用（可选）
        remarks: 备注（可选）
    """
    try:
        token = PlatformToken.query.get(token_id)
        if not token:
            return jsonify({"error": "Token 不存在"}), 404

        data = request.get_json(silent=True) or {}

        if "name" in data:
            token.name = safe_strip(data["name"])
        if "scopes" in data:
            scopes = data["scopes"]
            for s in scopes:
                if s not in VALID_SCOPES:
                    return jsonify({"error": f"无效的权限范围: {s}"}), 400
            token.scopes = json.dumps(scopes)
        if "enabled" in data:
            token.enabled = data["enabled"]
        if "remarks" in data:
            token.remarks = safe_str(data["remarks"])

        db.session.commit()
        return jsonify({"message": "更新成功", "data": token.to_dict()})
    except Exception as e:
        db.session.rollback()
        logger.error(f"更新 Token 失败: {e}", exc_info=True)
        return jsonify({"error": f"更新失败: {str(e)}"}), 500


@platform_token_bp.route("/tokens/<int:token_id>", methods=["DELETE"])
@jwt_required()
def delete_token(token_id: int):
    """删除 Token"""
    try:
        token = PlatformToken.query.get(token_id)
        if not token:
            return jsonify({"error": "Token 不存在"}), 404

        db.session.delete(token)
        db.session.commit()
        return jsonify({"message": "删除成功"})
    except Exception as e:
        db.session.rollback()
        logger.error(f"删除 Token 失败: {e}", exc_info=True)
        return jsonify({"error": f"删除失败: {str(e)}"}), 500
    token = PlatformToken.query.get(token_id)
    if not token:
        return jsonify({"error": "Token 不存在"}), 404

    db.session.delete(token)
    db.session.commit()
    return jsonify({"message": "Token 删除成功"})


@platform_token_bp.route("/tokens/<int:token_id>/regenerate", methods=["PUT"])
@jwt_required()
def regenerate_token(token_id: int):
    """重新生成 Token（保留其他配置）"""
    token = PlatformToken.query.get(token_id)
    if not token:
        return jsonify({"error": "Token 不存在"}), 404

    new_token_value = PlatformToken.generate_token()
    token.set_token(new_token_value)
    db.session.commit()

    return jsonify({
        "message": "Token 已重新生成",
        "token": new_token_value,
        "warning": "旧 Token 已失效，请更新使用新 Token 的应用"
    })


# ==================== Token 验证（供中间件使用） ====================

def verify_platform_token(token_value: str) -> tuple[bool, dict]:
    """验证平台 Token

    返回: (是否有效, Token 信息字典)
    """
    if not token_value or not token_value.startswith("daidai_"):
        return False, {"error": "无效的 Token 格式"}

    token = PlatformToken.query.filter_by(token=token_value).first()
    if not token:
        return False, {"error": "Token 不存在"}

    if not token.platform.enabled:
        return False, {"error": "平台已禁用"}

    if not token.is_valid():
        if token.is_expired():
            return False, {"error": "Token 已过期"}
        return False, {"error": "Token 已禁用"}

    # 更新最后使用时间
    token.last_used_at = datetime.utcnow()
    db.session.commit()

    return True, {
        "token_id": token.id,
        "platform_id": token.platform_id,
        "platform_name": token.platform.name,
        "scopes": json.loads(token.scopes or "[]"),
    }


# ==================== 调用日志 ====================

@platform_token_bp.route("/tokens/<int:token_id>/logs", methods=["GET"])
@jwt_required()
def list_token_logs(token_id: int):
    """获取 Token 调用日志"""
    token = PlatformToken.query.get(token_id)
    if not token:
        return jsonify({"error": "Token 不存在"}), 404

    page = request.args.get("page", 1, type=int)
    page_size = request.args.get("page_size", 20, type=int)

    query = PlatformTokenLog.query.filter_by(token_id=token_id)\
        .order_by(PlatformTokenLog.called_at.desc())
    pagination = query.paginate(page=page, per_page=page_size, error_out=False)

    return jsonify({
        "data": [log.to_dict() for log in pagination.items],
        "total": pagination.total,
        "page": page,
        "page_size": page_size,
    })


@platform_token_bp.route("/platforms/<int:platform_id>/logs", methods=["GET"])
@jwt_required()
def list_platform_logs(platform_id: int):
    """获取平台所有 Token 的调用日志"""
    platform = Platform.query.get(platform_id)
    if not platform:
        return jsonify({"error": "平台不存在"}), 404

    page = request.args.get("page", 1, type=int)
    page_size = request.args.get("page_size", 20, type=int)

    # 获取该平台所有 Token 的 ID
    token_ids = [t.id for t in platform.tokens.all()]

    query = PlatformTokenLog.query.filter(PlatformTokenLog.token_id.in_(token_ids))\
        .order_by(PlatformTokenLog.called_at.desc())
    pagination = query.paginate(page=page, per_page=page_size, error_out=False)

    return jsonify({
        "data": [log.to_dict() for log in pagination.items],
        "total": pagination.total,
        "page": page,
        "page_size": page_size,
    })


# ==================== 自动清理过期 Token ====================

def cleanup_expired_tokens() -> int:
    """清理过期的 Token（返回清理数量）"""
    expired_tokens = PlatformToken.query.filter(
        PlatformToken.expires_at.isnot(None),
        PlatformToken.expires_at < datetime.utcnow()
    ).all()

    count = len(expired_tokens)
    for token in expired_tokens:
        db.session.delete(token)

    db.session.commit()
    return count
