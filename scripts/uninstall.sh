#!/bin/bash

# ReadZen 卸载脚本
# 安全卸载 ReadZen 服务及相关文件

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

PROJECT_NAME="readzen"
DEFAULT_INSTALL_DIR="/opt/readzen"
SERVICE_FILE="/etc/systemd/system/readzen.service"

echo -e "${RED}>>> ReadZen 卸载程序 <<<${NC}"

if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}错误: 请使用 root 权限运行 (sudo ./uninstall.sh)${NC}"
    exit 1
fi

read -p "请输入安装目录 [默认: $DEFAULT_INSTALL_DIR]: " INSTALL_DIR
INSTALL_DIR=${INSTALL_DIR:-$DEFAULT_INSTALL_DIR}

if [ ! -d "$INSTALL_DIR" ]; then
    echo -e "${YELLOW}警告: 目录 $INSTALL_DIR 不存在${NC}"
    read -p "是否继续卸载服务文件? [y/N]: " CONTINUE
    if [[ ! $CONTINUE =~ ^[Yy]$ ]]; then
        exit 0
    fi
fi

echo -e "\n${YELLOW}即将执行以下操作:${NC}"
echo "1. 停止并禁用 readzen 服务"
echo "2. 删除 systemd 服务文件"
echo "3. 删除安装目录: $INSTALL_DIR"

echo -e "\n${RED}警告: 此操作将删除所有数据，包括:${NC}"
echo "- 数据库文件 ($INSTALL_DIR/data/)"
echo "- 日志文件 ($INSTALL_DIR/logs/)"
echo "- 配置文件 ($INSTALL_DIR/.env)"
echo "- 代码目录 ($INSTALL_DIR/workspace/)"

read -p "\n确认卸载? 输入 'yes' 继续: " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    echo -e "${YELLOW}已取消卸载${NC}"
    exit 0
fi

echo -e "\n${YELLOW}步骤 1: 停止并禁用服务${NC}"
if systemctl is-active --quiet readzen 2>/dev/null; then
    systemctl stop readzen
    echo "服务已停止"
fi

if systemctl is-enabled --quiet readzen 2>/dev/null; then
    systemctl disable readzen
    echo "服务已禁用"
fi

echo -e "\n${YELLOW}步骤 2: 删除 systemd 服务文件${NC}"
if [ -f "$SERVICE_FILE" ]; then
    rm -f "$SERVICE_FILE"
    systemctl daemon-reload
    echo "服务文件已删除"
else
    echo "服务文件不存在，跳过"
fi

echo -e "\n${YELLOW}步骤 3: 删除安装目录${NC}"
if [ -d "$INSTALL_DIR" ]; then
    read -p "是否保留数据目录? [y/N]: " KEEP_DATA
    if [[ $KEEP_DATA =~ ^[Yy]$ ]]; then
        echo "备份数据到 /tmp/readzen_backup_$(date +%Y%m%d%H%M%S)"
        cp -r "$INSTALL_DIR/data" "/tmp/readzen_backup_$(date +%Y%m%d%H%M%S)" 2>/dev/null || true
    fi
    
    rm -rf "$INSTALL_DIR"
    echo "安装目录已删除: $INSTALL_DIR"
else
    echo "安装目录不存在，跳过"
fi

echo -e "\n${YELLOW}步骤 4: 删除系统用户${NC}"
if id "$PROJECT_NAME" &>/dev/null; then
    userdel "$PROJECT_NAME" 2>/dev/null || true
    echo "系统用户已删除: $PROJECT_NAME"
else
    echo "系统用户不存在，跳过"
fi

echo -e "\n${GREEN}=================================================${NC}"
echo -e "${GREEN}✅ ReadZen 已成功卸载${NC}"
echo -e "${GREEN}=================================================${NC}"

if [[ $KEEP_DATA =~ ^[Yy]$ ]]; then
    echo -e "\n数据已备份至: /tmp/readzen_backup_*"
    echo "如需恢复，请手动复制到新的安装目录"
fi

echo -e "\n残留检查:"
echo "- 服务状态: $(systemctl is-active readzen 2>/dev/null || echo 'inactive')"
echo "- 目录存在: $([ -d "$INSTALL_DIR" ] && echo '是' || echo '否')"
echo -e "${GREEN}=================================================${NC}"
