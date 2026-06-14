# ReadZen systemd 部署指南

使用 systemd 将 ReadZen 作为系统服务部署到 Linux 服务器。

## 环境要求

- **操作系统**: Ubuntu 22.04+, Debian 11+, CentOS 8+, RHEL 8+
- **Python**: 3.8+ (推荐 3.11+)
- **权限**: 需要 root 权限运行部署脚本
- **网络**: 可访问互联网（用于安装依赖和克隆代码）

## 快速部署（推荐）

### 1. 下载部署脚本

```bash
# 从 GitHub 克隆项目
git clone https://github.com/2926930231/ReadZen.git
cd ReadZen

# 或者下载单个脚本
wget https://raw.githubusercontent.com/2926930231/ReadZen/main/scripts/deploy.sh
chmod +x deploy.sh
```

### 2. 运行部署脚本

```bash
sudo ./scripts/deploy.sh
```

### 3. 按提示操作

脚本会交互式询问以下配置：

```
>>> 开始部署 ReadZen (每日一文) <<<

步骤 1: 配置安装目录
请输入安装根目录 [默认: /opt/readzen]: 
# 直接回车使用默认 /opt/readzen
# 或输入自定义路径如 /home/readzen

步骤 2: 选择代码来源
1) 从 GitHub 克隆最新代码 (推荐)
2) 使用当前目录下的代码
请选择 [1-2]: 1

步骤 3-8: 自动执行...
```

### 4. 部署完成

脚本执行完成后会显示：

```
=================================================
🎉 ReadZen 部署完成！
=================================================

服务状态:
   Active: active (running) since ...

访问地址:
👉 http://192.168.1.100:15000
👉 http://localhost:15000

常用命令:
- 查看日志: sudo journalctl -u readzen -f
- 重启服务: sudo systemctl restart readzen
- 配置文件: /opt/readzen/.env
- 代码目录: /opt/readzen/workspace
=================================================
```

## 手动部署

如需手动部署，按以下步骤操作：

### 1. 安装系统依赖

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install -y python3-pip python3-venv git curl openssl lsof
```

**CentOS/RHEL:**
```bash
sudo dnf install -y python3-pip git curl openssl lsof
```

### 2. 创建部署目录和用户

```bash
INSTALL_DIR="/opt/readzen"  # 可自定义

sudo useradd -r -s /bin/false -m -d $INSTALL_DIR readzen
sudo mkdir -p $INSTALL_DIR/{workspace,logs,data}
sudo chown -R readzen:readzen $INSTALL_DIR
```

### 3. 部署代码

**方式 A - 从 GitHub 克隆:**
```bash
cd $INSTALL_DIR
sudo -u readzen git clone https://github.com/2926930231/ReadZen.git workspace
```

**方式 B - 使用本地代码:**
```bash
cd /path/to/your/code
sudo rsync -av --exclude 'venv' --exclude '.git' --exclude '__pycache__' ./ $INSTALL_DIR/workspace/
sudo chown -R readzen:readzen $INSTALL_DIR/workspace
```

### 4. 创建虚拟环境并安装依赖

```bash
cd $INSTALL_DIR/workspace
sudo -u readzen python3 -m venv venv
sudo -u readzen ./venv/bin/pip install --upgrade pip
sudo -u readzen ./venv/bin/pip install -r requirements.txt
```

### 5. 配置环境变量

```bash
sudo tee $INSTALL_DIR/.env > /dev/null <<EOF
FLASK_ENV=production
SECRET_KEY=$(openssl rand -base64 32)
DATA_DIR=$INSTALL_DIR/data
HOST=0.0.0.0
PORT=15000
WORKERS=4
TIMEOUT=120
LOG_DIR=$INSTALL_DIR/logs
EOF

sudo chmod 600 $INSTALL_DIR/.env
sudo chown readzen:readzen $INSTALL_DIR/.env
```

### 6. 创建 systemd 服务

```bash
sudo tee /etc/systemd/system/readzen.service > /dev/null <<EOF
[Unit]
Description=ReadZen - Daily Article Reader Service
After=network.target

[Service]
User=readzen
Group=readzen
WorkingDirectory=$INSTALL_DIR/workspace
Environment="PATH=$INSTALL_DIR/workspace/venv/bin"
EnvironmentFile=$INSTALL_DIR/.env
ExecStart=$INSTALL_DIR/workspace/venv/bin/gunicorn \
    --chdir $INSTALL_DIR/workspace \
    --bind \${HOST}:\${PORT} \
    --workers \${WORKERS} \
    --timeout \${TIMEOUT} \
    --access-logfile \${LOG_DIR}/access.log \
    --error-logfile \${LOG_DIR}/error.log \
    --capture-output \
    server:app
Restart=always
RestartSec=5
LimitNOFILE=65535

[Install]
WantedBy=multi-user.target
EOF
```

### 7. 启动服务

```bash
sudo systemctl daemon-reload
sudo systemctl enable readzen
sudo systemctl start readzen
```

### 8. 验证部署

```bash
# 查看服务状态
sudo systemctl status readzen

# 测试访问
curl http://localhost:15000
```

## 服务管理

### 常用命令

```bash
# 查看服务状态
sudo systemctl status readzen

# 启动/停止/重启
sudo systemctl start readzen
sudo systemctl stop readzen
sudo systemctl restart readzen

# 查看实时日志
sudo journalctl -u readzen -f

# 查看最近 100 行日志
sudo journalctl -u readzen -n 100

# 查看今天的日志
sudo journalctl -u readzen --since today
```

### 配置文件位置

| 文件 | 路径 |
|------|------|
| 环境配置 | `/opt/readzen/.env` |
| 服务配置 | `/etc/systemd/system/readzen.service` |
| 访问日志 | `/opt/readzen/logs/access.log` |
| 错误日志 | `/opt/readzen/logs/error.log` |
| 数据文件 | `/opt/readzen/data/` |

## 更新部署

### 使用脚本更新

```bash
cd /opt/readzen/workspace
sudo git pull origin main
sudo -u readzen ./venv/bin/pip install -r requirements.txt
sudo systemctl restart readzen
```

### 手动更新

```bash
# 1. 备份数据
sudo cp -r /opt/readzen/data /opt/readzen/data.backup.$(date +%Y%m%d)

# 2. 停止服务
sudo systemctl stop readzen

# 3. 更新代码
cd /opt/readzen/workspace
sudo -u readzen git pull origin main

# 4. 更新依赖
sudo -u readzen ./venv/bin/pip install -r requirements.txt

# 5. 启动服务
sudo systemctl start readzen

# 6. 检查状态
sudo systemctl status readzen
```

## Nginx 反向代理（可选）

如需通过域名访问，可配置 Nginx：

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:15000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

启用配置：
```bash
sudo ln -s /etc/nginx/sites-available/readzen /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

## 故障排查

### 服务无法启动

```bash
# 查看详细错误
sudo journalctl -u readzen -n 200 --no-pager

# 检查端口占用
sudo lsof -i:15000

# 手动测试应用
sudo -u readzen /opt/readzen/workspace/venv/bin/python -c "
import sys
sys.path.insert(0, '/opt/readzen/workspace')
from server import app
app.run(host='127.0.0.1', port=15000)
"
```

### 权限问题

```bash
# 修复文件权限
sudo chown -R readzen:readzen /opt/readzen/data
sudo chown -R readzen:readzen /opt/readzen/logs
sudo chmod 600 /opt/readzen/.env
```

### 依赖问题

```bash
# 重新安装依赖
cd /opt/readzen/workspace
sudo -u readzen ./venv/bin/pip install --force-reinstall -r requirements.txt
```

## 目录结构

部署完成后，目录结构如下：

```
/opt/readzen/                 # 安装根目录（可自定义）
├── .env                      # 环境变量配置
├── workspace/                # 代码目录
│   ├── server.py            # 主服务
│   ├── database.py          # 数据库模块
│   ├── index.html           # 前端页面
│   ├── requirements.txt     # Python 依赖
│   └── venv/                # Python 虚拟环境
├── logs/                     # 日志目录
│   ├── access.log           # 访问日志
│   └── error.log            # 错误日志
└── data/                     # 数据目录
    └── data.db              # SQLite 数据库
```

## 安全建议

1. **修改默认密码**: 首次登录后修改 admin 密码
2. **配置防火墙**: 仅开放必要端口（80/443）
3. **使用 HTTPS**: 生产环境务必配置 SSL 证书
4. **定期备份**: 备份 `/opt/readzen/data/` 目录
5. **日志轮转**: 配置 logrotate 防止日志占满磁盘

## 支持与反馈

- **GitHub Issues**: [提交问题](https://github.com/TIANXUAN13/ReadZen/issues)
- **文档**: [详细文档](README.md)

---
**部署脚本位置**: `scripts/deploy.sh`
