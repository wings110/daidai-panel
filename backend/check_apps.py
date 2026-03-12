"""迁移脚本：将现有的哈希值标记为需要重置"""
from app import create_app
from app.extensions import db
from app.models.open_app import OpenApp

app = create_app()

with app.app_context():
    apps = OpenApp.query.all()
    print(f"找到 {len(apps)} 个应用")

    if len(apps) == 0:
        print("没有应用需要迁移")
    else:
        print("\n警告：由于从哈希改为加密，现有应用的 Secret 无法恢复。")
        print("建议：")
        print("1. 如果这些应用还在使用，请在管理界面重置它们的 Secret")
        print("2. 如果是测试数据，可以直接删除重建")
        print("\n应用列表:")
        for app_obj in apps:
            print(f"  - ID: {app_obj.id}, 名称: {app_obj.name}, Client ID: {app_obj.client_id}")
