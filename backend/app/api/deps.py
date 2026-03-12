"""依赖管理接口（pip / npm 包安装）"""

import subprocess
import logging

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required

from app.models.system_config import SystemConfig
from app.utils.command_validator import validate_package_name
from app.utils.validators import safe_strip

logger = logging.getLogger(__name__)
deps_bp = Blueprint("deps", __name__)


@deps_bp.route("/python", methods=["GET"])
@jwt_required()
def list_python_deps():
    """列出已安装的 Python 包"""
    try:
        result = subprocess.run(
            ["pip", "list", "--format=json"],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0:
            import json
            packages = json.loads(result.stdout)
            return jsonify({"data": packages, "total": len(packages)})
        return jsonify({"error": result.stderr[:500]}), 500
    except subprocess.TimeoutExpired:
        return jsonify({"error": "命令超时"}), 500
    except FileNotFoundError:
        return jsonify({"error": "pip 未找到"}), 500


@deps_bp.route("/python", methods=["POST"])
@jwt_required()
def install_python_dep():
    """安装 Python 包

    请求体:
        name: 包名（如 requests 或 requests==2.31.0）
        names: 包名列表（批量安装）
    """
    data = request.get_json(silent=True) or {}
    name = safe_strip(data.get("name"))
    names = data.get("names", [])

    # 批量安装
    if names and isinstance(names, list):
        results = []
        for pkg_name in names:
            pkg_name = safe_strip(pkg_name)
            if not pkg_name or not validate_package_name(pkg_name):
                results.append({"name": pkg_name, "success": False, "error": "包名格式不合法"})
                continue

            try:
                registry = safe_strip(SystemConfig.get("python_registry", ""))
                # 使用参数列表，防止命令注入
                cmd = ["pip", "install", pkg_name]
                if registry:
                    # 验证 registry URL 格式
                    if registry.startswith(('http://', 'https://')):
                        cmd.extend(["-i", registry])

                result = subprocess.run(
                    cmd,
                    capture_output=True, text=True, timeout=120,
                )
                if result.returncode == 0:
                    results.append({"name": pkg_name, "success": True})
                else:
                    results.append({"name": pkg_name, "success": False, "error": result.stderr[-200:]})
            except subprocess.TimeoutExpired:
                results.append({"name": pkg_name, "success": False, "error": "安装超时"})
            except Exception as e:
                results.append({"name": pkg_name, "success": False, "error": str(e)})

        success_count = sum(1 for r in results if r["success"])
        return jsonify({
            "message": f"批量安装完成，成功 {success_count}/{len(names)} 个",
            "results": results
        })

    # 单个安装
    if not name or not validate_package_name(name):
        return jsonify({"error": "包名格式不合法"}), 400

    try:
        # 获取配置的镜像源
        registry = safe_strip(SystemConfig.get("python_registry", ""))
        cmd = ["pip", "install", name]
        if registry and registry.startswith(('http://', 'https://')):
            cmd.extend(["-i", registry])

        result = subprocess.run(
            cmd,
            capture_output=True, text=True, timeout=120,
        )
        if result.returncode == 0:
            return jsonify({"message": f"安装成功: {name}", "output": result.stdout[-500:]})
        return jsonify({"error": f"安装失败: {result.stderr[-500:]}"}), 500
    except subprocess.TimeoutExpired:
        return jsonify({"error": "安装超时"}), 500


@deps_bp.route("/python", methods=["DELETE"])
@jwt_required()
def uninstall_python_dep():
    """卸载 Python 包

    查询参数:
        name: 包名
    """
    name = safe_strip(request.args.get("name", ""))
    if not name or not validate_package_name(name):
        return jsonify({"error": "包名格式不合法"}), 400

    try:
        result = subprocess.run(
            ["pip", "uninstall", "-y", name],
            capture_output=True, text=True, timeout=60,
        )
        if result.returncode == 0:
            return jsonify({"message": f"卸载成功: {name}"})
        return jsonify({"error": f"卸载失败: {result.stderr[-500:]}"}), 500
    except subprocess.TimeoutExpired:
        return jsonify({"error": "卸载超时"}), 500


@deps_bp.route("/node", methods=["GET"])
@jwt_required()
def list_node_deps():
    """列出已安装的全局 Node 包"""
    try:
        result = subprocess.run(
            ["npm", "list", "-g", "--json", "--depth=0"],
            capture_output=True, text=True, timeout=30,
        )
        import json
        data = json.loads(result.stdout) if result.stdout else {}
        deps = data.get("dependencies", {})
        packages = [{"name": k, "version": v.get("version", "")} for k, v in deps.items()]
        return jsonify({"data": packages, "total": len(packages)})
    except subprocess.TimeoutExpired:
        return jsonify({"error": "命令超时"}), 500
    except FileNotFoundError:
        return jsonify({"error": "npm 未找到"}), 500
    except Exception:
        return jsonify({"data": [], "total": 0})


@deps_bp.route("/node", methods=["POST"])
@jwt_required()
def install_node_dep():
    """安装全局 Node 包

    请求体:
        name: 包名
    """
    data = request.get_json(silent=True) or {}
    name = safe_strip(data.get("name"))

    if not name or not validate_package_name(name):
        return jsonify({"error": "包名格式不合法"}), 400

    try:
        # 获取配置的镜像源
        registry = safe_strip(SystemConfig.get("node_registry", ""))
        cmd = ["npm", "install", "-g", name]
        if registry:
            cmd.extend(["--registry", registry])

        result = subprocess.run(
            cmd,
            capture_output=True, text=True, timeout=120,
        )
        if result.returncode == 0:
            return jsonify({"message": f"安装成功: {name}", "output": result.stdout[-500:]})
        return jsonify({"error": f"安装失败: {result.stderr[-500:]}"}), 500
    except subprocess.TimeoutExpired:
        return jsonify({"error": "安装超时"}), 500


@deps_bp.route("/node", methods=["DELETE"])
@jwt_required()
def uninstall_node_dep():
    """卸载全局 Node 包"""
    name = safe_strip(request.args.get("name", ""))
    if not name or not validate_package_name(name):
        return jsonify({"error": "包名格式不合法"}), 400

    try:
        result = subprocess.run(
            ["npm", "uninstall", "-g", name],
            capture_output=True, text=True, timeout=60,
        )
        if result.returncode == 0:
            return jsonify({"message": f"卸载成功: {name}"})
        return jsonify({"error": f"卸载失败: {result.stderr[-500:]}"}), 500
    except subprocess.TimeoutExpired:
        return jsonify({"error": "卸载超时"}), 500


@deps_bp.route("/python/batch", methods=["DELETE"])
@jwt_required()
def batch_uninstall_python():
    """批量卸载 Python 包"""
    data = request.get_json(silent=True) or {}
    names = data.get("names", [])

    if not names or not isinstance(names, list):
        return jsonify({"error": "请提供包名列表"}), 400

    results = []
    for name in names:
        name = safe_strip(name)
        if not name or not validate_package_name(name):
            results.append({"name": name, "success": False, "error": "包名格式不合法"})
            continue

        try:
            result = subprocess.run(
                ["pip", "uninstall", "-y", name],
                capture_output=True, text=True, timeout=60,
            )
            if result.returncode == 0:
                results.append({"name": name, "success": True})
            else:
                results.append({"name": name, "success": False, "error": result.stderr[-200:]})
        except subprocess.TimeoutExpired:
            results.append({"name": name, "success": False, "error": "卸载超时"})
        except Exception as e:
            results.append({"name": name, "success": False, "error": str(e)})

    success_count = sum(1 for r in results if r["success"])
    return jsonify({
        "message": f"批量卸载完成，成功 {success_count}/{len(names)} 个",
        "results": results
    })

