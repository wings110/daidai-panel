"""安全管理接口"""

import logging
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

from app.extensions import db
from app.models.login_log import LoginLog
from app.models.user_session import UserSession
from app.models.ip_whitelist import IPWhitelist
from app.models.two_factor_auth import TwoFactorAuth
from app.models.user import User
from app.utils.permissions import require_admin, get_current_user
from app.services.login_security import clean_old_login_logs
from app.utils.validators import safe_strip, safe_str, safe_int

logger = logging.getLogger(__name__)
security_bp = Blueprint("security", __name__)


# ==================== 登录日志 ====================

@security_bp.route("/login-logs", methods=["GET"])
@jwt_required()
def list_login_logs():
    """获取登录日志列表"""
    user_id = request.args.get("user_id", type=int)
    status = request.args.get("status", type=int)
    page = request.args.get("page", 1, type=int)
    page_size = request.args.get("page_size", 20, type=int)

    query = LoginLog.query
    if user_id:
        query = query.filter_by(user_id=user_id)
    if status is not None:
        query = query.filter_by(status=status)

    query = query.order_by(LoginLog.created_at.desc())
    pagination = query.paginate(page=page, per_page=page_size, error_out=False)

    return jsonify({
        "data": [log.to_dict() for log in pagination.items],
        "total": pagination.total,
        "page": page,
        "page_size": page_size,
    })


@security_bp.route("/login-logs/clean", methods=["DELETE"])
@jwt_required()
@require_admin
def clean_login_logs():
    """清理旧的登录日志"""
    days = request.args.get("days", 90, type=int)
    deleted = clean_old_login_logs(days)
    return jsonify({"message": f"已清理 {deleted} 条登录日志"})


# ==================== 会话管理 ====================

@security_bp.route("/sessions", methods=["GET"])
@jwt_required()
def list_sessions():
    """获取当前用户的会话列表"""
    current_user = get_current_user()
    sessions = UserSession.query.filter_by(
        user_id=current_user.id,
        is_active=True
    ).order_by(UserSession.last_activity.desc()).all()

    return jsonify({"data": [s.to_dict() for s in sessions]})


@security_bp.route("/sessions/<int:session_id>", methods=["DELETE"])
@jwt_required()
def revoke_session(session_id: int):
    """撤销指定会话"""
    current_user = get_current_user()
    session = UserSession.query.filter_by(
        id=session_id,
        user_id=current_user.id
    ).first()

    if not session:
        return jsonify({"error": "会话不存在"}), 404

    session.revoke()
    return jsonify({"message": "会话已撤销"})


@security_bp.route("/sessions/revoke-all", methods=["POST"])
@jwt_required()
def revoke_all_sessions():
    """撤销所有其他会话"""
    current_user = get_current_user()
    current_token = request.headers.get("Authorization", "").replace("Bearer ", "")

    sessions = UserSession.query.filter_by(
        user_id=current_user.id,
        is_active=True
    ).all()

    revoked_count = 0
    for session in sessions:
        if session.session_token != current_token:
            session.revoke()
            revoked_count += 1

    return jsonify({"message": f"已撤销 {revoked_count} 个会话"})


# ==================== IP 白名单 ====================

@security_bp.route("/ip-whitelist", methods=["GET"])
@jwt_required()
@require_admin
def list_ip_whitelist():
    """获取 IP 白名单列表"""
    ips = IPWhitelist.query.order_by(IPWhitelist.created_at.desc()).all()
    return jsonify({"data": [ip.to_dict() for ip in ips]})


@security_bp.route("/ip-whitelist", methods=["POST"])
@jwt_required()
@require_admin
def add_ip_whitelist():
    """添加 IP 到白名单"""
    try:
        data = request.get_json(silent=True) or {}
        ip_address = safe_strip(data.get("ip_address"))
        description = safe_str(data.get("description"))

        if not ip_address:
            return jsonify({"error": "IP 地址不能为空"}), 400

        # 检查是否已存在
        existing = IPWhitelist.query.filter_by(ip_address=ip_address).first()
        if existing:
            return jsonify({"error": "该 IP 已在白名单中"}), 409

        current_user = get_current_user()
        ip_entry = IPWhitelist(
            ip_address=ip_address,
            description=description,
            created_by=current_user.id if current_user else None,
        )
        db.session.add(ip_entry)
        db.session.commit()

        return jsonify({"message": "添加成功", "data": ip_entry.to_dict()}), 201
    except Exception as e:
        db.session.rollback()
        logger.error(f"添加 IP 白名单失败: {e}", exc_info=True)
        return jsonify({"error": f"添加失败: {str(e)}"}), 500


@security_bp.route("/ip-whitelist/<int:ip_id>", methods=["PUT"])
@jwt_required()
@require_admin
def update_ip_whitelist(ip_id: int):
    """更新 IP 白名单"""
    ip_entry = IPWhitelist.query.get(ip_id)
    if not ip_entry:
        return jsonify({"error": "IP 不存在"}), 404

    data = request.get_json(silent=True) or {}
    if "description" in data:
        ip_entry.description = data["description"]
    if "enabled" in data:
        ip_entry.enabled = data["enabled"]

    db.session.commit()
    return jsonify({"message": "更新成功", "data": ip_entry.to_dict()})


@security_bp.route("/ip-whitelist/<int:ip_id>", methods=["DELETE"])
@jwt_required()
@require_admin
def delete_ip_whitelist(ip_id: int):
    """删除 IP 白名单"""
    ip_entry = IPWhitelist.query.get(ip_id)
    if not ip_entry:
        return jsonify({"error": "IP 不存在"}), 404

    db.session.delete(ip_entry)
    db.session.commit()
    return jsonify({"message": "删除成功"})


# ==================== 双因素认证 ====================

@security_bp.route("/2fa/setup", methods=["POST"])
@jwt_required()
def setup_2fa():
    """设置双因素认证"""
    current_user = get_current_user()

    # 检查是否已设置
    tfa = TwoFactorAuth.query.filter_by(user_id=current_user.id).first()
    if tfa and tfa.enabled:
        return jsonify({"error": "双因素认证已启用"}), 400

    # 生成新的 secret
    secret = TwoFactorAuth.generate_secret()

    if not tfa:
        tfa = TwoFactorAuth(user_id=current_user.id, secret=secret)
        db.session.add(tfa)
    else:
        tfa.secret = secret

    db.session.commit()

    # 生成二维码 URI
    totp_uri = tfa.get_totp_uri(current_user.username)

    return jsonify({
        "secret": secret,
        "totp_uri": totp_uri,
        "message": "请使用认证器应用扫描二维码"
    })


@security_bp.route("/2fa/enable", methods=["POST"])
@jwt_required()
def enable_2fa():
    """启用双因素认证"""
    try:
        current_user = get_current_user()
        data = request.get_json(silent=True) or {}
        token = safe_strip(data.get("token"))

        if not token:
            return jsonify({"error": "请输入验证码"}), 400

        tfa = TwoFactorAuth.query.filter_by(user_id=current_user.id).first()
        if not tfa:
            return jsonify({"error": "请先设置双因素认证"}), 400

        if not tfa.verify_token(token):
            return jsonify({"error": "验证码错误"}), 400

        tfa.enabled = True
        backup_codes = tfa.generate_backup_codes()
        db.session.commit()

        return jsonify({
            "message": "双因素认证已启用",
            "backup_codes": backup_codes
        })
    except Exception as e:
        db.session.rollback()
        logger.error(f"启用双因素认证失败: {e}", exc_info=True)
        return jsonify({"error": f"启用失败: {str(e)}"}), 500


@security_bp.route("/2fa/disable", methods=["POST"])
@jwt_required()
def disable_2fa():
    """禁用双因素认证"""
    current_user = get_current_user()
    data = request.get_json(silent=True) or {}
    password = data.get("password", "")

    if not current_user.check_password(password):
        return jsonify({"error": "密码错误"}), 400

    tfa = TwoFactorAuth.query.filter_by(user_id=current_user.id).first()
    if not tfa or not tfa.enabled:
        return jsonify({"error": "双因素认证未启用"}), 400

    tfa.enabled = False
    db.session.commit()

    return jsonify({"message": "双因素认证已禁用"})


@security_bp.route("/2fa/status", methods=["GET"])
@jwt_required()
def get_2fa_status():
    """获取双因素认证状态"""
    current_user = get_current_user()
    tfa = TwoFactorAuth.query.filter_by(user_id=current_user.id).first()

    return jsonify({
        "enabled": tfa.enabled if tfa else False,
        "has_backup_codes": bool(tfa and tfa.backup_codes) if tfa else False
    })


@security_bp.route("/2fa/regenerate-backup-codes", methods=["POST"])
@jwt_required()
def regenerate_backup_codes():
    """重新生成备用码"""
    current_user = get_current_user()
    data = request.get_json(silent=True) or {}
    password = data.get("password", "")

    if not current_user.check_password(password):
        return jsonify({"error": "密码错误"}), 400

    tfa = TwoFactorAuth.query.filter_by(user_id=current_user.id).first()
    if not tfa or not tfa.enabled:
        return jsonify({"error": "双因素认证未启用"}), 400

    backup_codes = tfa.generate_backup_codes()
    return jsonify({
        "message": "备用码已重新生成",
        "backup_codes": backup_codes
    })
