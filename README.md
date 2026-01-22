# ReadZen (每日一文)

一个基于 Flask 的极简禅意阅读器，支持每日一文、本地文件上传、收藏管理及用户系统。

## 功能特性

- 📖 **每日一文**：从 API 获取精选文章，沉浸式阅读体验
- 📁 **上传中心**：支持单个文件及整文件夹上传，自动同步至数据库
- ⭐ **收藏管理**：一键收藏喜欢的文章，支持批量下载为 ZIP
- 👥 **用户系统**：支持多用户注册，内置管理员后台
- 🌙 **禅意视觉**：磨砂玻璃 UI、阅读进度条、衬线体排版、深色模式
- 🔐 **安全可靠**：图形验证码防护，Docker 容器化部署

## 快速开始

### Docker 运行 (推荐)

最简单的方式是使用 Docker 运行：

```bash
docker run -d \
  --name readzen \
  -p 15000:15000 \
  -v $(pwd)/data:/app/data \
  -e ADMIN_PASSWORD=admin123 \
  tianxuan13/readzen:latest
```

访问地址: `http://localhost:15000`

### Docker Compose

```yaml
# docker-compose.yml
version: '3.8'
services:
  readzen:
    image: tianxuan13/readzen:latest
    ports:
      - "15000:15000"
    volumes:
      - ./data:/app/data
    environment:
      - ADMIN_PASSWORD=admin123
```

运行命令：
```bash
docker-compose up -d
```

### 本地开发运行

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 运行服务
python server.py

# 3. 访问 http://localhost:15000
```

## 默认账户

- 用户名：`admin`
- 密码：`admin123` (可通过环境变量 `ADMIN_PASSWORD` 自定义)

## 部署说明

### 挂载数据
务必挂载 `/app/data` 目录以实现数据持久化。所有的用户账号、收藏文章、上传文件都存储在该目录下的 `data.db` 中。

### 端口配置
默认端口已统一为 `15000`。

## GitHub Actions

项目已配置 GitHub Actions 自动构建镜像并推送到 Docker Hub。手动触发工作流时可自定义：
- `branch`: 构建分支
- `tag`: 镜像标签
- `password`: 默认管理员密码

---
MIT License
