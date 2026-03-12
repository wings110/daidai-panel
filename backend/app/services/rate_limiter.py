"""API 限流服务"""

import time
from functools import wraps
from flask import request, jsonify
from collections import defaultdict
from datetime import datetime, timedelta

# 简单的内存限流器（生产环境建议使用 Redis）
_rate_limit_store = defaultdict(list)


def rate_limit(max_requests: int, window_seconds: int, key_func=None):
    """
    API 限流装饰器

    Args:
        max_requests: 时间窗口内最大请求数
        window_seconds: 时间窗口（秒）
        key_func: 自定义 key 生成函数，默认使用 IP + 路径
    """
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            # 生成限流 key
            if key_func:
                key = key_func()
            else:
                ip = request.remote_addr or "unknown"
                path = request.path
                key = f"{ip}:{path}"

            now = time.time()

            # 清理过期记录
            _rate_limit_store[key] = [
                t for t in _rate_limit_store[key]
                if now - t < window_seconds
            ]

            # 检查是否超过限制
            if len(_rate_limit_store[key]) >= max_requests:
                oldest = _rate_limit_store[key][0]
                retry_after = int(window_seconds - (now - oldest)) + 1
                return jsonify({
                    "error": "请求过于频繁，请稍后再试",
                    "retry_after": retry_after
                }), 429

            # 记录本次请求
            _rate_limit_store[key].append(now)

            return f(*args, **kwargs)
        return wrapped
    return decorator


def get_user_rate_limit_key():
    """基于用户的限流 key"""
    from flask_jwt_extended import get_jwt_identity
    try:
        identity = get_jwt_identity()
        return f"user:{identity}:{request.path}"
    except:
        ip = request.remote_addr or "unknown"
        return f"ip:{ip}:{request.path}"


def clean_rate_limit_store():
    """清理过期的限流记录"""
    now = time.time()
    keys_to_delete = []

    for key, timestamps in _rate_limit_store.items():
        # 清理 1 小时前的记录
        _rate_limit_store[key] = [t for t in timestamps if now - t < 3600]
        if not _rate_limit_store[key]:
            keys_to_delete.append(key)

    for key in keys_to_delete:
        del _rate_limit_store[key]


# API 调用统计
_api_stats = defaultdict(lambda: {"count": 0, "errors": 0, "total_time": 0.0})


def record_api_call(endpoint: str, duration: float, success: bool = True):
    """记录 API 调用统计"""
    _api_stats[endpoint]["count"] += 1
    _api_stats[endpoint]["total_time"] += duration
    if not success:
        _api_stats[endpoint]["errors"] += 1


def get_api_stats():
    """获取 API 调用统计"""
    stats = []
    for endpoint, data in _api_stats.items():
        avg_time = data["total_time"] / data["count"] if data["count"] > 0 else 0
        stats.append({
            "endpoint": endpoint,
            "count": data["count"],
            "errors": data["errors"],
            "avg_time": round(avg_time, 3),
            "error_rate": round(data["errors"] / data["count"] * 100, 2) if data["count"] > 0 else 0
        })
    return sorted(stats, key=lambda x: x["count"], reverse=True)


def reset_api_stats():
    """重置 API 统计"""
    _api_stats.clear()
