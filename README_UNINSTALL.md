# ReadZen 卸载指南

安全卸载 ReadZen 服务及相关文件。

## 快速卸载

### 1. 运行卸载脚本

```bash
cd ReadZen
sudo ./scripts/uninstall.sh
```

### 2. 按提示操作

```
>>> ReadZen 卸载程序 <<<

请输入安装目录 [默认: /opt/readzen]: 
# 直接回车或输入自定义路径

即将执行以下操作:
1. 停止并禁用 readzen 服务
2. 删除 systemd 服务文件
3. 删除安装目录: /opt/readzen

警告: 此操作将删除所有数据，包括:
- 数据库文件 (/opt/readzen/data/)
- 日志文件 (/opt/readzen/logs/)
- 配置文件 (/opt/readzen/.env)
- 代码目录 (/opt/readzen/workspace/)

确认卸载? 输入 'yes' 继续: yes

步骤 1: 停止并禁用服务
步骤 2: 删除 systemd 服务文件
步骤 3: 删除安装目录
步骤 4: 删除系统用户

=================================================
✅ ReadZen 已成功卸载
=================================================
```

## 手动卸载

如需手动卸载，按以下步骤操作：

### 1. 停止并禁用服务

```bash
sudo systemctl stop readzen
sudo systemctl disable readzen
```

### 2. 删除服务文件

```bash
sudo rm -f /etc/systemd/system/readzen.service
sudo systemctl daemon-reload
```

### 3. 删除安装目录（可选）

**完全删除：**
```bash
sudo rm -rf /opt/readzen
```

**保留数据：**
```bash
# 先备份数据
sudo cp -r /opt/readzen/data ~/readzen_backup

# 删除其他文件，保留数据
sudo rm -rf /opt/readzen/workspace
sudo rm -rf /opt/readzen/logs
# 保留 /opt/readzen/data
```

### 4. 删除系统用户

```bash
sudo userdel readzen
```

### 5. 清理日志（可选）

```bash
# 清理 systemd 日志
sudo journalctl --vacuum-time=1d --unit=readzen
```

## 数据备份

卸载前建议备份重要数据：

```bash
# 备份数据库和上传的文件
sudo tar -czf ~/readzen_backup_$(date +%Y%m%d).tar.gz -C /opt/readzen data/

# 备份配置
cp /opt/readzen/.env ~/readzen_env_backup
```

## 恢复数据

如需恢复之前的数据：

```bash
# 重新安装 ReadZen
sudo ./scripts/deploy.sh

# 停止服务
sudo systemctl stop readzen

# 恢复数据
sudo rm -rf /opt/readzen/data
sudo tar -xzf ~/readzen_backup_20240130.tar.gz -C /opt/readzen
sudo chown -R readzen:readzen /opt/readzen/data

# 重启服务
sudo systemctl start readzen
```

## 常见问题

### 服务无法停止

```bash
# 强制停止
sudo systemctl kill readzen
# 或
sudo pkill -f gunicorn
```

### 权限不足

```bash
# 使用 sudo 运行所有命令
sudo -i  # 切换到 root 用户
cd /opt/readzen
rm -rf *
```

### 端口仍被占用

```bash
# 查找占用 15000 端口的进程
sudo lsof -i:15000

# 强制结束
sudo kill -9 <PID>
```

## 完整清理清单

卸载后检查以下项目是否已删除：

- [ ] systemd 服务: `/etc/systemd/system/readzen.service`
- [ ] 安装目录: `/opt/readzen`
- [ ] 系统用户: `readzen`
- [ ] 运行中的进程: `ps aux | grep gunicorn`
- [ ] 开放端口: `sudo lsof -i:15000`

## 重新安装

如需重新安装：

```bash
# 1. 清理残留
sudo ./scripts/uninstall.sh

# 2. 重新部署
sudo ./scripts/deploy.sh
```

---
**卸载脚本位置**: `scripts/uninstall.sh`
