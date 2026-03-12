# ============================================================
# 呆呆面板 Dockerfile — 单镜像，类青龙面板部署方式
# 容器以 root 用户运行，内含 Nginx + Gunicorn + Node.js + Python
# ============================================================

# ---- 阶段 1：前端构建 ----
FROM node:20-alpine AS frontend-builder

WORKDIR /build

COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install --registry https://registry.npmmirror.com

COPY frontend/ .
RUN npm run build


# ---- 阶段 2：最终镜像 ----
FROM python:3.11-slim

LABEL maintainer="daidai-panel"
LABEL description="呆呆面板 - 定时任务管理系统"

# 环境变量
ENV DAIDAI_DATA_DIR=/dd/data \
    DAIDAI_SCRIPTS_DIR=/dd/scripts \
    DAIDAI_LOG_DIR=/dd/log \
    DAIDAI_CONFIG_DIR=/dd/config \
    FLASK_ENV=production \
    PYTHONUNBUFFERED=1 \
    TZ=Asia/Shanghai

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    bash \
    nginx \
    cron \
    tzdata \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && npm config set registry https://registry.npmmirror.com \
    && ln -sf /usr/share/zoneinfo/Asia/Shanghai /etc/localtime \
    && echo "Asia/Shanghai" > /etc/timezone \
    && apt-get clean && rm -rf /var/lib/apt/lists/* /tmp/*

# 创建数据目录
RUN mkdir -p /dd/data /dd/scripts /dd/log /dd/config /dd/deps

# 安装 Python 依赖
WORKDIR /app/backend
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir psutil

# 复制后端代码
COPY backend/ .

# 复制前端构建产物
COPY --from=frontend-builder /build/dist /app/frontend/dist

# 复制 Nginx 配置
COPY docker/nginx.conf /etc/nginx/conf.d/default.conf
RUN rm -f /etc/nginx/sites-enabled/default

# 复制启动脚本
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# 暴露端口（Nginx 对外 7100，与青龙保持类似）
EXPOSE 7100

VOLUME ["/dd/data", "/dd/scripts", "/dd/log", "/dd/config"]

ENTRYPOINT ["/entrypoint.sh"]
