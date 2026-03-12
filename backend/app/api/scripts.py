"""脚本管理接口"""

import os
import re
import subprocess
import threading
import time
import logging
from datetime import datetime

from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required

from app.extensions import db
from app.models.script_version import ScriptVersion
from app.utils.validators import safe_strip, safe_str

logger = logging.getLogger(__name__)
scripts_bp = Blueprint("scripts", __name__)

ALLOWED_EXTENSIONS = {
    # 脚本文件
    ".py", ".js", ".sh", ".ts",
    # 配置文件
    ".json", ".yaml", ".yml", ".txt", ".md", ".conf", ".ini", ".env", ".toml", ".xml", ".csv",
    # 图片文件
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".bmp", ".webp",
    # 其他常用文件
    ".log", ".htm", ".html", ".css", ".sql", ".bat", ".cmd", ".ps1",
}
# 二进制文件类型（不适合文本编辑器打开）
BINARY_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".ico", ".bmp", ".webp"}
# 支持中文文件名
FILENAME_PATTERN = re.compile(r'^[\w\u4e00-\u9fff\-./]+$', re.UNICODE)
MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10MB（支持图片后提高限制）


def _get_mime(ext: str) -> str:
    """根据扩展名返回 MIME 类型"""
    mime_map = {
        ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".gif": "image/gif", ".svg": "image/svg+xml", ".ico": "image/x-icon",
        ".bmp": "image/bmp", ".webp": "image/webp",
    }
    return mime_map.get(ext, "application/octet-stream")


@scripts_bp.route("", methods=["GET"])
@jwt_required()
def list_scripts():
    """获取脚本文件列表"""
    scripts_dir = current_app.config["SCRIPTS_DIR"]
    os.makedirs(scripts_dir, exist_ok=True)

    files = []
    for root, dirs, filenames in os.walk(scripts_dir):
        for fn in filenames:
            ext = os.path.splitext(fn)[1].lower()
            if ext in ALLOWED_EXTENSIONS:
                full = os.path.join(root, fn)
                rel = os.path.relpath(full, scripts_dir).replace("\\", "/")
                stat = os.stat(full)
                files.append({
                    "path": rel,
                    "name": fn,
                    "size": stat.st_size,
                    "mtime": stat.st_mtime,
                })

    files.sort(key=lambda x: x["path"])
    return jsonify({"data": files, "total": len(files)})


@scripts_bp.route("/tree", methods=["GET"])
@jwt_required()
def script_tree():
    """获取脚本文件树结构"""
    scripts_dir = current_app.config["SCRIPTS_DIR"]
    os.makedirs(scripts_dir, exist_ok=True)

    def build_tree(base: str, rel_prefix: str = "") -> list:
        nodes = []
        try:
            entries = sorted(os.listdir(base))
        except OSError:
            return nodes

        dirs = []
        files = []
        for entry in entries:
            full = os.path.join(base, entry)
            rel = f"{rel_prefix}/{entry}" if rel_prefix else entry
            if os.path.isdir(full):
                children = build_tree(full, rel)
                # 显示所有目录，包括空目录
                dirs.append({
                    "key": rel,
                    "title": entry,
                    "isLeaf": False,
                    "type": "directory",
                    "children": children,
                })
            elif os.path.isfile(full):
                ext = os.path.splitext(entry)[1].lower()
                if ext in ALLOWED_EXTENSIONS or not ext:  # 支持无扩展名文件
                    stat = os.stat(full)
                    files.append({
                        "key": rel,
                        "title": entry,
                        "isLeaf": True,
                        "type": "file",
                        "extension": ext,
                        "size": stat.st_size,
                        "mtime": stat.st_mtime,
                    })
        return dirs + files

    tree = build_tree(scripts_dir)
    return jsonify({"data": tree})


@scripts_bp.route("/content", methods=["GET"])
@jwt_required()
def read_script():
    """读取脚本内容

    查询参数:
        path: 脚本相对路径
    """
    path = safe_strip(request.args.get("path", ""))
    if not path:
        return jsonify({"error": "缺少 path 参数"}), 400

    full_path = _safe_path(path)
    if not full_path:
        return jsonify({"error": "非法路径"}), 400
    if not os.path.isfile(full_path):
        return jsonify({"error": "文件不存在"}), 404

    try:
        ext = os.path.splitext(full_path)[1].lower()
        if ext in BINARY_EXTENSIONS:
            # 二进制文件返回 base64 编码
            import base64
            with open(full_path, "rb") as f:
                raw = f.read()
            content = base64.b64encode(raw).decode("ascii")
            return jsonify({"data": {"path": path, "content": content, "binary": True, "mime": _get_mime(ext)}})
        with open(full_path, "r", encoding="utf-8") as f:
            content = f.read()
    except UnicodeDecodeError:
        return jsonify({"error": "文件编码不支持，仅支持 UTF-8"}), 400

    return jsonify({"data": {"path": path, "content": content, "binary": False}})


@scripts_bp.route("/content", methods=["PUT"])
@jwt_required()
def save_script():
    """保存脚本内容（自动记录版本历史）

    请求体:
        path: 脚本相对路径
        content: 脚本内容
        message: 版本备注（可选）
    """
    data = request.get_json(silent=True) or {}
    path = safe_strip(data.get("path"))
    content = data.get("content", "")
    message = data.get("message", "")

    if not path:
        return jsonify({"error": "缺少 path 参数"}), 400

    ext = os.path.splitext(path)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return jsonify({"error": f"不支持的文件类型: {ext}"}), 400

    full_path = _safe_path(path, must_exist=False)
    if not full_path:
        return jsonify({"error": "非法路径"}), 400

    if len(content.encode("utf-8")) > MAX_UPLOAD_SIZE:
        return jsonify({"error": "文件大小超过 10MB 限制"}), 400

    # 写入文件
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    with open(full_path, "w", encoding="utf-8") as f:
        f.write(content)

    # 记录版本历史
    last_version = ScriptVersion.query.filter_by(script_path=path)\
        .order_by(ScriptVersion.version.desc()).first()
    new_version = (last_version.version + 1) if last_version else 1

    sv = ScriptVersion(
        script_path=path,
        content=content,
        version=new_version,
        message=message or f"v{new_version}",
    )
    db.session.add(sv)
    db.session.commit()

    return jsonify({"message": "保存成功", "version": new_version})


@scripts_bp.route("/upload", methods=["POST"])
@jwt_required()
def upload_script():
    """上传脚本文件"""
    if "file" not in request.files:
        return jsonify({"error": "缺少文件"}), 400

    file = request.files["file"]
    if not file.filename:
        return jsonify({"error": "文件名为空"}), 400

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return jsonify({"error": f"不支持的文件类型: {ext}"}), 400

    # 安全文件名
    filename = file.filename.replace("\\", "/")
    if not FILENAME_PATTERN.match(filename):
        return jsonify({"error": "文件名包含非法字符"}), 400

    # 读取内容并检查大小
    content = file.read()
    if len(content) > MAX_UPLOAD_SIZE:
        return jsonify({"error": "文件大小超过 10MB 限制"}), 400

    full_path = _safe_path(filename, must_exist=False)
    if not full_path:
        return jsonify({"error": "非法路径"}), 400

    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    with open(full_path, "wb") as f:
        f.write(content)

    return jsonify({"message": "上传成功", "path": filename}), 201


@scripts_bp.route("", methods=["DELETE"])
@jwt_required()
def delete_script():
    """删除脚本文件或文件夹

    查询参数:
        path: 脚本相对路径
        type: 类型 (file/directory)
    """
    path = safe_strip(request.args.get("path", ""))
    item_type = safe_strip(request.args.get("type", "file"))

    if not path:
        return jsonify({"error": "缺少 path 参数"}), 400

    full_path = _safe_path(path)
    if not full_path:
        return jsonify({"error": "非法路径"}), 400

    if not os.path.exists(full_path):
        return jsonify({"error": "文件或文件夹不存在"}), 404

    try:
        if item_type == "directory" or os.path.isdir(full_path):
            # 删除文件夹及其内容
            import shutil
            shutil.rmtree(full_path)
            return jsonify({"message": "文件夹删除成功"})
        else:
            # 删除文件
            os.remove(full_path)
            return jsonify({"message": "文件删除成功"})
    except Exception as e:
        return jsonify({"error": f"删除失败: {str(e)}"}), 500


@scripts_bp.route("/versions", methods=["GET"])
@jwt_required()
def list_versions():
    """获取脚本版本历史

    查询参数:
        path: 脚本相对路径
    """
    path = safe_strip(request.args.get("path", ""))
    if not path:
        return jsonify({"error": "缺少 path 参数"}), 400

    versions = ScriptVersion.query.filter_by(script_path=path)\
        .order_by(ScriptVersion.version.desc()).limit(50).all()
    return jsonify({"data": [v.to_dict() for v in versions]})


@scripts_bp.route("/versions/<int:version_id>", methods=["GET"])
@jwt_required()
def get_version_content(version_id: int):
    """获取某个版本的内容"""
    sv = ScriptVersion.query.get(version_id)
    if not sv:
        return jsonify({"error": "版本不存在"}), 404
    return jsonify({"data": {"content": sv.content, **sv.to_dict()}})


@scripts_bp.route("/versions/<int:version_id>/rollback", methods=["PUT"])
@jwt_required()
def rollback_version(version_id: int):
    """回滚到指定版本"""
    sv = ScriptVersion.query.get(version_id)
    if not sv:
        return jsonify({"error": "版本不存在"}), 404

    full_path = _safe_path(sv.script_path, must_exist=False)
    if not full_path:
        return jsonify({"error": "非法路径"}), 400

    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    with open(full_path, "w", encoding="utf-8") as f:
        f.write(sv.content)

    # 创建新版本记录
    last = ScriptVersion.query.filter_by(script_path=sv.script_path)\
        .order_by(ScriptVersion.version.desc()).first()
    new_ver = (last.version + 1) if last else 1

    new_sv = ScriptVersion(
        script_path=sv.script_path,
        content=sv.content,
        version=new_ver,
        message=f"回滚到 v{sv.version}",
    )
    db.session.add(new_sv)
    db.session.commit()

    return jsonify({"message": f"已回滚到 v{sv.version}", "version": new_ver})


def _safe_path(rel_path: str, must_exist: bool = True) -> str | None:
    """将相对路径转换为安全的绝对路径，防止目录穿越"""
    if not FILENAME_PATTERN.match(rel_path):
        return None

    scripts_dir = os.path.abspath(current_app.config["SCRIPTS_DIR"])
    full_path = os.path.normpath(os.path.join(scripts_dir, rel_path))

    if not full_path.startswith(scripts_dir):
        return None

    if must_exist and not os.path.exists(full_path):
        return None

    return full_path


# ==================== 文件夹管理 ====================

@scripts_bp.route("/directory", methods=["POST"])
@jwt_required()
def create_directory():
    """创建文件夹

    请求体:
        path: 文件夹相对路径
    """
    data = request.get_json(silent=True) or {}
    path = safe_strip(data.get("path"))

    if not path:
        return jsonify({"error": "缺少 path 参数"}), 400

    if not FILENAME_PATTERN.match(path):
        return jsonify({"error": "路径包含非法字符"}), 400

    full_path = _safe_path(path, must_exist=False)
    if not full_path:
        return jsonify({"error": "非法路径"}), 400

    if os.path.exists(full_path):
        return jsonify({"error": "文件夹已存在"}), 400

    try:
        os.makedirs(full_path, exist_ok=True)
        return jsonify({"message": "文件夹创建成功", "path": path}), 201
    except Exception as e:
        return jsonify({"error": f"创建失败: {str(e)}"}), 500


@scripts_bp.route("/rename", methods=["PUT"])
@jwt_required()
def rename_item():
    """重命名文件或文件夹

    请求体:
        old_path: 原路径
        new_name: 新名称（不含路径）
    """
    data = request.get_json(silent=True) or {}
    old_path = safe_strip(data.get("old_path"))
    new_name = safe_strip(data.get("new_name"))

    if not old_path or not new_name:
        return jsonify({"error": "缺少必要参数"}), 400

    if "/" in new_name or "\\" in new_name:
        return jsonify({"error": "新名称不能包含路径分隔符"}), 400

    if not FILENAME_PATTERN.match(new_name):
        return jsonify({"error": "名称包含非法字符"}), 400

    old_full_path = _safe_path(old_path)
    if not old_full_path:
        return jsonify({"error": "非法路径"}), 400

    if not os.path.exists(old_full_path):
        return jsonify({"error": "文件或文件夹不存在"}), 404

    # 构建新路径
    parent_dir = os.path.dirname(old_full_path)
    new_full_path = os.path.join(parent_dir, new_name)

    # 验证新路径安全性
    scripts_dir = os.path.abspath(current_app.config["SCRIPTS_DIR"])
    if not new_full_path.startswith(scripts_dir):
        return jsonify({"error": "非法路径"}), 400

    if os.path.exists(new_full_path):
        return jsonify({"error": "目标名称已存在"}), 400

    try:
        os.rename(old_full_path, new_full_path)
        # 计算新的相对路径
        new_rel_path = os.path.relpath(new_full_path, scripts_dir).replace("\\", "/")
        return jsonify({"message": "重命名成功", "new_path": new_rel_path})
    except Exception as e:
        return jsonify({"error": f"重命名失败: {str(e)}"}), 500


@scripts_bp.route("/move", methods=["PUT"])
@jwt_required()
def move_item():
    """移动文件或文件夹

    请求体:
        source_path: 源路径
        target_dir: 目标文件夹路径（相对路径，空字符串表示根目录）
    """
    data = request.get_json(silent=True) or {}
    source_path = safe_strip(data.get("source_path"))
    target_dir = safe_strip(data.get("target_dir"))

    if not source_path:
        return jsonify({"error": "缺少 source_path 参数"}), 400

    source_full_path = _safe_path(source_path)
    if not source_full_path:
        return jsonify({"error": "非法源路径"}), 400

    if not os.path.exists(source_full_path):
        return jsonify({"error": "源文件或文件夹不存在"}), 404

    # 处理目标目录
    scripts_dir = current_app.config["SCRIPTS_DIR"]
    if target_dir:
        target_full_dir = _safe_path(target_dir, must_exist=False)
        if not target_full_dir:
            return jsonify({"error": "非法目标路径"}), 400
        os.makedirs(target_full_dir, exist_ok=True)
    else:
        target_full_dir = scripts_dir

    # 构建目标路径
    item_name = os.path.basename(source_full_path)
    target_full_path = os.path.join(target_full_dir, item_name)

    # 验证不是移动到自己的子目录
    if os.path.isdir(source_full_path):
        try:
            if os.path.commonpath([source_full_path, target_full_path]) == source_full_path:
                return jsonify({"error": "不能移动到自己的子目录"}), 400
        except ValueError:
            pass

    if os.path.exists(target_full_path):
        return jsonify({"error": "目标位置已存在同名文件或文件夹"}), 400

    try:
        import shutil
        shutil.move(source_full_path, target_full_path)
        # 计算新的相对路径
        new_rel_path = os.path.relpath(target_full_path, scripts_dir).replace("\\", "/")
        return jsonify({"message": "移动成功", "new_path": new_rel_path})
    except Exception as e:
        return jsonify({"error": f"移动失败: {str(e)}"}), 500


@scripts_bp.route("/copy", methods=["POST"])
@jwt_required()
def copy_item():
    """复制文件或文件夹

    请求体:
        source_path: 源路径
        target_dir: 目标文件夹路径（相对路径，空字符串表示根目录）
        new_name: 新名称（可选，不提供则使用原名称）
    """
    data = request.get_json(silent=True) or {}
    source_path = safe_strip(data.get("source_path"))
    target_dir = safe_strip(data.get("target_dir"))
    new_name = safe_strip(data.get("new_name"))

    if not source_path:
        return jsonify({"error": "缺少 source_path 参数"}), 400

    source_full_path = _safe_path(source_path)
    if not source_full_path:
        return jsonify({"error": "非法源路径"}), 400

    if not os.path.exists(source_full_path):
        return jsonify({"error": "源文件或文件夹不存在"}), 404

    # 处理目标目录
    scripts_dir = current_app.config["SCRIPTS_DIR"]
    if target_dir:
        target_full_dir = _safe_path(target_dir, must_exist=False)
        if not target_full_dir:
            return jsonify({"error": "非法目标路径"}), 400
        os.makedirs(target_full_dir, exist_ok=True)
    else:
        target_full_dir = scripts_dir

    # 确定目标名称
    if new_name:
        if "/" in new_name or "\\" in new_name:
            return jsonify({"error": "新名称不能包含路径分隔符"}), 400
        if not FILENAME_PATTERN.match(new_name):
            return jsonify({"error": "名称包含非法字符"}), 400
        item_name = new_name
    else:
        item_name = os.path.basename(source_full_path)

    target_full_path = os.path.join(target_full_dir, item_name)

    if os.path.exists(target_full_path):
        return jsonify({"error": "目标位置已存在同名文件或文件夹"}), 400

    try:
        import shutil
        if os.path.isdir(source_full_path):
            shutil.copytree(source_full_path, target_full_path)
        else:
            shutil.copy2(source_full_path, target_full_path)

        # 计算新的相对路径
        new_rel_path = os.path.relpath(target_full_path, scripts_dir).replace("\\", "/")
        return jsonify({"message": "复制成功", "new_path": new_rel_path}), 201
    except Exception as e:
        return jsonify({"error": f"复制失败: {str(e)}"}), 500


@scripts_bp.route("/batch", methods=["DELETE"])
@jwt_required()
def batch_delete():
    """批量删除文件或文件夹

    请求体:
        paths: 路径列表 [{"path": "xxx", "type": "file/directory"}, ...]
    """
    data = request.get_json(silent=True) or {}
    paths = data.get("paths", [])

    if not paths or not isinstance(paths, list):
        return jsonify({"error": "缺少 paths 参数或格式错误"}), 400

    success_count = 0
    failed_items = []

    for item in paths:
        path = safe_strip(item.get("path"))
        item_type = item.get("type", "file")

        if not path:
            continue

        full_path = _safe_path(path)
        if not full_path or not os.path.exists(full_path):
            failed_items.append({"path": path, "reason": "路径无效或不存在"})
            continue

        try:
            if item_type == "directory" or os.path.isdir(full_path):
                import shutil
                shutil.rmtree(full_path)
            else:
                os.remove(full_path)
            success_count += 1
        except Exception as e:
            failed_items.append({"path": path, "reason": str(e)})

    return jsonify({
        "message": f"成功删除 {success_count} 项",
        "success_count": success_count,
        "failed_count": len(failed_items),
        "failed_items": failed_items
    })


# ==================== 脚本调试运行 ====================
    """将相对路径转换为安全的绝对路径，防止目录穿越"""
    if not FILENAME_PATTERN.match(rel_path):
        return None

    scripts_dir = os.path.abspath(current_app.config["SCRIPTS_DIR"])
    full_path = os.path.normpath(os.path.join(scripts_dir, rel_path))

    if not full_path.startswith(scripts_dir):
        return None

    if must_exist and not os.path.exists(full_path):
        return None

    return full_path


# ==================== 脚本调试运行 ====================

# 存储运行中的脚本进程和日志 {run_id: {"process": Popen, "logs": [], "done": bool}}
_debug_runs = {}
_debug_lock = threading.Lock()


@scripts_bp.route("/run", methods=["POST"])
@jwt_required()
def run_script():
    """调试运行脚本

    请求体:
        path: 脚本相对路径

    返回:
        run_id: 运行ID，用于获取日志
    """
    data = request.get_json(silent=True) or {}
    path = safe_strip(data.get("path"))

    if not path:
        return jsonify({"error": "缺少 path 参数"}), 400

    full_path = _safe_path(path)
    if not full_path:
        return jsonify({"error": "非法路径"}), 400
    if not os.path.isfile(full_path):
        return jsonify({"error": "文件不存在"}), 404

    # 确定执行命令
    ext = os.path.splitext(path)[1].lower()
    if ext == ".py":
        # Python 添加 -u 参数禁用缓冲，实现实时输出
        cmd = ["python", "-u", full_path]
    elif ext == ".js":
        cmd = ["node", full_path]
    elif ext == ".ts":
        cmd = ["ts-node", full_path]
    elif ext == ".sh":
        cmd = ["bash", full_path]
    else:
        return jsonify({"error": f"不支持的脚本类型: {ext}"}), 400

    # 加载环境变量（只使用项目配置的环境变量，但保留必要的系统变量）
    from app.models.env_var import EnvVar

    # 只保留必要的系统环境变量（PATH、SYSTEMROOT等）
    env_vars = {}
    for key in ['PATH', 'SYSTEMROOT', 'PATHEXT', 'TEMP', 'TMP']:
        if key in os.environ:
            env_vars[key] = os.environ[key]

    # 添加项目配置的环境变量
    enabled_envs = EnvVar.query.filter_by(enabled=True).all()
    for env in enabled_envs:
        env_vars[env.name] = env.value

    # 生成运行ID
    run_id = f"{int(time.time() * 1000)}_{os.path.basename(path)}"

    # 启动进程
    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            encoding='utf-8',
            errors='replace',
            bufsize=1,
            universal_newlines=True,
            env=env_vars,  # 使用精简的环境变量
            cwd=os.path.dirname(full_path) or current_app.config["SCRIPTS_DIR"],
        )
    except FileNotFoundError as e:
        return jsonify({"error": f"执行器未找到: {e}"}), 500
    except Exception as e:
        return jsonify({"error": f"启动失败: {e}"}), 500

    # 存储运行信息
    with _debug_lock:
        _debug_runs[run_id] = {
            "process": process,
            "logs": [f"[{datetime.now().strftime('%H:%M:%S')}] 开始执行: {path}\n"],
            "done": False,
            "exit_code": None,
            "status": "running",  # running, success, failed, stopped
            "start_time": time.time(),
        }

    # 启动日志收集线程
    def collect_logs():
        with _debug_lock:
            run_info = _debug_runs.get(run_id)
            if not run_info:
                return
            process = run_info["process"]
            start_time = run_info["start_time"]

        try:
            for line in process.stdout:
                with _debug_lock:
                    if run_id in _debug_runs:
                        _debug_runs[run_id]["logs"].append(line)
        except Exception:
            pass

        # 等待进程结束
        exit_code = process.wait()
        elapsed = time.time() - start_time

        with _debug_lock:
            if run_id in _debug_runs:
                _debug_runs[run_id]["done"] = True
                _debug_runs[run_id]["exit_code"] = exit_code

                # 根据退出码判断成功或失败
                if exit_code == 0:
                    status_msg = "执行成功"
                    _debug_runs[run_id]["status"] = "success"
                else:
                    status_msg = "执行失败"
                    _debug_runs[run_id]["status"] = "failed"

                _debug_runs[run_id]["logs"].append(
                    f"\n[{datetime.now().strftime('%H:%M:%S')}] "
                    f"{status_msg}，退出码: {exit_code}，耗时: {elapsed:.2f}秒\n"
                )

    thread = threading.Thread(target=collect_logs, daemon=True)
    thread.start()

    return jsonify({"message": "脚本已启动", "run_id": run_id}), 201


@scripts_bp.route("/run/<run_id>/logs", methods=["GET"])
@jwt_required()
def get_run_logs(run_id: str):
    """获取运行日志

    返回:
        logs: 日志行列表
        done: 是否执行完成
        exit_code: 退出码（完成时）
        status: 运行状态 (running, success, failed, stopped)
    """
    with _debug_lock:
        run_info = _debug_runs.get(run_id)
        if not run_info:
            return jsonify({"error": "运行记录不存在"}), 404

        return jsonify({
            "logs": run_info["logs"][:],
            "done": run_info["done"],
            "exit_code": run_info.get("exit_code"),
            "status": run_info.get("status", "running"),
        })


@scripts_bp.route("/run/<run_id>/stop", methods=["PUT"])
@jwt_required()
def stop_run(run_id: str):
    """停止运行中的脚本"""
    with _debug_lock:
        run_info = _debug_runs.get(run_id)
        if not run_info:
            return jsonify({"error": "运行记录不存在"}), 404

        if run_info["done"]:
            return jsonify({"error": "脚本已执行完成"}), 400

        process = run_info["process"]
        try:
            process.terminate()
            run_info["logs"].append(f"\n[{datetime.now().strftime('%H:%M:%S')}] 脚本已被手动停止\n")
            run_info["done"] = True
            run_info["exit_code"] = -1
            run_info["status"] = "stopped"
        except Exception as e:
            return jsonify({"error": f"停止失败: {e}"}), 500

    return jsonify({"message": "脚本已停止"})


@scripts_bp.route("/run/<run_id>", methods=["DELETE"])
@jwt_required()
def clear_run(run_id: str):
    """清除运行记录"""
    with _debug_lock:
        if run_id not in _debug_runs:
            return jsonify({"error": "运行记录不存在"}), 404

        run_info = _debug_runs[run_id]
        if not run_info["done"]:
            # 如果还在运行，先停止
            try:
                run_info["process"].terminate()
            except Exception:
                pass

        del _debug_runs[run_id]

    return jsonify({"message": "记录已清除"})


# ==================== 代码格式化 ====================

@scripts_bp.route("/format", methods=["POST"])
@jwt_required()
def format_code():
    """格式化代码

    请求体:
        content: 代码内容
        language: 语言类型 (python/shell/json)
        formatter: 格式化工具 (可选)
            - python: black/autopep8 (默认 black)
    """
    data = request.get_json(silent=True) or {}
    content = data.get("content", "")
    language = data.get("language", "").lower()
    formatter = data.get("formatter", "").lower()

    if not content:
        return jsonify({"error": "代码内容不能为空"}), 400

    if not language:
        return jsonify({"error": "语言类型不能为空"}), 400

    try:
        if language == "python":
            formatted = _format_python(content, formatter or "black")
        elif language == "shell":
            formatted = _format_shell(content)
        elif language == "json":
            formatted = _format_json(content)
        else:
            return jsonify({"error": f"不支持的语言类型: {language}"}), 400

        return jsonify({
            "data": {
                "content": formatted,
                "language": language,
                "formatter": formatter or "default"
            }
        })
    except Exception as e:
        return jsonify({"error": f"格式化失败: {str(e)}"}), 500


def _format_python(content: str, formatter: str) -> str:
    """格式化 Python 代码"""
    if formatter == "black":
        try:
            import black
            # 使用 black 格式化
            formatted = black.format_str(content, mode=black.Mode(
                line_length=88,
                string_normalization=True,
            ))
            return formatted
        except ImportError:
            # 如果 black 未安装，降级到 autopep8
            formatter = "autopep8"
        except Exception as e:
            raise Exception(f"Black 格式化失败: {str(e)}")

    if formatter == "autopep8":
        try:
            import autopep8
            # 使用 autopep8 格式化
            formatted = autopep8.fix_code(content, options={
                'max_line_length': 88,
                'aggressive': 1,
            })
            return formatted
        except ImportError:
            raise Exception("autopep8 未安装")
        except Exception as e:
            raise Exception(f"autopep8 格式化失败: {str(e)}")

    raise Exception(f"不支持的 Python 格式化工具: {formatter}")


def _format_shell(content: str) -> str:
    """格式化 Shell 脚本

    使用 shfmt 命令行工具（如果可用）
    否则返回基础格式化
    """
    import subprocess
    import tempfile
    import os

    try:
        # 尝试使用 shfmt
        with tempfile.NamedTemporaryFile(mode='w', suffix='.sh', delete=False, encoding='utf-8') as f:
            f.write(content)
            temp_path = f.name

        try:
            # 调用 shfmt 格式化
            result = subprocess.run(
                ['shfmt', '-i', '2', '-bn', '-ci', '-sr', temp_path],
                capture_output=True,
                text=True,
                timeout=5,
                encoding='utf-8'
            )

            if result.returncode == 0:
                return result.stdout
            else:
                # shfmt 失败，返回基础格式化
                return _format_shell_basic(content)
        finally:
            os.unlink(temp_path)

    except (FileNotFoundError, subprocess.TimeoutExpired):
        # shfmt 未安装或超时，使用基础格式化
        return _format_shell_basic(content)
    except Exception as e:
        raise Exception(f"Shell 格式化失败: {str(e)}")


def _format_shell_basic(content: str) -> str:
    """Shell 基础格式化（移除行尾空格）"""
    lines = content.split('\n')
    return '\n'.join(line.rstrip() for line in lines)


def _format_json(content: str) -> str:
    """格式化 JSON"""
    import json
    try:
        obj = json.loads(content)
        return json.dumps(obj, indent=2, ensure_ascii=False, sort_keys=False)
    except json.JSONDecodeError as e:
        raise Exception(f"JSON 格式错误: {str(e)}")
