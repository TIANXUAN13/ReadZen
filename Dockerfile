# 使用轻量级基础镜像
FROM python:3.10-slim-bookworm

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=5000
ENV HOST=0.0.0.0

# 使用构建参数设置 ADMIN_PASSWORD
ARG ADMIN_PASSWORD=admin123
ENV ADMIN_PASSWORD=${ADMIN_PASSWORD}

# 安装必要的依赖，只保留 sqlite3
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        sqlite3 \
        && rm -rf /var/lib/apt/lists/* \
        && apt-get clean

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用文件
COPY server.py .

# 清理 pip 缓存
RUN rm -rf /root/.cache/pip

# 减小权限（可选）
RUN groupadd -r appgroup && useradd -r -g appgroup appuser && \
    chown -R appuser:appgroup /app
USER appuser

EXPOSE 5000

CMD ["python", "server.py"]