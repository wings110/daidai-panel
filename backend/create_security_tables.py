"""数据库表创建脚本 - 用于创建新增的安全相关表

运行方式:
    python create_security_tables.py
"""

from app import create_app
from app.extensions import db


def create_security_tables():
    """创建安全相关的数据库表"""
    # 导入所有新增的模型
    from app.models.token_blocklist import TokenBlocklist
    from app.models.security_audit import SecurityAudit
    from app.models.login_attempt import LoginAttempt

    app = create_app()
    with app.app_context():
        # 创建所有表
        db.create_all()

        # 验证表是否创建成功
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()

        print("=" * 60)
        print("数据库表创建完成")
        print("=" * 60)

        required_tables = [
            'token_blocklist',
            'security_audits',
            'login_attempts'
        ]

        for table in required_tables:
            status = "✓" if table in tables else "✗"
            print(f"{status} {table}")

        print("=" * 60)

        # 检查是否所有表都创建成功
        all_created = all(table in tables for table in required_tables)
        if all_created:
            print("所有安全表创建成功！")
            return True
        else:
            print("警告: 部分表创建失败")
            return False


if __name__ == "__main__":
    success = create_security_tables()
    exit(0 if success else 1)
