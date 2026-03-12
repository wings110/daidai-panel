"""Swagger API 文档配置"""

from flasgger import Swagger

# Swagger 配置
swagger_config = {
    "headers": [],
    "specs": [
        {
            "endpoint": "apispec",
            "route": "/api/docs/apispec.json",
            "rule_filter": lambda rule: True,
            "model_filter": lambda tag: True,
        }
    ],
    "static_url_path": "/api/docs/static",
    "swagger_ui": True,
    "specs_route": "/api/docs/",
}

# Swagger 模板
swagger_template = {
    "swagger": "2.0",
    "info": {
        "title": "呆呆面板 API 文档",
        "description": "呆呆面板 RESTful API 接口文档",
        "contact": {
            "email": "support@daidai-panel.com",
        },
        "version": "1.1.0",
    },
    "host": "localhost:5000",
    "basePath": "/api",
    "schemes": ["http", "https"],
    "securityDefinitions": {
        "Bearer": {
            "type": "apiKey",
            "name": "Authorization",
            "in": "header",
            "description": "JWT Authorization header using the Bearer scheme. Example: \"Authorization: Bearer {token}\"",
        }
    },
    "security": [{"Bearer": []}],
    "tags": [
        {"name": "认证", "description": "用户认证相关接口"},
        {"name": "任务", "description": "定时任务管理接口"},
        {"name": "日志", "description": "任务日志管理接口"},
        {"name": "脚本", "description": "脚本文件管理接口"},
        {"name": "环境变量", "description": "环境变量管理接口"},
        {"name": "订阅", "description": "订阅管理接口"},
        {"name": "通知", "description": "通知渠道管理接口"},
        {"name": "依赖", "description": "依赖包管理接口"},
        {"name": "系统", "description": "系统信息和配置接口"},
        {"name": "用户", "description": "用户管理接口"},
        {"name": "安全", "description": "安全管理接口"},
        {"name": "开放API", "description": "开放API管理接口"},
    ],
}


def init_swagger(app):
    """初始化 Swagger 文档"""
    Swagger(app, config=swagger_config, template=swagger_template)
