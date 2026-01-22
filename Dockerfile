# --- 阶段 1: 构建阶段 (Builder) ---
# 使用官方 Python 镜像作为构建环境
FROM python:3.10-slim-bookworm as builder

WORKDIR /app

# 禁止 Python 产生 .pyc 文件，并开启无缓冲输出
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# 安装构建依赖 (如需编译 C 扩展则需要 gcc 等)
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc python3-dev && \
    rm -rf /var/lib/apt/lists/*

# 安装 Python 依赖到用户目录下，方便后续拷贝
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt


# --- 阶段 2: 最终运行阶段 (Runtime) ---
FROM python:3.10-slim-bookworm

LABEL maintainer="ReadZen Team"
LABEL description="A zen-style daily article reader with local file support"

WORKDIR /app

# 从构建阶段拷贝安装好的 Python 包
COPY --from=builder /root/.local /root/.local
# 确保脚本在 PATH 中
ENV PATH=/root/.local/bin:$PATH

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

# 安装运行时必需的最小依赖：
# - sqlite3: 数据库管理
# - curl: 用于健康检查
RUN apt-get update && \
    apt-get install -y --no-install-recommends sqlite3 curl && \
    rm -rf /var/lib/apt/lists/* && \
    # 提前创建目录
    mkdir -p $DATA_DIR $PRELOADED_DIR && \
    # 确保目录权限正确（特别是对于 bind mount）
    chmod 777 $DATA_DIR

# 拷贝应用核心代码
COPY server.py database.py index.html ./

# 【构建时初始化】在镜像内生成预置数据库
# 这一步非常重要：即使外部挂载了空目录，应用启动时也能从这里恢复初始结构
RUN export DATA_DIR=$PRELOADED_DIR && \
    python -c "from database import init_db; init_db()" && \
    # 设置预置数据库权限为可读
    chmod 666 $PRELOADED_DIR/data.db

# 健康检查：确保容器服务真正可用
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:${PORT}/api/daily || exit 1

# 暴露端口
EXPOSE ${PORT}

# 启动指令优化：
# 使用 Gunicorn 替代 Flask 自带的开发服务器，提升并发处理能力和稳定性
# -w 4: 使用 4 个工作进程 (通常为 CPU 核心数 * 2 + 1)
# --timeout 120: 增加超时时间，防止大型文件上传时断开
# --access-logfile / --error-logfile: 将日志输出到标准输出/错误流，方便 Docker 日志收集
CMD ["gunicorn", \
     "-w", "4", \
     "-b", "0.0.0.0:15000", \
     "--timeout", "120", \
     "--access-logfile", "-", \
     "--error-logfile", "-", \
     "server:app"]
