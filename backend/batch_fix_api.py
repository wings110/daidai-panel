#!/usr/bin/env python3
"""
批量修复 API 文件的类型安全问题
"""

import re
import os

# 需要修复的文件列表
FILES_TO_FIX = [
    "open_api.py",
    "platform_tokens.py",
    "ssh_keys.py",
    "security.py",
    "scripts.py",
    "system.py",
    "logs.py",
    "deps.py",
]

API_DIR = r"D:\爱学习的呆子\呆呆面板开发\backend\app\api"


def add_imports(content: str) -> str:
    """添加必要的导入"""
    # 检查是否已经有 logging 导入
    if "import logging" not in content:
        # 在第一个 import 后添加 logging
        content = re.sub(
            r'(""".*?""")\n\n',
            r'\1\n\nimport logging\n',
            content,
            count=1,
            flags=re.DOTALL
        )

    # 检查是否已经有 validators 导入
    if "from app.utils.validators import" not in content:
        # 在最后一个 from app 导入后添加
        lines = content.split('\n')
        insert_idx = -1
        for i, line in enumerate(lines):
            if line.startswith('from app.'):
                insert_idx = i

        if insert_idx >= 0:
            lines.insert(insert_idx + 1, "from app.utils.validators import safe_strip, safe_str, safe_int, safe_bool")
            content = '\n'.join(lines)

    # 添加 logger
    if "logger = logging.getLogger(__name__)" not in content:
        # 在 Blueprint 定义前添加
        content = re.sub(
            r'(\w+_bp = Blueprint\()',
            r'logger = logging.getLogger(__name__)\n\1',
            content,
            count=1
        )

    return content


def fix_strip_calls(content: str) -> str:
    """修复 .strip() 调用"""
    # 替换 data.get("field", "").strip() 为 safe_strip(data.get("field"))
    content = re.sub(
        r'data\.get\("(\w+)",\s*""\)\.strip\(\)',
        r'safe_strip(data.get("\1"))',
        content
    )

    # 替换 data["field"].strip() 为 safe_strip(data["field"])
    content = re.sub(
        r'data\["(\w+)"\]\.strip\(\)',
        r'safe_strip(data["\1"])',
        content
    )

    # 替换 request.args.get("field", "").strip() 为 safe_strip(request.args.get("field"))
    content = re.sub(
        r'request\.args\.get\("(\w+)",\s*""\)\.strip\(\)',
        r'safe_strip(request.args.get("\1"))',
        content
    )

    return content


def add_exception_handling(content: str) -> str:
    """为函数添加异常处理"""
    # 这个比较复杂，需要手动处理
    # 这里只是标记需要手动处理的函数
    return content


def process_file(filepath: str):
    """处理单个文件"""
    print(f"Processing {os.path.basename(filepath)}...")

    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    original_content = content

    # 添加导入
    content = add_imports(content)

    # 修复 strip 调用
    content = fix_strip_calls(content)

    # 如果有修改，写回文件
    if content != original_content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"  ✓ Fixed {os.path.basename(filepath)}")
    else:
        print(f"  - No changes needed for {os.path.basename(filepath)}")


def main():
    """主函数"""
    print("=" * 60)
    print("批量修复 API 文件类型安全问题")
    print("=" * 60)
    print()

    for filename in FILES_TO_FIX:
        filepath = os.path.join(API_DIR, filename)
        if os.path.exists(filepath):
            try:
                process_file(filepath)
            except Exception as e:
                print(f"  ✗ Error processing {filename}: {e}")
        else:
            print(f"  ✗ File not found: {filename}")
        print()

    print("=" * 60)
    print("完成！")
    print("=" * 60)
    print()
    print("注意：以下修复需要手动完成：")
    print("1. 为所有 create/update/delete 函数添加 try-except 块")
    print("2. 在 except 块中添加 db.session.rollback()")
    print("3. 添加详细的错误日志记录")
    print()


if __name__ == "__main__":
    main()
