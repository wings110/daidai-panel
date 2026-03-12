"""开放 API 管理接口（Client ID / Client Secret）"""

import logging
import json
from datetime import datetime, timedelta

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, create_access_token

from app.extensions import db, limiter
from app.models.open_app import OpenApp, ApiCallLog
from app.utils.validators import safe_strip, safe_str, safe_int, safe_bool

logger = logging.getLogger(__name__)
open_api_bp = Blueprint("open_api", __name__)

VALID_SCOPES = ["tasks", "scripts", "envs", "logs", "system"]


# ==================== 应用管理（需管理员 JWT） ====================

@open_api_bp.route("/apps", methods=["GET"])
@jwt_required()
def list_apps():
    """获取应用列表"""
    apps = OpenApp.query.order_by(OpenApp.created_at.desc()).all()
    return jsonify({"data": [a.to_dict() for a in apps]})


@open_api_bp.route("/apps", methods=["POST"])
@jwt_required()
def create_app():
    """创建应用（返回 Client ID + Client Secret，Secret 仅此一次明文展示）

    请求体:
        name: 应用名称
        scopes: 权限范围列表（可选）
        token_expiry: Token 有效期秒数（可选）
    """
    data = request.get_json(silent=True) or {}
    name = safe_strip(data.get("name"))
    if not name:
        return jsonify({"error": "应用名称不能为空"}), 400

    scopes = data.get("scopes", [])
    for s in scopes:
        if s not in VALID_SCOPES:
            return jsonify({"error": f"无效的权限范围: {s}"}), 400

    client_id = OpenApp.generate_client_id()
    client_secret = OpenApp.generate_client_secret()

    app_obj = OpenApp(
        name=name,
        client_id=client_id,
        scopes=json.dumps(scopes),
        token_expiry=data.get("token_expiry", 2592000),
    )
    app_obj.set_secret(client_secret)
    db.session.add(app_obj)
    db.session.commit()

    result = app_obj.to_dict()
    result["client_secret"] = client_secret  # 仅创建时返回

    return jsonify({"message": "应用创建成功", "data": result}), 201


@open_api_bp.route("/apps/<int:app_id>", methods=["PUT"])
@jwt_required()
def update_app(app_id: int):
    """编辑应用"""
    app_obj = OpenApp.query.get(app_id)
    if not app_obj:
        return jsonify({"error": "应用不存在"}), 404

    data = request.get_json(silent=True) or {}
    if "name" in data:
        app_obj.name = safe_strip(data["name"])
    if "scopes" in data:
        scopes = data["scopes"]
        for s in scopes:
            if s not in VALID_SCOPES:
                return jsonify({"error": f"无效的权限范围: {s}"}), 400
        app_obj.scopes = json.dumps(scopes)
    if "token_expiry" in data:
        app_obj.token_expiry = data["token_expiry"]
    if "enabled" in data:
        app_obj.enabled = data["enabled"]

    db.session.commit()
    return jsonify({"message": "更新成功", "data": app_obj.to_dict()})


@open_api_bp.route("/apps/<int:app_id>", methods=["DELETE"])
@jwt_required()
def delete_app(app_id: int):
    """删除应用"""
    app_obj = OpenApp.query.get(app_id)
    if not app_obj:
        return jsonify({"error": "应用不存在"}), 404

    db.session.delete(app_obj)
    db.session.commit()
    return jsonify({"message": "应用删除成功"})


@open_api_bp.route("/apps/<int:app_id>/reset-secret", methods=["PUT"])
@jwt_required()
def reset_secret(app_id: int):
    """重置 Client Secret"""
    app_obj = OpenApp.query.get(app_id)
    if not app_obj:
        return jsonify({"error": "应用不存在"}), 404

    new_secret = OpenApp.generate_client_secret()
    app_obj.set_secret(new_secret)
    db.session.commit()

    return jsonify({
        "message": "Secret 已重置",
        "client_secret": new_secret,
    })


@open_api_bp.route("/apps/<int:app_id>/secret", methods=["POST"])
@jwt_required()
@limiter.limit("3/hour")  # 严格限制密钥查询频率
def get_app_secret(app_id: int):
    """获取应用的 Client Secret（解密后的明文）

    安全要求：
    1. 需要管理员权限
    2. 需要二次密码验证
    3. 记录审计日志
    4. 严格速率限制
    """
    from flask_jwt_extended import get_jwt_identity
    from app.models.user import User

    # 1. 验证管理员权限
    current_username = get_jwt_identity()
    user = User.query.filter_by(username=current_username).first()

    if not user or user.role != 'admin':
        return jsonify({"error": "需要管理员权限"}), 403

    # 2. 验证应用存在
    app_obj = OpenApp.query.get(app_id)
    if not app_obj:
        return jsonify({"error": "应用不存在"}), 404

    # 3. 要求二次密码验证
    data = request.get_json(silent=True) or {}
    password = data.get("password", "")

    if not password:
        return jsonify({"error": "需要输入当前密码进行二次验证"}), 400

    if not user.check_password(password):
        # 记录失败尝试
        _log_security_event("SECRET_ACCESS_FAILED", user.id, app_id,
                           "密码验证失败", request.remote_addr)
        return jsonify({"error": "密码验证失败"}), 401

    # 4. 记录审计日志
    _log_security_event("SECRET_ACCESS", user.id, app_id,
                       "查看应用密钥", request.remote_addr)

    try:
        secret = app_obj.get_secret()
        return jsonify({
            "client_secret": secret,
            "warning": "请妥善保管密钥，不要泄露给他人"
        })
    except Exception as e:
        return jsonify({"error": f"解密失败: {str(e)}"}), 500


def _log_security_event(event_type: str, user_id: int, app_id: int,
                        description: str, ip_address: str) -> None:
    """记录安全审计日志"""
    from app.models.security_audit import SecurityAudit

    audit = SecurityAudit(
        event_type=event_type,
        user_id=user_id,
        resource_type="open_app",
        resource_id=app_id,
        description=description,
        ip_address=ip_address,
        user_agent=request.headers.get('User-Agent', '')[:512]
    )
    db.session.add(audit)
    db.session.commit()


# ==================== 开放 Token 获取（无需登录） ====================

@open_api_bp.route("/auth/token", methods=["POST"])
@limiter.limit("10/minute")
def get_token():
    """用 Client ID + Client Secret 换取 Access Token

    请求体:
        client_id: Client ID
        client_secret: Client Secret
    """
    data = request.get_json(silent=True) or {}
    client_id = safe_strip(data.get("client_id"))
    client_secret = safe_strip(data.get("client_secret"))

    if not client_id or not client_secret:
        return jsonify({"error": "缺少 client_id 或 client_secret"}), 400

    app_obj = OpenApp.query.filter_by(client_id=client_id).first()
    if not app_obj:
        return jsonify({"error": "无效的 client_id"}), 401
    if not app_obj.enabled:
        return jsonify({"error": "应用已禁用"}), 403
    if not app_obj.check_secret(client_secret):
        return jsonify({"error": "client_secret 错误"}), 401

    # 生成 token，identity 中标记为开放 API
    token = create_access_token(
        identity=f"app:{app_obj.id}",
        expires_delta=timedelta(seconds=app_obj.token_expiry),
        additional_claims={"scopes": json.loads(app_obj.scopes or "[]"), "type": "open_api"},
    )

    app_obj.last_used_at = datetime.utcnow()
    db.session.commit()

    return jsonify({
        "access_token": token,
        "token_type": "Bearer",
        "expires_in": app_obj.token_expiry,
    })


# ==================== 调用日志 ====================

@open_api_bp.route("/apps/<int:app_id>/logs", methods=["GET"])
@jwt_required()
def list_call_logs(app_id: int):
    """获取应用调用日志"""
    page = request.args.get("page", 1, type=int)
    page_size = request.args.get("page_size", 20, type=int)

    query = ApiCallLog.query.filter_by(app_id=app_id)\
        .order_by(ApiCallLog.called_at.desc())
    pagination = query.paginate(page=page, per_page=page_size, error_out=False)

    return jsonify({
        "data": [log.to_dict() for log in pagination.items],
        "total": pagination.total,
        "page": page,
        "page_size": page_size,
    })
