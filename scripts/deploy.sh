#!/bin/bash

# =================================================================
# ReadZen 一键部署脚本 (systemd 版)
# 支持系统: Ubuntu 22.04+, Debian 11+, CentOS 8+, RHEL 8+
# =================================================================

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# 配置变量
PROJECT_NAME="readzen"
DEFAULT_INSTALL_DIR="/opt/readzen"
DEFAULT_REPO="https://github.com/2926930231/ReadZen.git"

# 1. 权限检查
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}错误: 请使用 root 权限运行此脚本 (sudo ./deploy.sh)${NC}"
    exit 1
fi

echo -e "${GREEN}>>> 开始部署 ReadZen (每日一文) <<<${NC}"

# 2. 路径配置
echo -e "\n${YELLOW}步骤 1: 配置安装目录${NC}"
read -p "请输入安装根目录 [默认: $DEFAULT_INSTALL_DIR]: " INSTALL_DIR
INSTALL_DIR=${INSTALL_DIR:-$DEFAULT_INSTALL_DIR}

WORKSPACE_DIR="$INSTALL_DIR/workspace"
LOG_DIR="$INSTALL_DIR/logs"
DATA_DIR="$INSTALL_DIR/data"
SERVICE_FILE="/etc/systemd/system/readzen.service"

echo -e "\n${YELLOW}步骤 2: 选择代码来源${NC}"
echo "1) 从 GitHub 克隆最新代码 (推荐)"
echo "2) 使用当前目录下的代码"
read -p "请选择 [1-2]: " SOURCE_CHOICE

case $SOURCE_CHOICE in
    1)
        read -p "请输入仓库地址 [默认: $DEFAULT_REPO]: " REPO_URL
        REPO_URL=${REPO_URL:-$DEFAULT_REPO}
        ;;
    2)
        echo -e "${GREEN}使用本地代码模式${NC}"
        LOCAL_CODE_DIR=$(pwd)
        ;;
    *)
        echo -e "${RED}无效选择，退出${NC}"
        exit 1
        ;;
esac

echo -e "\n${YELLOW}步骤 3: 安装系统依赖${NC}"
if [ -f /etc/debian_version ]; then
    apt update
    apt install -y python3-pip python3-venv git curl openssl lsof
elif [ -f /etc/redhat-release ]; then
    dnf install -y python3-pip git curl openssl lsof
else
    echo -e "${RED}不支持的操作系统类型${NC}"
    exit 1
fi

# 检查 Python 版本
PYTHON_CMD="python3"
if ! command -v $PYTHON_CMD &> /dev/null; then
    echo -e "${RED}错误: 未找到 python3${NC}"
    exit 1
fi

PY_VERSION=$($PYTHON_CMD -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo -e "检测到 Python 版本: ${GREEN}$PY_VERSION${NC}"

# 虽然建议 3.11+，但 3.8+ 通常也能跑，这里做基础检查
if [ $(echo "$PY_VERSION < 3.8" | bc -l) -eq 1 ]; then
    echo -e "${RED}错误: Python 版本过低，需要 3.8+${NC}"
    exit 1
fi

echo -e "\n${YELLOW}步骤 4: 准备部署目录${NC}"
if [ ! -d "$INSTALL_DIR" ]; then
    useradd -r -s /bin/false -m -d $INSTALL_DIR $PROJECT_NAME || true
    mkdir -p $WORKSPACE_DIR $LOG_DIR $DATA_DIR
else
    echo -e "${YELLOW}目录 $INSTALL_DIR 已存在，将进行更新部署${NC}"
fi

if [ "$SOURCE_CHOICE" == "1" ]; then
    echo "正在克隆代码..."
    rm -rf $WORKSPACE_DIR/*
    git clone $REPO_URL $WORKSPACE_DIR
else
    echo "正在同步本地代码..."
    # 排除虚拟环境和隐藏文件
    rsync -av --exclude 'venv' --exclude '.git' --exclude '__pycache__' "$LOCAL_CODE_DIR/" "$WORKSPACE_DIR/"
fi

chown -R $PROJECT_NAME:$PROJECT_NAME $INSTALL_DIR

echo -e "\n${YELLOW}步骤 5: 配置虚拟环境${NC}"
cd $WORKSPACE_DIR
if [ ! -d "venv" ]; then
    sudo -u $PROJECT_NAME $PYTHON_CMD -m venv venv
fi

echo "安装依赖包..."
sudo -u $PROJECT_NAME ./venv/bin/pip install --upgrade pip
sudo -u $PROJECT_NAME ./venv/bin/pip install -r requirements.txt

echo -e "\n${YELLOW}步骤 6: 生成配置文件${NC}"
if [ ! -f "$INSTALL_DIR/.env" ]; then
    SECRET_KEY=$(openssl rand -base64 32)
    cat > "$INSTALL_DIR/.env" << EOF
# ReadZen 生产环境配置
FLASK_ENV=production
SECRET_KEY=$SECRET_KEY
DATA_DIR=$DATA_DIR
HOST=0.0.0.0
PORT=15000
WORKERS=4
TIMEOUT=120
LOG_DIR=$LOG_DIR
EOF
    chmod 600 "$INSTALL_DIR/.env"
    chown $PROJECT_NAME:$PROJECT_NAME "$INSTALL_DIR/.env"
    echo -e "${GREEN}.env 文件已生成${NC}"
else
    echo -e "${YELLOW}.env 文件已存在，跳过生成${NC}"
fi

echo -e "\n${YELLOW}步骤 7: 配置 systemd 服务${NC}"
cat > $SERVICE_FILE << EOF
[Unit]
Description=ReadZen - Daily Article Reader Service
After=network.target

[Service]
User=$PROJECT_NAME
Group=$PROJECT_NAME
WorkingDirectory=$WORKSPACE_DIR
Environment="PATH=$WORKSPACE_DIR/venv/bin"
EnvironmentFile=$INSTALL_DIR/.env
ExecStart=$WORKSPACE_DIR/venv/bin/gunicorn \
    --chdir $WORKSPACE_DIR \
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

echo -e "\n${YELLOW}步骤 8: 启动服务${NC}"
systemctl daemon-reload
systemctl enable $PROJECT_NAME
systemctl restart $PROJECT_NAME

echo -e "\n${GREEN}=================================================${NC}"
echo -e "${GREEN}🎉 ReadZen 部署完成！${NC}"
echo -e "${GREEN}=================================================${NC}"

PORT=$(grep "PORT=" "$INSTALL_DIR/.env" | cut -d'=' -f2)

echo -e "\n服务状态:"
systemctl status $PROJECT_NAME --no-pager | grep "Active:"

echo -e "\n访问地址:"

PUBLIC_IP=$(curl -s https://ifconfig.me 2>/dev/null || echo "")
if [ -n "$PUBLIC_IP" ]; then
    echo -e "👉 ${YELLOW}公网地址: http://${PUBLIC_IP}:${PORT}${NC}"
fi


echo -e "\n局域网地址:"
if command -v ip &> /dev/null; then
    ip -4 addr show | grep -E "inet.*scope.*(eth|ens|enp|wlan|wlp)" | awk '{print $2}' | cut -d'/' -f1 | while read -r ip; do
        echo -e "👉 ${YELLOW}http://${ip}:${PORT}${NC}"
    done
elif command -v ifconfig &> /dev/null; then
    ifconfig | grep -E "inet.*(eth|ens|enp|wlan|wlp)" | awk '{print $2}' | while read -r ip; do
        echo -e "👉 ${YELLOW}http://${ip}:${PORT}${NC}"
    done
else
    echo -e "${YELLOW}无法获取网卡地址，请使用 ip addr 或 ifconfig 查看${NC}"
fi

echo -e "\n常用命令:"
echo "- 查看日志: sudo journalctl -u $PROJECT_NAME -f"
echo "- 重启服务: sudo systemctl restart $PROJECT_NAME"
echo "- 配置文件: $INSTALL_DIR/.env"
echo "- 代码目录: $WORKSPACE_DIR"
echo -e "${GREEN}=================================================${NC}"
