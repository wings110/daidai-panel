"""迁移脚本：将 client_secret_hash 改为 client_secret_encrypted"""
import sys
from app import create_app
from app.extensions import db

app = create_app()

with app.app_context():
    # 检查表结构
    from sqlalchemy import inspect
    inspector = inspect(db.engine)

    # 检查 open_apps 表的列
    columns = [col['name'] for col in inspector.get_columns('open_apps')]
    print(f"当前列: {columns}")

    if 'client_secret_hash' in columns and 'client_secret_encrypted' not in columns:
        print("需要重命名列...")
        # 重命名列
        with db.engine.connect() as conn:
            conn.execute(db.text(
                "ALTER TABLE open_apps RENAME COLUMN client_secret_hash TO client_secret_encrypted"
            ))
            conn.commit()
        print("列重命名完成")
    elif 'client_secret_encrypted' in columns:
        print("列已经是 client_secret_encrypted，无需迁移")
    else:
        print("错误：找不到 client_secret_hash 或 client_secret_encrypted 列")
        sys.exit(1)
