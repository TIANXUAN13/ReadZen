# 每日一文阅读器

一个简单的每日一文阅读应用，支持本地文章阅读、收藏、用户管理等功能。

## 功能特性

- 📖 每日一文：从 API 获取每日文章
- 📁 本地文章：支持读取本地 txt/md 文件
- ⭐ 收藏功能：登录用户可收藏文章
- 👥 用户管理：管理员可管理用户
- 🌙 深色模式：支持深色/浅色/纸张色主题
- 🔐 用户认证：注册、登录、登出

## 快速开始

### 本地运行

```bash
# 安装依赖
pip install -r requirements.txt

# 运行服务
python server.py

# 访问 http://localhost:5000
```

### Docker 运行

```bash
# 构建镜像
docker build -t daily-article-reader .

# 运行容器
docker run -d -p 5000:5000 \
  -v $(pwd)/data.db:/app/data.db \
  --name daily-article \
  daily-article-reader

# 访问 http://localhost:5000
```

### 使用自定义 admin 密码

```bash
docker build -t daily-article-reader . --build-arg ADMIN_PASSWORD=your_password
```

## Docker Compose

```bash
docker-compose up -d
```

## GitHub Actions 自动构建

### 配置 secrets

在 GitHub 仓库 Settings → Secrets 中添加以下 secrets：

| Secret Name | Description |
|-------------|-------------|
| `DOCKERHUB_USERNAME` | Docker Hub 用户名 |
| `DOCKERHUB_TOKEN` | Docker Hub Access Token |
| `GITHUB_TOKEN` | GitHub Token（自动提供）|

### 使用方法

1. 进入 GitHub 仓库的 Actions 页面
2. 选择 "Docker Build & Release" workflow
3. 点击 "Run workflow"
4. 输入参数：
   - `tag`: 镜像标签（如 `v1.0.0`、`latest`）
   - `password`: admin 用户密码（可选，默认 `admin123`）
5. 点击 "Run workflow"

### 构建产物

- Docker Hub 镜像：`yourusername/daily-article-reader:<tag>`
- GitHub Release（当 tag 不是 `latest` 时）：
  - `daily-article-reader.tar` - Docker 镜像备份
  - `daily-article-reader.tar.sha256` - 校验文件

## 默认账户

- 用户名：`admin`
- 密码：`admin123`（可在构建时通过 `ADMIN_PASSWORD` 环境变量修改）

## 项目结构

```
├── index.html          # 前端页面
├── server.py           # Flask 后端
├── database.py         # SQLite 数据库操作
├── requirements.txt    # Python 依赖
├── Dockerfile          # Docker 构建文件
├── docker-compose.yml  # Docker Compose 配置
├── .github/
│   └── workflows/
│       └── docker-release.yml  # GitHub Actions
└── .gitignore          # Git 忽略配置
```

## API 接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/auth/register` | POST | 用户注册 |
| `/api/auth/login` | POST | 用户登录 |
| `/api/auth/logout` | POST | 退出登录 |
| `/api/auth/me` | GET | 获取当前用户 |
| `/api/daily` | GET | 获取每日一文 |
| `/api/favorites` | GET | 获取收藏列表 |
| `/api/favorites` | POST | 添加收藏 |
| `/api/favorites` | DELETE | 删除收藏 |
| `/api/admin/users` | GET | 获取用户列表（仅 admin） |
| `/api/admin/users/<id>` | DELETE | 删除用户（仅 admin） |

## License

MIT
