# ReadZen systemd 部署指南

## 概述

本文档介绍如何使用 systemd 在 Linux 服务器上部署 ReadZen 服务。

**适用场景**：独立服务器 / VPS / 虚拟机（非容器化部署）

**技术栈**：
- Python 3.11+
- Gunicorn 4+ (WSGI 服务器)
- systemd (进程管理)
- 可选：Nginx (反向代理)

---

## 1. 服务器准备工作

### 1.1 创建部署用户（生产环境最佳实践）

```bash
# 创建专门的服务用户（无登录权限）
sudo useradd -r -s /bin/false -m -d /opt/readzen readzen

# 创建数据目录并设置权限
sudo mkdir -p /opt/readzen/{data,logs}
sudo chown -R readzen:readzen /opt/readzen
sudo chmod 755 /opt/readzen/data
```

### 1.2 安装系统依赖

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install -y python3.11 python3.11-venv python3-pip nginx git

# RHEL/CentOS
sudo dnf install -y python311 python311-pip nginx git
```

### 1.3 克隆项目

```bash
# 克隆到 /opt/readzen/workspace
sudo mkdir -p /opt/readzen/workspace
sudo git clone https://your-repo/readzen.git /opt/readzen/workspace
sudo chown -R readzen:readzen /opt/readzen/workspace
```

---

## 2. 配置环境

### 2.1 创建 Python 虚拟环境

```bash
cd /opt/readzen/workspace
sudo python3.11 -m venv venv
sudo chown -R readzen:readzen venv
sudo -u readzen ./venv/bin/pip install --upgrade pip
sudo -u readzen ./venv/bin/pip install -r requirements.txt
```

### 2.2 创建环境变量文件

```bash
sudo nano /opt/readzen/.env
```

**模板内容**：

```bash
# ReadZen Environment Configuration
# 复制此文件为 .env 并修改配置

# Flask 配置
FLASK_ENV=production
SECRET_KEY=your-super-secret-key-change-this-in-production

# 数据目录（确保已创建并有写入权限）
DATA_DIR=/opt/readzen/data

# 服务器配置
HOST=127.0.0.1
PORT=5000
WORKERS=4
TIMEOUT=120

# API 配置（按需修改）
# DAILY_API_URL=https://your-api-endpoint.com

# 日志配置
LOG_DIR=/opt/readzen/logs
LOG_LEVEL=info
```

### 2.3 初始化数据库

```bash
cd /opt/readzen/workspace
sudo -u readzen ./venv/bin/python -c "from database import init_db; init_db()"
```

---

## 3. systemd 服务配置

### 3.1 创建服务文件

```bash
sudo nano /etc/systemd/system/readzen.service
```

**服务文件内容**：

```ini
[Unit]
Description=ReadZen - Daily Article Reader Service
Documentation=https://github.com/your-repo/readzen
After=network.target

[Service]
# 服务用户和组
User=readzen
Group=readzen

# 工作目录
WorkingDirectory=/opt/readzen/workspace

# 虚拟环境
Environment="PATH=/opt/readzen/workspace/venv/bin"
EnvironmentFile=/opt/readzen/.env

# Gunicorn 命令
# -k gevent: 异步处理，提高并发性能
# --access-logfile: 访问日志
# --error-logfile: 错误日志
# --capture-output: 捕获 Python 输出到日志
ExecStart=/opt/readzen/workspace/venv/bin/gunicorn \
    --chdir /opt/readzen/workspace \
    --bind ${HOST}:${PORT} \
    --workers ${WORKERS} \
    --timeout ${TIMEOUT} \
    --access-logfile ${LOG_DIR}/access.log \
    --error-logfile ${LOG_DIR}/error.log \
    --capture-output \
    server:app

# 重启策略
Restart=always
RestartSec=5

# 文件描述符限制（高并发时需要）
LimitNOFILE=65535

# 内存限制（可选，防止内存泄漏）
MemoryMax=1G

# 环境清理
RuntimeDirectoryMode=0755

# 健康检查 ExecHealthCheck 用于 systemd 服务健康监控
# 检查服务是否响应
ExecHealthCheck=/opt/readzen/workspace/venv/bin/python -c "
import urllib.request
urllib.request.urlopen('http://127.0.0.1:5000/health', timeout=5)
"

[Install]
WantedBy=multi-user.target
```

### 3.2 创建定时任务服务（可选）

如果需要每日自动任务：

```bash
sudo nano /etc/systemd/system/readzen-daily.service
```

```ini
[Unit]
Description=ReadZen Daily Task
After=readzen.service

[Service]
Type=oneshot
User=readzen
Environment="PATH=/opt/readzen/workspace/venv/bin"
EnvironmentFile=/opt/readzen/.env
ExecStart=/opt/readzen/workspace/venv/bin/python /opt/readzen/workspace/daily_task.py
```

创建定时器：

```bash
sudo nano /etc/systemd/system/readzen-daily.timer
```

```ini
[Unit]
Description=Run ReadZen Daily Task at 6 AM

[Timer]
OnCalendar=*-*-* 06:00:00
Persistent=true

[Install]
WantedBy=timers.target
```

### 3.3 重新加载并启动服务

```bash
# 重新加载 systemd 配置
sudo systemctl daemon-reload

# 设置开机自启
sudo systemctl enable readzen.service

# 启动服务
sudo systemctl start readzen.service

# 检查状态
sudo systemctl status readzen.service
```

---

## 4. Nginx 反向代理（生产环境推荐）

### 4.1 创建 Nginx 配置

```bash
sudo nano /etc/nginx/sites-available/readzen
```

```nginx
server {
    listen 80;
    server_name your-domain.com;  # 替换为你的域名

    # 重定向到 HTTPS（如果使用 SSL）
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com;

    # SSL 配置（按需修改）
    ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;
    ssl_session_timeout 1d;
    ssl_session_cache shared:SSL:50m;
    ssl_session_tickets off;

    # 安全头
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;

    # Gzip 压缩
    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_types text/plain text/css text/xml text/javascript application/javascript application/json application/xml;

    # 静态文件缓存
    location /static/ {
        alias /opt/readzen/workspace/static/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    # 主应用代理
    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_http_version 1.1;

        # WebSocket 支持（如果需要）
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";

        # 原始请求头传递
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # 超时设置
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;

        # 缓冲优化
        proxy_buffering on;
        proxy_buffer_size 4k;
        proxy_buffers 8 4k;
    }

    # 健康检查端点
    location /health {
        proxy_pass http://127.0.0.1:5000/health;
        access_log off;
    }
}
```

### 4.2 启用配置

```bash
# 启用站点
sudo ln -s /etc/nginx/sites-available/readzen /etc/nginx/sites-enabled/

# 测试配置
sudo nginx -t

# 重启 Nginx
sudo systemctl restart nginx
```

### 4.3 配置防火墙

```bash
# UFW
sudo ufw allow 80
sudo ufw allow 443
sudo ufw enable

# 或 firewalld
sudo firewall-cmd --permanent --add-service=http
sudo firewall-cmd --permanent --add-service=https
sudo firewall-cmd --reload
```

---

## 5. 日志管理

### 5.1 日志文件位置

- **访问日志**：`/opt/readzen/logs/access.log`
- **错误日志**：`/opt/readzen/logs/error.log`
- **systemd 日志**：`journalctl -u readzen`

### 5.2 日志查看命令

```bash
# 查看服务日志
sudo journalctl -u readzen -f

# 查看最近 100 行
sudo journalctl -u readzen -n 100

# 查看今天的日志
sudo journalctl -u readzen --since today

# 查看错误日志
sudo tail -f /opt/readzen/logs/error.log
```

### 5.3 日志轮转

创建日志轮转配置：

```bash
sudo nano /etc/logrotate.d/readzen
```

```text
/opt/readzen/logs/*.log {
    daily
    rotate 14
    compress
    delaycompress
    missingok
    notifempty
    create 0640 readzen readzen
    postrotate
        systemctl reload readzen > /dev/null 2>&1 || true
    endscript
}
```

---

## 6. 服务管理命令

### 6.1 日常操作

```bash
# 启动服务
sudo systemctl start readzen

# 停止服务
sudo systemctl stop readzen

# 重启服务
sudo systemctl restart readzen

# 重新加载配置（不断开连接）
sudo systemctl reload readzen

# 查看状态
sudo systemctl status readzen

# 查看是否开机自启
sudo systemctl is-enabled readzen
```

### 6.2 故障排查

```bash
# 查看详细日志
sudo journalctl -u readzen -n 200 --no-pager

# 检查 Gunicorn 进程
ps aux | grep gunicorn

# 检查端口占用
sudo netstat -tlnp | grep 5000

# 测试应用直接运行
cd /opt/readzen/workspace
sudo -u readzen ./venv/bin/python -c "from server import app; app.run(host='127.0.0.1', port=5000)"
```

### 6.3 健康检查脚本

```bash
#!/bin/bash
# /opt/readzen/health_check.sh

HEALTH_URL="http://127.0.0.1:5000/health"
TIMEOUT=5

if curl -s --connect-timeout $TIMEOUT $HEALTH_URL | grep -q "OK"; then
    exit 0
else
    echo "Health check failed, restarting readzen..."
    sudo systemctl restart readzen
    exit 1
fi
```

添加到 crontab 每 5 分钟检查：

```bash
crontab -e
# 添加
*/5 * * * * /opt/readzen/health_check.sh >> /opt/readzen/logs/health.log 2>&1
```

---

## 7. 更新部署

### 7.1 更新脚本

```bash
#!/bin/bash
# /opt/readzen/update.sh

set -e

echo "Stopping ReadZen..."
sudo systemctl stop readzen

echo "Backing up data..."
cp -r /opt/readzen/data /opt/readzen/data.backup.$(date +%Y%m%d)

echo "Pulling latest code..."
cd /opt/readzen/workspace
sudo -u readzen git fetch origin
sudo -u readzen git pull origin main

echo "Installing dependencies..."
sudo -u readzen ./venv/bin/pip install -r requirements.txt

echo "Migrating database..."
sudo -u readzen ./venv/bin/python -c "from database import migrate; migrate()"

echo "Starting ReadZen..."
sudo systemctl start readzen

echo "Checking status..."
sudo systemctl status readzen

echo "Update complete!"
```

### 7.2 执行更新

```bash
chmod +x /opt/readzen/update.sh
sudo /opt/readzen/update.sh
```

---

## 8. 安全加固

### 8.1 文件权限

```bash
# 确保敏感文件权限正确
sudo chmod 600 /opt/readzen/.env  # 环境变量文件
sudo chmod 644 /etc/systemd/system/readzen.service
sudo chown -R root:root /opt/readzen
sudo chown -R readzen:readzen /opt/readzen/data
sudo chown -R readzen:readzen /opt/readzen/logs
```

### 8.2 SELinux（如果启用）

```bash
# 允许 Nginx 代理
sudo setsebool -P httpd_can_network_connect 1

# 允许日志写入
sudo setsebool -P httpd_sys_script_anon_write 1
```

---

## 9. Docker vs systemd 对比

| 特性 | Docker | systemd |
|------|--------|---------|
| **部署复杂度** | 中等 | 低 |
| **资源隔离** | 强 | 一般 |
| **端口管理** | 自动 | 手动配置 |
| **日志收集** | docker logs | journalctl |
| **更新方式** | 重建容器 | 更新代码 + 重启 |
| **适合场景** | 多服务、K8s | 单体应用、VPS |

---

## 10. 快速参考卡

```bash
# === 一键部署脚本 === #
# 在服务器上以 root 运行

export READZEN_USER="readzen"
export READZEN_DIR="/opt/readzen"

# 1. 安装依赖
apt update && apt install -y python3.11 python3-pip nginx git

# 2. 创建用户和目录
useradd -r -s /bin/false -m -d $READZEN_DIR $READZEN_USER
mkdir -p $READZEN_DIR/{data,logs,workspace}
chown -R $READZEN_USER:$READZEN_USER $READZEN_DIR

# 3. 克隆代码
git clone https://your-repo/readzen.git $READZEN_DIR/workspace
chown -R $READZEN_USER:$READZEN_USER $READZEN_DIR/workspace

# 4. 安装 Python 依赖
python3 -m venv $READZEN_DIR/workspace/venv
$READZEN_DIR/workspace/venv/bin/pip install -r $READZEN_DIR/workspace/requirements.txt

# 5. 创建配置
cat > $READZEN_DIR/.env << EOF
FLASK_ENV=production
SECRET_KEY=$(openssl rand -base64 32)
DATA_DIR=$READZEN_DIR/data
HOST=127.0.0.1
PORT=5000
WORKERS=4
TIMEOUT=120
LOG_DIR=$READZEN_DIR/logs
EOF

chmod 600 $READZEN_DIR/.env

# 6. 安装 systemd 服务
cat > /etc/systemd/system/readzen.service << EOF
[Unit]
Description=ReadZen Service
After=network.target

[Service]
User=$READZEN_USER
Group=$READZEN_USER
WorkingDirectory=$READZEN_DIR/workspace
Environment="PATH=$READZEN_DIR/workspace/venv/bin"
EnvironmentFile=$READZEN_DIR/.env
ExecStart=$READZEN_DIR/workspace/venv/bin/gunicorn \
    --bind \${HOST}:\${PORT} \
    --workers \${WORKERS} \
    --timeout \${TIMEOUT} \
    --access-logfile \${LOG_DIR}/access.log \
    --error-logfile \${LOG_DIR}/error.log \
    --capture-output \
    server:app
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# 7. 启动服务
systemctl daemon-reload
systemctl enable readzen
systemctl start readzen

echo "ReadZen deployed successfully!"
systemctl status readzen
```

---

## 11. 故障排查速查

| 问题 | 解决方案 |
|------|----------|
| 服务无法启动 | `journalctl -u readzen -n 100` 查看日志 |
| 端口 5000 被占用 | `lsof -i:5000` 查找进程 |
| 权限错误 | 检查 `/opt/readzen` 目录所有者 |
| 502 Bad Gateway | 检查 Nginx 和 Gunicorn 是否都在运行 |
| 内存不足 | 减少 `WORKERS` 数量 |
| 504 Timeout | 增加 `TIMEOUT` 值 |

---

**完成！** 如有问题，检查 `journalctl -u readzen -f` 获取实时日志。
