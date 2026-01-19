# 使用轻量级基础镜像
FROM python:3.10-slim-bookworm

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=5000
ENV HOST=0.0.0.0
ARG ADMIN_PASSWORD=admin123
ENV ADMIN_PASSWORD=${ADMIN_PASSWORD}

# 定义数据目录和预置数据目录
ENV DATA_DIR=/app/data
ENV PRELOADED_DIR=/app/preloaded_data

# 安装必要的依赖 (只保留 sqlite3，不需要 gosu 了)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        sqlite3 \
        && rm -rf /var/lib/apt/lists/* \
        && apt-get clean

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY server.py .
COPY database.py .
COPY index.html .

# 创建必要的目录
RUN mkdir -p $DATA_DIR && \
    mkdir -p $PRELOADED_DIR

# 【关键步骤】构建镜像时，把数据库生成在 preloaded 目录中
# 这样即使 /app/data 被挂载覆盖，备份数据依然在
RUN export DATA_DIR=$PRELOADED_DIR && \
    python -c "from database import init_db; init_db()"

# 暴露端口
EXPOSE 5000

# 默认以 Root 身份直接启动
CMD ["python", "server.py"]