"""认证接口"""

import time
import logging
from datetime import datetime, timedelta
from collections import defaultdict

from flask import Blueprint, request, jsonify
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    jwt_required,
    get_jwt_identity,
    get_jwt,
)

from app.extensions import db, limiter, add_token_to_blocklist
from app.models.user import User
from app.models.login_attempt import LoginAttempt
from app.utils.validators import safe_strip, validate_required

logger = logging.getLogger(__name__)
auth_bp = Blueprint("auth", __name__)

# ---------- 登录失败锁定配置 ----------
_LOGIN_MAX_ATTEMPTS = 5       # 最大尝试次数
_LOGIN_LOCKOUT_MINUTES = 15   # 锁定时长（分钟）
_REQUIRE_CAPTCHA_AFTER = 3    # 失败 N 次后需要验证码


def _check_login_lockout_db(ip: str) -> tuple[bool, int]:
    """检查 IP 是否被锁定（使用数据库持久化），返回 (是否锁定, 剩余秒数)"""
    cutoff_time = datetime.utcnow() - timedelta(minutes=_LOGIN_LOCKOUT_MINUTES)

    # 查询最近的失败记录
    recent_failures = LoginAttempt.query.filter(
        LoginAttempt.ip_address == ip,
        LoginAttempt.success == False,
        LoginAttempt.created_at > cutoff_time
    ).count()

    if recent_failures >= _LOGIN_MAX_ATTEMPTS:
        # 获取最早的失败记录
        first_failure = LoginAttempt.query.filter(
            LoginAttempt.ip_address == ip,
            LoginAttempt.success == False,
            LoginAttempt.created_at > cutoff_time
        ).order_by(LoginAttempt.created_at.asc()).first()

        if first_failure:
            elapsed = (datetime.utcnow() - first_failure.created_at).total_seconds()
            remaining = int(_LOGIN_LOCKOUT_MINUTES * 60 - elapsed)
            return True, max(remaining, 0)

    return False, 0


def _require_captcha(ip: str) -> bool:
    """检查是否需要验证码"""
    cutoff_time = datetime.utcnow() - timedelta(minutes=_LOGIN_LOCKOUT_MINUTES)

    recent_failures = LoginAttempt.query.filter(
        LoginAttempt.ip_address == ip,
        LoginAttempt.success == False,
        LoginAttempt.created_at > cutoff_time
    ).count()

    return recent_failures >= _REQUIRE_CAPTCHA_AFTER


def _record_login_attempt(ip: str, username: str = None, success: bool = False,
                          failure_reason: str = None) -> None:
    """记录登录尝试"""
    user_agent = request.headers.get('User-Agent', '')[:512]

    attempt = LoginAttempt(
        ip_address=ip,
        username=username,
        success=success,
        failure_reason=failure_reason,
        user_agent=user_agent
    )
    db.session.add(attempt)
    db.session.commit()


def _clear_login_failures(ip: str) -> None:
    """清除登录失败记录（登录成功后调用）"""
    cutoff_time = datetime.utcnow() - timedelta(minutes=_LOGIN_LOCKOUT_MINUTES)

    # 删除最近的失败记录
    LoginAttempt.query.filter(
        LoginAttempt.ip_address == ip,
        LoginAttempt.success == False,
        LoginAttempt.created_at > cutoff_time
    ).delete()
    db.session.commit()


@auth_bp.route("/check-init", methods=["GET"])
def check_init():
    """检查是否需要初始化管理员账号"""
    need_init = User.query.count() == 0
    return jsonify({"need_init": need_init})


@auth_bp.route("/init", methods=["POST"])
def init_admin():
    """初始化管理员账号（仅当无用户时可用）

    请求体:
        username: 用户名
        password: 密码（最少 8 位）
    """
    try:
        if User.query.count() > 0:
            return jsonify({"error": "管理员已初始化，不可重复操作"}), 400

        data = request.get_json(silent=True) or {}
        username = safe_strip(data.get("username"))
        password = data.get("password", "")

        if not username or len(username) < 2:
            return jsonify({"error": "用户名至少 2 个字符"}), 400
        if len(password) < 8:
            return jsonify({"error": "密码至少 8 个字符"}), 400

        user = User(username=username, role="admin")
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        return jsonify({"message": "管理员初始化成功", "user": user.to_dict()}), 201
    except Exception as e:
        db.session.rollback()
        logger.error(f"初始化管理员失败: {e}", exc_info=True)
        return jsonify({"error": f"初始化失败: {str(e)}"}), 500


@auth_bp.route("/login", methods=["POST"])
@limiter.limit("5/minute")  # 降低速率限制从 10 改为 5
def login():
    """用户登录

    请求体:
        username: 用户名
        password: 密码
        totp_token: TOTP 验证码（如果启用了 2FA）
    """
    from app.services.login_security import (
        log_login_attempt, check_ip_whitelist,
        detect_suspicious_login, check_login_rate_limit
    )
    from app.models.two_factor_auth import TwoFactorAuth

    # 首次启动检查是否需要初始化
    if User.query.count() == 0:
        return jsonify({"error": "请先初始化管理员账号", "need_init": True}), 403

    data = request.get_json(silent=True) or {}
    username = safe_strip(data.get("username"))
    password = data.get("password", "")
    totp_token = safe_strip(data.get("totp_token"))

    if not username or not password:
        return jsonify({"error": "用户名和密码不能为空"}), 400

    # IP 白名单检查
    allowed, reason = check_ip_whitelist()
    if not allowed:
        log_login_attempt(username, success=False, failure_reason=reason)
        return jsonify({"error": reason}), 403

    # 登录频率限制
    allowed, reason = check_login_rate_limit(username)
    if not allowed:
        log_login_attempt(username, success=False, failure_reason=reason)
        return jsonify({"error": reason}), 429

    # 登录失败锁定检查
    client_ip = request.remote_addr or "unknown"
    locked, remaining = _check_login_lockout_db(client_ip)
    if locked:
        reason = f"登录失败次数过多，请 {remaining // 60 + 1} 分钟后再试"
        _record_login_attempt(client_ip, username, success=False, failure_reason=reason)
        return jsonify({"error": reason}), 429

    # 检查是否需要验证码
    need_captcha = _require_captcha(client_ip)
    if need_captcha:
        from app.models.system_config import SystemConfig
        geetest_enabled = SystemConfig.get("geetest_enabled", "false") == "true"
        if geetest_enabled:
            lot_number = safe_strip(data.get("lot_number"))
            captcha_output = safe_strip(data.get("captcha_output"))
            pass_token = safe_strip(data.get("pass_token"))
            gen_time = safe_strip(data.get("gen_time"))
            if not all([lot_number, captcha_output, pass_token, gen_time]):
                return jsonify({
                    "error": "需要验证码",
                    "require_captcha": True
                }), 400
            from app.utils.geetest import validate_geetest
            if not validate_geetest(lot_number, captcha_output, pass_token, gen_time):
                return jsonify({
                    "error": "验证码验证失败，请重试",
                    "require_captcha": True
                }), 400
        else:
            # 极验未启用时，仅提示需要验证码但不阻止登录
            captcha_code = safe_strip(data.get("captcha"))
            if not captcha_code:
                return jsonify({
                    "error": "需要验证码",
                    "require_captcha": True
                }), 400

    # 验证用户名和密码
    user = User.query.filter_by(username=username).first()
    if not user or not user.check_password(password):
        _record_login_attempt(client_ip, username, success=False, failure_reason="用户名或密码错误")
        return jsonify({"error": "用户名或密码错误"}), 401

    if not user.enabled:
        log_login_attempt(username, user.id, success=False, failure_reason="账户已禁用")
        return jsonify({"error": "账户已被禁用，请联系管理员"}), 403

    # 检查是否启用了 2FA
    tfa = TwoFactorAuth.query.filter_by(user_id=user.id, enabled=True).first()
    if tfa:
        if not totp_token:
            return jsonify({
                "error": "需要双因素认证",
                "require_2fa": True
            }), 401

        # 验证 TOTP token 或备用码
        valid = tfa.verify_token(totp_token) or tfa.verify_backup_code(totp_token)
        if not valid:
            _record_login_attempt(client_ip, username, success=False, failure_reason="双因素认证失败")
            return jsonify({"error": "验证码错误"}), 401

    # 检测可疑登录
    is_suspicious, sus_reason = detect_suspicious_login(username)

    # 登录成功，清除失败记录
    _clear_login_failures(client_ip)

    # 记录最后登录时间
    user.last_login_at = datetime.utcnow()
    db.session.commit()

    # 记录登录日志
    log_login_attempt(username, user.id, success=True,
                     login_type="2fa" if tfa else "password")

    access_token = create_access_token(identity=user.username)
    refresh_token = create_refresh_token(identity=user.username)

    # 登录成功通知（异步，不阻塞响应）
    try:
        import threading
        from app.models.system_config import SystemConfig
        notify_login = SystemConfig.get("notify_on_login")
        if notify_login == "true" or is_suspicious:
            _username = user.username
            _time_str = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
            _ip = client_ip
            _suspicious = is_suspicious
            _sus_reason = sus_reason

            def _send_login_notify():
                from wsgi import app as _app
                with _app.app_context():
                    from app.services.notifier import broadcast_notification
                    title = "⚠️ 可疑登录通知" if _suspicious else "登录通知"
                    content = f"用户 {_username} 于 {_time_str} (UTC) 登录面板\nIP: {_ip}"
                    if _suspicious:
                        content += f"\n\n可疑原因: {_sus_reason}"
                    broadcast_notification(title=title, content=content)
            threading.Thread(target=_send_login_notify, daemon=True).start()
    except Exception:
        pass  # 通知失败不影响登录

    response_data = {
        "message": "登录成功",
        "access_token": access_token,
        "refresh_token": refresh_token,
        "user": user.to_dict(),
    }

    if is_suspicious:
        response_data["warning"] = sus_reason

    return jsonify(response_data)


@auth_bp.route("/logout", methods=["POST"])
@jwt_required()
def logout():
    """登出（将当前 Token 加入黑名单）"""
    jwt_data = get_jwt()
    jti = jwt_data["jti"]
    exp = jwt_data.get("exp", 0)

    # 计算 Token 剩余有效期
    from datetime import datetime
    now = datetime.utcnow().timestamp()
    expires_in = max(int(exp - now), 0)

    # 获取当前用户 ID
    identity = get_jwt_identity()
    user = User.query.filter_by(username=identity).first()
    user_id = user.id if user else None

    # 加入黑名单（持久化到数据库）
    add_token_to_blocklist(jti, expires_in=expires_in, token_type="access", user_id=user_id)

    return jsonify({"message": "已安全退出"})


@auth_bp.route("/refresh", methods=["POST"])
@jwt_required(refresh=True)
def refresh():
    """刷新 Access Token"""
    identity = get_jwt_identity()
    user = User.query.filter_by(username=identity).first()
    if not user or not user.enabled:
        return jsonify({"error": "账户不可用"}), 403
    access_token = create_access_token(identity=identity)
    return jsonify({"access_token": access_token})


@auth_bp.route("/user", methods=["GET"])
@jwt_required()
def get_current_user():
    """获取当前登录用户信息"""
    identity = get_jwt_identity()
    user = User.query.filter_by(username=identity).first()
    if not user:
        return jsonify({"error": "用户不存在"}), 404
    return jsonify({"user": user.to_dict()})


@auth_bp.route("/password", methods=["PUT"])
@jwt_required()
def change_password():
    """修改密码

    请求体:
        old_password: 旧密码
        new_password: 新密码（最少 8 位）
    """
    try:
        identity = get_jwt_identity()
        user = User.query.filter_by(username=identity).first()
        if not user:
            return jsonify({"error": "用户不存在"}), 404

        data = request.get_json(silent=True) or {}
        old_password = data.get("old_password", "")
        new_password = data.get("new_password", "")

        if not user.check_password(old_password):
            return jsonify({"error": "旧密码错误"}), 400
        if len(new_password) < 8:
            return jsonify({"error": "新密码至少 8 个字符"}), 400

        user.set_password(new_password)
        db.session.commit()

        return jsonify({"message": "密码修改成功"})
    except Exception as e:
        db.session.rollback()
        logger.error(f"修改密码失败: {e}", exc_info=True)
        return jsonify({"error": f"修改失败: {str(e)}"}), 500


@auth_bp.route("/captcha-config", methods=["GET"])
def get_captcha_config():
    """获取验证码配置（公开接口，前端初始化极验 SDK 需要）"""
    from app.models.system_config import SystemConfig
    enabled = SystemConfig.get("geetest_enabled", "false") == "true"
    captcha_id = SystemConfig.get("geetest_captcha_id", "") if enabled else ""
    return jsonify({
        "enabled": enabled,
        "captcha_id": captcha_id,
    })
