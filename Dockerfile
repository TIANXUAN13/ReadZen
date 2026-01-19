FROM python:3.10-slim-bookworm

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=5000
ENV HOST=0.0.0.0
ARG ADMIN_PASSWORD=admin123
ENV ADMIN_PASSWORD=${ADMIN_PASSWORD}

# 1. 设置数据目录环境变量
# DATA_DIR 是运行时挂载的目录
# PRELOADED_DIR 是构建时存放初始数据的目录
ENV DATA_DIR=/app/data
ENV PRELOADED_DIR=/app/preloaded_data

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        sqlite3 \
        gosu \
        && rm -rf /var/lib/apt/lists/* \
        && apt-get clean

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY server.py .
COPY database.py .
COPY index.html .

# 2. 创建用户、组和必要的目录
# 注意：我们这里不往 /app/data 里写东西，而是往 preloaded 里写
RUN groupadd -r appgroup && useradd -r -g appgroup appuser && \
    mkdir -p $DATA_DIR && \
    mkdir -p $PRELOADED_DIR && \
    chown -R appuser:appgroup /app

# 3. 关键点：在构建阶段，临时把 DATA_DIR 指向 preloaded 目录
# 这样运行 init_db 时，数据库会生成在 /app/preloaded_data/data.db
RUN export DATA_DIR=$PRELOADED_DIR && \
    python -c "from database import init_db; init_db()" && \
    chown -R appuser:appgroup $PRELOADED_DIR

# 4. 再次确保挂载点的权限（虽然挂载后可能会变，但先设好）
RUN chown -R appuser:appgroup $DATA_DIR && \
    chmod 777 $DATA_DIR

USER appuser

EXPOSE 5000

CMD ["python", "server.py"]