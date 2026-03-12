"""API 版本管理"""

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required
from app.services.rate_limiter import get_api_stats, reset_api_stats
from app.utils.permissions import require_admin

api_meta_bp = Blueprint("api_meta", __name__)


@api_meta_bp.route("/version", methods=["GET"])
def get_api_version():
    """获取 API 版本信息
    ---
    tags:
      - 系统
    responses:
      200:
        description: API 版本信息
        schema:
          type: object
          properties:
            version:
              type: string
              example: "v1"
            api_version:
              type: string
              example: "1.1.0"
            supported_versions:
              type: array
              items:
                type: string
              example: ["v1"]
    """
    return jsonify({
        "version": "v1",
        "api_version": "1.1.0",
        "supported_versions": ["v1"],
        "deprecated_versions": [],
        "documentation": "/api/docs/",
    })


@api_meta_bp.route("/health", methods=["GET"])
def health_check():
    """健康检查
    ---
    tags:
      - 系统
    responses:
      200:
        description: 服务健康状态
        schema:
          type: object
          properties:
            status:
              type: string
              example: "healthy"
            timestamp:
              type: string
              example: "2024-01-01T00:00:00"
    """
    from datetime import datetime
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.1.0",
    })


@api_meta_bp.route("/stats", methods=["GET"])
@jwt_required()
@require_admin
def get_api_statistics():
    """获取 API 调用统计
    ---
    tags:
      - 系统
    security:
      - Bearer: []
    responses:
      200:
        description: API 调用统计
        schema:
          type: object
          properties:
            data:
              type: array
              items:
                type: object
                properties:
                  endpoint:
                    type: string
                  count:
                    type: integer
                  errors:
                    type: integer
                  avg_time:
                    type: number
                  error_rate:
                    type: number
    """
    stats = get_api_stats()
    return jsonify({"data": stats})


@api_meta_bp.route("/stats/reset", methods=["POST"])
@jwt_required()
@require_admin
def reset_api_statistics():
    """重置 API 调用统计
    ---
    tags:
      - 系统
    security:
      - Bearer: []
    responses:
      200:
        description: 重置成功
    """
    reset_api_stats()
    return jsonify({"message": "API 统计已重置"})


@api_meta_bp.route("/rate-limit/status", methods=["GET"])
@jwt_required()
def get_rate_limit_status():
    """获取当前用户的限流状态
    ---
    tags:
      - 系统
    security:
      - Bearer: []
    responses:
      200:
        description: 限流状态
        schema:
          type: object
          properties:
            remaining:
              type: integer
              description: 剩余请求次数
            reset_at:
              type: string
              description: 重置时间
    """
    # 这里可以返回当前用户的限流状态
    return jsonify({
        "message": "限流状态查询功能",
        "note": "具体限流规则请参考 API 文档"
    })
