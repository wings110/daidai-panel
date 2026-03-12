#!/bin/bash
set -e

echo "============================================"
echo "  呆呆面板 (Daidai Panel) 启动中..."
echo "============================================"

# 确保数据目录存在
mkdir -p /dd/data /dd/scripts /dd/log /dd/config /dd/deps

# 如果配置目录中有 secret_key，复制到 data 目录
if [ -f /dd/config/.secret_key ]; then
    cp /dd/config/.secret_key /dd/data/.secret_key
fi

# 初始化数据库和默认配置
cd /app/backend
echo "[1/4] 初始化数据库..."
python -c "
from wsgi import app
print('数据库初始化完成')
"

# 备份 secret_key 到配置目录
if [ -f /dd/data/.secret_key ] && [ ! -f /dd/config/.secret_key ]; then
    cp /dd/data/.secret_key /dd/config/.secret_key
fi

# 启动 Nginx
echo "[2/4] 启动 Nginx..."
nginx

# 启动后端 (Gunicorn)
echo "[3/4] 启动后端服务..."
echo "[4/4] 呆呆面板启动完成！"

exec gunicorn wsgi:app \
    --bind 127.0.0.1:5000 \
    --workers "${GUNICORN_WORKERS:-2}" \
    --threads "${GUNICORN_THREADS:-4}" \
    --timeout 600 \
    --access-logfile /dd/log/access.log \
    --error-logfile /dd/log/error.log \
    --log-level info
