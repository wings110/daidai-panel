"""加密工具模块"""
import os
import base64
import secrets
from pathlib import Path
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


def _get_or_create_encryption_secret() -> str:
    """获取或创建加密密钥

    优先级：
    1. 环境变量 ENCRYPTION_SECRET
    2. 持久化文件 data/.encryption_secret
    3. 自动生成并保存到文件
    """
    # 1. 尝试从环境变量获取
    secret = os.getenv("ENCRYPTION_SECRET")
    if secret:
        return secret

    # 2. 尝试从持久化文件读取
    data_dir = os.getenv("DAIDAI_DATA_DIR", os.getenv("DATA_DIR", "./data"))
    secret_file = Path(data_dir) / ".encryption_secret"

    if secret_file.exists():
        try:
            with open(secret_file, 'r', encoding='utf-8') as f:
                secret = f.read().strip()
                if secret:
                    return secret
        except Exception as e:
            print(f"警告: 读取加密密钥文件失败: {e}")

    # 3. 自动生成新密钥并持久化
    print("⚠️  未找到加密密钥，正在自动生成...")
    secret = secrets.token_urlsafe(32)  # 生成 256 位随机密钥

    try:
        os.makedirs(data_dir, exist_ok=True)
        with open(secret_file, 'w', encoding='utf-8') as f:
            f.write(secret)
        # 设置文件权限为仅所有者可读写
        os.chmod(secret_file, 0o600)
        print(f"✅ 加密密钥已生成并保存到: {secret_file}")
        print("⚠️  请妥善保管此文件，丢失后将无法解密已加密的数据！")
    except Exception as e:
        print(f"❌ 保存加密密钥失败: {e}")
        print("⚠️  请手动设置环境变量 ENCRYPTION_SECRET")
        raise RuntimeError("无法初始化加密密钥，请设置 ENCRYPTION_SECRET 环境变量")

    return secret


def get_encryption_key() -> bytes:
    """获取加密密钥"""
    secret = _get_or_create_encryption_secret()
    salt = b"openapi-secret-salt"

    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(secret.encode()))
    return key


def encrypt_secret(plain_text: str) -> str:
    """加密 Secret"""
    key = get_encryption_key()
    f = Fernet(key)
    encrypted = f.encrypt(plain_text.encode())
    return base64.urlsafe_b64encode(encrypted).decode()


def decrypt_secret(encrypted_text: str) -> str:
    """解密 Secret"""
    key = get_encryption_key()
    f = Fernet(key)
    encrypted = base64.urlsafe_b64decode(encrypted_text.encode())
    decrypted = f.decrypt(encrypted)
    return decrypted.decode()


# 通用加密/解密函数（用于 SSH 密钥等）
def encrypt_data(plain_text: str) -> str:
    """加密数据（通用）"""
    return encrypt_secret(plain_text)


def decrypt_data(encrypted_text: str) -> str:
    """解密数据（通用）"""
    return decrypt_secret(encrypted_text)
