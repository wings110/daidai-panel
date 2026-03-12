"""订阅管理接口"""

import os
import re
import shutil
import subprocess
import logging
from datetime import datetime
from fnmatch import fnmatch

from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required

from app.extensions import db
from app.models.subscription import Subscription
from app.utils.validators import safe_strip, safe_str

logger = logging.getLogger(__name__)
subs_bp = Blueprint("subscriptions", __name__)

URL_PATTERN = re.compile(r'^https?://[\w\-._~:/?#\[\]@!$&\'()*+,;=%]+$')


@subs_bp.route("", methods=["GET"])
@jwt_required()
def list_subs():
    """获取订阅列表"""
    subs = Subscription.query.order_by(Subscription.created_at.desc()).all()
    return jsonify({"data": [s.to_dict() for s in subs]})


@subs_bp.route("", methods=["POST"])
@jwt_required()
def create_sub():
    """创建订阅

    请求体:
        name: 名称
        url: 仓库地址（HTTP/HTTPS）
        branch: 分支（默认 main）
        schedule: Cron 表达式
        whitelist: 白名单 glob（可选）
        blacklist: 黑名单 glob（可选）
        target_dir: 存放子目录（可选）
    """
    try:
        data = request.get_json(silent=True) or {}
        name = safe_strip(data.get("name"))
        url = safe_strip(data.get("url"))

        if not name:
            return jsonify({"error": "名称不能为空"}), 400
        if not url or not URL_PATTERN.match(url):
            return jsonify({"error": "仓库地址必须是有效的 HTTP/HTTPS URL"}), 400

        sub_type = safe_strip(data.get("sub_type", "git"))
        if sub_type not in ("git", "file"):
            return jsonify({"error": "类型必须是 git 或 file"}), 400

        sub = Subscription(
            name=name,
            url=url,
            sub_type=sub_type,
            branch=safe_strip(data.get("branch", "main")) or "main",
            schedule=safe_strip(data.get("schedule", "0 0 * * *")),
            whitelist=safe_str(data.get("whitelist")),
            blacklist=safe_str(data.get("blacklist")),
            target_dir=_sanitize_dir(safe_str(data.get("target_dir"))),
        )
        db.session.add(sub)
        db.session.commit()

        return jsonify({"message": "创建成功", "data": sub.to_dict()}), 201
    except Exception as e:
        db.session.rollback()
        logger.error(f"创建订阅失败: {e}", exc_info=True)
        return jsonify({"error": f"创建失败: {str(e)}"}), 500


@subs_bp.route("/<int:sub_id>", methods=["PUT"])
@jwt_required()
def update_sub(sub_id: int):
    """更新订阅"""
    try:
        sub = Subscription.query.get(sub_id)
        if not sub:
            return jsonify({"error": "订阅不存在"}), 404

        data = request.get_json(silent=True) or {}
        if "name" in data:
            sub.name = safe_strip(data["name"])
        if "url" in data:
            url = safe_strip(data["url"])
            if not URL_PATTERN.match(url):
                return jsonify({"error": "仓库地址必须是有效的 HTTP/HTTPS URL"}), 400
            sub.url = url
        if "branch" in data:
            sub.branch = safe_strip(data["branch"]) or "main"
        if "schedule" in data:
            sub.schedule = safe_strip(data["schedule"])
        if "whitelist" in data:
            sub.whitelist = safe_str(data["whitelist"])
        if "blacklist" in data:
            sub.blacklist = safe_str(data["blacklist"])
        if "target_dir" in data:
            sub.target_dir = _sanitize_dir(safe_str(data["target_dir"]))
        if "sub_type" in data:
            sub.sub_type = data["sub_type"]
        if "enabled" in data:
            sub.enabled = data["enabled"]

        db.session.commit()
        return jsonify({"message": "更新成功", "data": sub.to_dict()})
    except Exception as e:
        db.session.rollback()
        logger.error(f"更新订阅失败: {e}", exc_info=True)
        return jsonify({"error": f"更新失败: {str(e)}"}), 500


@subs_bp.route("/<int:sub_id>", methods=["DELETE"])
@jwt_required()
def delete_sub(sub_id: int):
    """删除订阅"""
    try:
        sub = Subscription.query.get(sub_id)
        if not sub:
            return jsonify({"error": "订阅不存在"}), 404

        db.session.delete(sub)
        db.session.commit()
        return jsonify({"message": "删除成功"})
    except Exception as e:
        db.session.rollback()
        logger.error(f"删除订阅失败: {e}", exc_info=True)
        return jsonify({"error": f"删除失败: {str(e)}"}), 500


@subs_bp.route("/<int:sub_id>/pull", methods=["POST"])
@jwt_required()
def pull_sub(sub_id: int):
    """手动拉取订阅"""
    sub = Subscription.query.get(sub_id)
    if not sub:
        return jsonify({"error": "订阅不存在"}), 404

    result = _do_pull(sub)
    return jsonify(result)


def _do_pull(sub: Subscription) -> dict:
    """执行订阅拉取（根据类型分发）并记录日志"""
    from app.models.sub_log import SubLog

    if (sub.sub_type or "git") == "file":
        result = _do_pull_file(sub)
    else:
        result = _do_pull_git(sub)

    # 记录订阅拉取日志
    log = SubLog(
        sub_id=sub.id,
        sub_name=sub.name,
        status=0 if "message" in result else 1,
        message=result.get("message") or result.get("error", ""),
    )
    db.session.add(log)
    db.session.commit()

    return result


def _do_pull_file(sub: Subscription) -> dict:
    """单文件订阅：从远程 URL 下载单个脚本文件"""
    from urllib.request import Request, urlopen
    from urllib.error import URLError
    from app.models.system_config import SystemConfig

    scripts_dir = current_app.config["SCRIPTS_DIR"]
    proxy_url = SystemConfig.get("proxy_url")

    try:
        # 从 URL 中提取文件名
        from urllib.parse import urlparse
        parsed = urlparse(sub.url)
        filename = os.path.basename(parsed.path) or "downloaded_script.py"

        # 构建代理
        if proxy_url:
            from urllib.request import ProxyHandler, build_opener
            proxy_handler = ProxyHandler({
                "http": proxy_url,
                "https": proxy_url,
            })
            opener = build_opener(proxy_handler)
        else:
            from urllib.request import build_opener
            opener = build_opener()

        req = Request(sub.url, headers={"User-Agent": "DaidaiPanel/1.0"})
        with opener.open(req, timeout=30) as resp:
            content = resp.read()

        if len(content) > 1 * 1024 * 1024:
            sub.last_pull_status = 1
            sub.last_pull_message = "文件过大（>1MB）"
            sub.last_pull_at = datetime.utcnow()
            db.session.commit()
            return {"error": "文件过大"}

        # 保存文件
        target = os.path.join(scripts_dir, sub.target_dir) if sub.target_dir else scripts_dir
        os.makedirs(target, exist_ok=True)
        dst = os.path.join(target, filename)
        with open(dst, "wb") as f:
            f.write(content)

        sub.last_pull_status = 0
        sub.last_pull_message = f"成功：下载 {filename}（{len(content)} 字节）"
        sub.last_pull_at = datetime.utcnow()
        db.session.commit()

        return {"message": f"下载成功：{filename}"}

    except URLError as e:
        sub.last_pull_status = 1
        sub.last_pull_message = f"下载失败：{e.reason}"
        sub.last_pull_at = datetime.utcnow()
        db.session.commit()
        return {"error": f"下载失败: {e.reason}"}
    except Exception as e:
        sub.last_pull_status = 1
        sub.last_pull_message = str(e)[:2000]
        sub.last_pull_at = datetime.utcnow()
        db.session.commit()
        return {"error": f"下载异常: {str(e)[:200]}"}


def _do_pull_git(sub: Subscription) -> dict:
    """Git 仓库订阅拉取（集成系统配置：代理、文件后缀过滤、自动增删定时任务）"""
    from app.models.system_config import SystemConfig
    from app.models.task import Task

    scripts_dir = current_app.config["SCRIPTS_DIR"]
    temp_dir = os.path.join(current_app.config["DATA_DIR"], "tmp_clone")

    # 读取系统配置
    proxy_url = SystemConfig.get("proxy_url")
    repo_extensions = SystemConfig.get("repo_file_extensions").split()
    auto_add = SystemConfig.get_bool("auto_add_cron")
    auto_del = SystemConfig.get_bool("auto_del_cron")
    default_cron = SystemConfig.get("default_cron_rule") or "0 9 * * *"

    try:
        # 清理临时目录
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)

        # 构建 Git 环境（代理支持）
        env = os.environ.copy()
        if proxy_url:
            env["http_proxy"] = proxy_url
            env["https_proxy"] = proxy_url

        # 克隆仓库（浅拷贝，限制深度）
        result = subprocess.run(
            ["git", "clone", "--depth", "1", "--branch", sub.branch, sub.url, temp_dir],
            capture_output=True,
            text=True,
            timeout=120,
            env=env,
        )

        if result.returncode != 0:
            sub.last_pull_status = 1
            sub.last_pull_message = result.stderr[:2000]
            sub.last_pull_at = datetime.utcnow()
            db.session.commit()
            return {"error": "拉取失败", "detail": result.stderr[:500]}, 500

        # 目标目录
        target = os.path.join(scripts_dir, sub.target_dir) if sub.target_dir else scripts_dir
        os.makedirs(target, exist_ok=True)

        # 解析白名单/黑名单
        whitelist = [p.strip() for p in sub.whitelist.split(",") if p.strip()] if sub.whitelist else None
        blacklist = [p.strip() for p in sub.blacklist.split(",") if p.strip()] if sub.blacklist else []

        # 记录拉取前已有脚本（用于 auto_del）
        old_scripts = set()
        if auto_del:
            tasks = Task.query.filter(Task.command.like(f"sub_{sub.id}/%")).all()
            old_scripts = {t.command for t in tasks}

        # 复制匹配的文件
        copied = 0
        new_scripts: list[str] = []
        for root, dirs, files in os.walk(temp_dir):
            # 跳过 .git 目录
            dirs[:] = [d for d in dirs if d != ".git"]
            for fn in files:
                # 文件后缀过滤（系统配置的 repo_file_extensions）
                ext = fn.rsplit(".", 1)[-1] if "." in fn else ""
                if repo_extensions and ext not in repo_extensions:
                    continue

                src = os.path.join(root, fn)
                rel = os.path.relpath(src, temp_dir).replace("\\", "/")

                # 白名单过滤
                if whitelist and not any(fnmatch(rel, w) for w in whitelist):
                    continue
                # 黑名单过滤
                if any(fnmatch(rel, b) for b in blacklist):
                    continue

                dst = os.path.join(target, rel)
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copy2(src, dst)
                copied += 1

                # 记录脚本命令标识（用于自动建任务）
                script_cmd = f"sub_{sub.id}/{rel}"
                new_scripts.append(script_cmd)

        # 自动创建定时任务
        added_tasks = 0
        if auto_add:
            for cmd in new_scripts:
                existing = Task.query.filter_by(command=cmd).first()
                if not existing:
                    task = Task(
                        name=f"[订阅] {cmd.split('/')[-1]}",
                        command=cmd,
                        schedule=default_cron,
                        status=Task.STATUS_DISABLED,
                    )
                    db.session.add(task)
                    added_tasks += 1

        # 自动删除失效定时任务
        removed_tasks = 0
        if auto_del and old_scripts:
            new_set = set(new_scripts)
            for old_cmd in old_scripts:
                if old_cmd not in new_set:
                    task = Task.query.filter_by(command=old_cmd).first()
                    if task:
                        db.session.delete(task)
                        removed_tasks += 1

        msg_parts = [f"拉取 {copied} 个文件"]
        if added_tasks:
            msg_parts.append(f"新增 {added_tasks} 个任务")
        if removed_tasks:
            msg_parts.append(f"清理 {removed_tasks} 个失效任务")

        sub.last_pull_status = 0
        sub.last_pull_message = "成功：" + "，".join(msg_parts)
        sub.last_pull_at = datetime.utcnow()
        db.session.commit()

        return {"message": "拉取成功，" + "，".join(msg_parts)}

    except subprocess.TimeoutExpired:
        sub.last_pull_status = 1
        sub.last_pull_message = "拉取超时（120s）"
        sub.last_pull_at = datetime.utcnow()
        db.session.commit()
        return {"error": "拉取超时"}

    except Exception as e:
        sub.last_pull_status = 1
        sub.last_pull_message = str(e)[:2000]
        sub.last_pull_at = datetime.utcnow()
        db.session.commit()
        return {"error": f"拉取异常: {str(e)[:200]}"}

    finally:
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)


@subs_bp.route("/logs", methods=["GET"])
@jwt_required()
def list_sub_logs():
    """获取订阅拉取日志

    查询参数:
        sub_id: 订阅 ID（可选）
        page: 页码
        page_size: 每页数量
    """
    from app.models.sub_log import SubLog

    sub_id = request.args.get("sub_id", type=int)
    page = request.args.get("page", 1, type=int)
    page_size = request.args.get("page_size", 20, type=int)

    query = SubLog.query
    if sub_id:
        query = query.filter_by(sub_id=sub_id)

    query = query.order_by(SubLog.created_at.desc())
    pagination = query.paginate(page=page, per_page=page_size, error_out=False)

    return jsonify({
        "data": [l.to_dict() for l in pagination.items],
        "total": pagination.total,
        "page": page,
        "page_size": page_size,
    })


def _sanitize_dir(d: str) -> str:
    """清理子目录名，防止路径穿越"""
    d = d.strip().replace("\\", "/").strip("/")
    parts = [p for p in d.split("/") if p and p != ".." and p != "."]
    return "/".join(parts)
