"""环境变量管理接口"""

import logging
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required

from app.extensions import db
from app.models.env_var import EnvVar
from app.utils.validators import safe_strip, safe_str, safe_int, validate_required

logger = logging.getLogger(__name__)
envs_bp = Blueprint("envs", __name__)


@envs_bp.route("", methods=["GET"])
@jwt_required()
def list_envs():
    """获取环境变量列表

    查询参数:
        keyword: 搜索关键词
        group: 分组过滤
        page: 页码
        page_size: 每页数量
    """
    keyword = safe_strip(request.args.get("keyword", ""))
    group = safe_strip(request.args.get("group", ""))
    page = safe_int(request.args.get("page"), default=1)
    page_size = safe_int(request.args.get("page_size"), default=20)

    query = EnvVar.query
    if keyword:
        query = query.filter(
            db.or_(
                EnvVar.name.ilike(f"%{keyword}%"),
                EnvVar.remarks.ilike(f"%{keyword}%"),
            )
        )
    if group:
        query = query.filter_by(group=group)

    query = query.order_by(EnvVar.position.asc(), EnvVar.created_at.desc())
    pagination = query.paginate(page=page, per_page=page_size, error_out=False)

    return jsonify({
        "data": [e.to_dict() for e in pagination.items],
        "total": pagination.total,
        "page": page,
        "page_size": page_size,
    })


@envs_bp.route("", methods=["POST"])
@jwt_required()
def create_env():
    """创建环境变量

    请求体:
        name: 变量名
        value: 变量值
        remarks: 备注（可选）
        group: 分组（可选）
    """
    try:
        data = request.get_json(silent=True) or {}

        # 使用辅助函数安全地处理输入
        name = safe_strip(data.get("name"))
        value = safe_str(data.get("value"))
        remarks = safe_str(data.get("remarks"))
        group = safe_strip(data.get("group"))

        # 验证必填字段
        error = validate_required(name, "变量名")
        if error:
            return jsonify({"error": error}), 400

        if not _is_valid_env_name(name):
            return jsonify({"error": "变量名只允许字母、数字和下划线"}), 400

        env = EnvVar(name=name, value=value, remarks=remarks, group=group)
        db.session.add(env)
        db.session.commit()

        return jsonify({"message": "创建成功", "data": env.to_dict()}), 201
    except Exception as e:
        db.session.rollback()
        logger.error(f"创建环境变量失败: {e}", exc_info=True)
        return jsonify({"error": f"创建失败: {str(e)}"}), 500


@envs_bp.route("/<int:env_id>", methods=["PUT"])
@jwt_required()
def update_env(env_id: int):
    """更新环境变量"""
    try:
        env = EnvVar.query.get(env_id)
        if not env:
            return jsonify({"error": "环境变量不存在"}), 404

        data = request.get_json(silent=True) or {}

        if "name" in data:
            name = safe_strip(data["name"])
            if not _is_valid_env_name(name):
                return jsonify({"error": "变量名只允许字母、数字和下划线"}), 400
            env.name = name

        if "value" in data:
            env.value = safe_str(data["value"])

        if "remarks" in data:
            env.remarks = safe_str(data["remarks"])

        if "group" in data:
            env.group = safe_strip(data["group"])

        db.session.commit()
        return jsonify({"message": "更新成功", "data": env.to_dict()})
    except Exception as e:
        db.session.rollback()
        logger.error(f"更新环境变量失败: {e}", exc_info=True)
        return jsonify({"error": f"更新失败: {str(e)}"}), 500


@envs_bp.route("/<int:env_id>", methods=["DELETE"])
@jwt_required()
def delete_env(env_id: int):
    """删除环境变量"""
    env = EnvVar.query.get(env_id)
    if not env:
        return jsonify({"error": "环境变量不存在"}), 404

    db.session.delete(env)
    db.session.commit()
    return jsonify({"message": "删除成功"})


@envs_bp.route("/<int:env_id>/enable", methods=["PUT"])
@jwt_required()
def enable_env(env_id: int):
    """启用环境变量"""
    env = EnvVar.query.get(env_id)
    if not env:
        return jsonify({"error": "环境变量不存在"}), 404
    env.enabled = True
    db.session.commit()
    return jsonify({"message": "已启用", "data": env.to_dict()})


@envs_bp.route("/<int:env_id>/disable", methods=["PUT"])
@jwt_required()
def disable_env(env_id: int):
    """禁用环境变量"""
    env = EnvVar.query.get(env_id)
    if not env:
        return jsonify({"error": "环境变量不存在"}), 404
    env.enabled = False
    db.session.commit()
    return jsonify({"message": "已禁用", "data": env.to_dict()})


@envs_bp.route("/batch", methods=["DELETE"])
@jwt_required()
def batch_delete():
    """批量删除环境变量

    请求体:
        ids: ID 列表
    """
    data = request.get_json(silent=True) or {}
    ids = data.get("ids", [])
    if not ids:
        return jsonify({"error": "请选择要删除的环境变量"}), 400

    count = EnvVar.query.filter(EnvVar.id.in_(ids)).delete()
    db.session.commit()
    return jsonify({"message": f"已删除 {count} 个环境变量"})


@envs_bp.route("/export", methods=["GET"])
@jwt_required()
def export_envs():
    """导出所有启用的环境变量为字典格式"""
    envs = EnvVar.query.filter_by(enabled=True).all()
    result = {e.name: e.value for e in envs}
    return jsonify({"data": result})


@envs_bp.route("/sort", methods=["PUT"])
@jwt_required()
def update_sort_order():
    """更新环境变量排序（Position 系统）

    请求体:
        source_id: 被移动的环境变量 ID
        target_id: 目标位置的环境变量 ID（移动到它之前）
        target_id 为 null 表示移动到最后
    """
    from app.models.env_var import INIT_POSITION, MAX_POSITION, MIN_POSITION

    data = request.get_json(silent=True) or {}
    source_id = data.get("source_id")
    target_id = data.get("target_id")

    if not source_id:
        return jsonify({"error": "缺少 source_id 参数"}), 400

    source_env = EnvVar.query.get(source_id)
    if not source_env:
        return jsonify({"error": "源环境变量不存在"}), 404

    if target_id is None:
        # 移动到最后
        max_env = EnvVar.query.order_by(EnvVar.position.desc()).first()
        if max_env:
            source_env.position = max_env.position + 1000.0
        else:
            source_env.position = INIT_POSITION
    else:
        # 移动到目标位置之前
        target_env = EnvVar.query.get(target_id)
        if not target_env:
            return jsonify({"error": "目标环境变量不存在"}), 404

        # 找到目标位置的前一个环境变量
        prev_env = EnvVar.query.filter(
            EnvVar.position < target_env.position
        ).order_by(EnvVar.position.desc()).first()

        if prev_env:
            # 插入到两者之间
            source_env.position = (prev_env.position + target_env.position) / 2.0
        else:
            # 插入到最前面
            source_env.position = target_env.position / 2.0

    db.session.commit()
    return jsonify({"message": "排序已更新", "data": source_env.to_dict()})


@envs_bp.route("/groups", methods=["GET"])
@jwt_required()
def list_groups():
    """获取所有分组"""
    groups = db.session.query(EnvVar.group).filter(EnvVar.group != "").distinct().all()
    group_list = [g[0] for g in groups if g[0]]
    return jsonify({"data": group_list})


@envs_bp.route("/export-all", methods=["GET"])
@jwt_required()
def export_all_envs():
    """导出所有环境变量为 JSON"""
    envs = EnvVar.query.all()
    data = []
    for env in envs:
        data.append({
            "name": env.name,
            "value": env.value,
            "remarks": env.remarks,
            "group": env.group,
            "enabled": env.enabled,
        })
    return jsonify({"data": data})


@envs_bp.route("/export-files", methods=["POST"])
@jwt_required()
def export_env_files():
    """导出环境变量为多种格式文件（参考青龙）

    请求体:
        format: 导出格式 (shell/js/python/all)
        enabled_only: 是否只导出已启用的（默认 true）

    返回:
        导出的文件内容或文件路径
    """
    from app.utils.env_exporter import (
        export_env_to_shell,
        export_env_to_js,
        export_env_to_python,
        export_all_formats
    )
    from flask import current_app
    import tempfile

    data = request.get_json(silent=True) or {}
    export_format = data.get("format", "all")
    enabled_only = data.get("enabled_only", True)

    # 查询环境变量
    query = EnvVar.query
    if enabled_only:
        query = query.filter_by(enabled=True)

    envs = query.order_by(EnvVar.position.asc()).all()
    env_list = [{"name": e.name, "value": e.value} for e in envs]

    # 创建临时目录
    temp_dir = tempfile.mkdtemp(prefix="daidai_env_")

    try:
        if export_format == "all":
            # 导出所有格式
            paths = export_all_formats(env_list, temp_dir)
            # 读取文件内容
            result = {}
            for fmt, path in paths.items():
                with open(path, 'r', encoding='utf-8') as f:
                    result[fmt] = f.read()
            return jsonify({"data": result})

        elif export_format == "shell":
            path = f"{temp_dir}/.env"
            export_env_to_shell(env_list, path)
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            return jsonify({"data": {"shell": content}})

        elif export_format == "js":
            path = f"{temp_dir}/.env.js"
            export_env_to_js(env_list, path)
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            return jsonify({"data": {"js": content}})

        elif export_format == "python":
            path = f"{temp_dir}/.env.py"
            export_env_to_python(env_list, path)
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            return jsonify({"data": {"python": content}})

        else:
            return jsonify({"error": "不支持的导出格式"}), 400

    finally:
        # 清理临时文件
        import shutil
        try:
            shutil.rmtree(temp_dir)
        except Exception:
            pass


@envs_bp.route("/import", methods=["POST"])
@jwt_required()
def import_envs():
    """批量导入环境变量

    请求体:
        envs: 环境变量列表
        mode: 导入模式 (merge/replace)

    兼容青龙面板导出格式（自动识别 status 字段等）
    """
    data = request.get_json(silent=True) or {}
    envs_data = data.get("envs", [])
    mode = data.get("mode", "merge")

    if not isinstance(envs_data, list):
        return jsonify({"error": "envs 必须是数组"}), 400

    if mode == "replace":
        # 替换模式：删除所有现有环境变量
        EnvVar.query.delete()

    imported_count = 0
    errors = []

    for env_data in envs_data:
        try:
            name = safe_strip(env_data.get("name"))
            if not name or not _is_valid_env_name(name):
                errors.append(f"变量名 {name} 不合法")
                continue

            value = safe_str(env_data.get("value"))
            remarks = safe_str(env_data.get("remarks"))
            group = safe_strip(env_data.get("group"))

            # 兼容青龙面板导出格式：status 为数字 (0=启用, 1=禁用)
            if "status" in env_data and isinstance(env_data["status"], (int, float)):
                enabled = int(env_data["status"]) == 0
            else:
                enabled = env_data.get("enabled", True)

            # merge 模式下按 name+value 匹配去重（同名变量可能有多个不同值）
            if mode == "merge":
                existing = EnvVar.query.filter_by(name=name, value=value).first()
            else:
                existing = None

            if existing:
                # 更新现有变量
                existing.remarks = remarks
                if group:
                    existing.group = group
                existing.enabled = enabled
            else:
                # 创建新变量
                env = EnvVar(
                    name=name,
                    value=value,
                    remarks=remarks,
                    group=group,
                    enabled=enabled,
                )
                db.session.add(env)

            imported_count += 1
        except Exception as e:
            errors.append(f"导入 {env_data.get('name', '未知')} 失败: {str(e)}")

    try:
        db.session.commit()
        result = {"message": f"成功导入 {imported_count} 个环境变量"}
        if errors:
            result["errors"] = errors
        return jsonify(result), 201 if imported_count > 0 else 400
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"导入失败: {str(e)}"}), 500


def _is_valid_env_name(name: str) -> bool:
    """校验环境变量名是否合法"""
    import re
    return bool(re.match(r'^[A-Za-z_][A-Za-z0-9_]*$', name))
