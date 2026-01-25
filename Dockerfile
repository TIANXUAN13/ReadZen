# --- 阶段 1: 构建阶段 (Builder) ---
FROM python:3.10-slim-bookworm as builder

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# 安装构建依赖
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc python3-dev && \
    rm -rf /var/lib/apt/lists/*

# 使用 --prefix 将所有内容安装到特定目录，确保路径可控
COPY requirements.txt .
RUN mkdir /install && \
    pip install --no-cache-dir --prefix=/install -r requirements.txt


# --- 阶段 2: 最终运行阶段 (Runtime) ---
FROM python:3.10-slim-bookworm

LABEL maintainer="ReadZen Team"
LABEL description="A zen-style daily article reader with local file support"

WORKDIR /app

# 从构建阶段拷贝安装好的 Python 包和可执行文件
COPY --from=builder /install /usr/local

# 运行时环境变量
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=15000
ENV HOST=0.0.0.0
ARG ADMIN_PASSWORD=admin123
ENV ADMIN_PASSWORD=${ADMIN_PASSWORD}

# 路径配置
ENV DATA_DIR=/app/data
ENV PRELOADED_DIR=/app/preloaded_data

# 安装运行时必需的最小依赖
RUN apt-get update && \
    apt-get install -y --no-install-recommends sqlite3 curl && \
    rm -rf /var/lib/apt/lists/* && \
    mkdir -p $DATA_DIR $PRELOADED_DIR && \
    chmod 777 $DATA_DIR

# 拷贝应用核心代码
COPY server.py database.py index.html ./

# 【构建时初始化】在镜像内生成预置数据库
RUN export DATA_DIR=$PRELOADED_DIR && \
    python -c "from database import init_db; init_db()" && \
    chmod 666 $PRELOADED_DIR/data.db

# 健康检查
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:${PORT}/api/daily || exit 1

EXPOSE ${PORT}

# 使用 Gunicorn 启动
CMD ["gunicorn", \
     "-w", "1", \
     "-k", "gthread", \
     "--threads", "8", \
     "-b", "0.0.0.0:15000", \
     "--timeout", "120", \
     "--access-logfile", "-", \
     "--error-logfile", "-", \
     "server:app"]
