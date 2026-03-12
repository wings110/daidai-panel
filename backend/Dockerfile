# 后端 Dockerfile
FROM python:3.11-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .

# 安装 Python 依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY . .

# 创建必要的目录
RUN mkdir -p data scripts logs

# 暴露端口
EXPOSE 7100

# 启动命令（使用 eventlet worker 支持 WebSocket）
CMD ["gunicorn", "-k", "eventlet", "-w", "1", "-b", "0.0.0.0:7100", "--timeout", "120", "wsgi:app"]
