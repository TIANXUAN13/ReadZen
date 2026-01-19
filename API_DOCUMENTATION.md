# 每日一文 - API使用文档

## 基础信息

- **基础URL**: `http://localhost:5000` (默认)
- **认证方式**: Session (Cookies)
- **数据格式**: JSON

---

## 🔐 认证API

### 1. 用户注册

**端点**: `POST /api/auth/register`

**请求参数**:
```json
{
  "username": "用户名",
  "password": "密码"
}
```

**成功响应** (200):
```json
{
  "id": 1,
  "username": "用户名"
}
```

**错误响应** (400):
```json
{
  "error": "user exists"
}
```

**使用案例**:
```bash
curl -X POST http://localhost:5000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"zhangsan","password":"password123"}' \
  --cookie-jar cookies.txt
```

```javascript
// JavaScript fetch 示例
const response = await fetch('http://localhost:5000/api/auth/register', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  credentials: 'include',
  body: JSON.stringify({
    username: 'zhangsan',
    password: 'password123'
  })
});
const data = await response.json();
console.log(data); // {id: 1, username: 'zhangsan'}
```

---

### 2. 用户登录

**端点**: `POST /api/auth/login`

**请求参数**:
```json
{
  "username": "用户名",
  "password": "密码"
}
```

**成功响应** (200):
```json
{
  "id": 1,
  "username": "用户名"
}
```

**错误响应** (401):
```json
{
  "error": "invalid credentials"
}
```

**使用案例**:
```bash
curl -X POST http://localhost:5000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"zhangsan","password":"password123"}' \
  --cookie-jar cookies.txt
```

```javascript
// JavaScript fetch 示例
const response = await fetch('http://localhost:5000/api/auth/login', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  credentials: 'include',
  body: JSON.stringify({
    username: 'zhangsan',
    password: 'password123'
  })
});
const data = await response.json();
console.log(data); // {id: 1, username: 'zhangsan'}
```

---

### 3. 获取当前用户信息

**端点**: `GET /api/auth/me`

**需要认证**: 是

**成功响应** (200):
```json
{
  "id": 1,
  "username": "用户名"
}
```

**错误响应** (401):
```json
{
  "error": "not logged in"
}
```

**使用案例**:
```bash
curl http://localhost:5000/api/auth/me \
  --cookie cookies.txt
```

```javascript
// JavaScript fetch 示例
const response = await fetch('http://localhost:5000/api/auth/me', {
  method: 'GET',
  credentials: 'include'
});
const data = await response.json();
console.log(data); // {id: 1, username: 'zhangsan'}
```

---

### 4. 用户登出

**端点**: `POST /api/auth/logout`

**需要认证**: 是

**成功响应** (200):
```json
{
  "ok": true
}
```

**使用案例**:
```bash
curl -X POST http://localhost:5000/api/auth/logout \
  --cookie cookies.txt
```

```javascript
// JavaScript fetch 示例
const response = await fetch('http://localhost:5000/api/auth/logout', {
  method: 'POST',
  credentials: 'include'
});
const data = await response.json();
console.log(data); // {ok: true}
```

---

### 5. 修改密码

**端点**: `POST /api/auth/change-password`

**需要认证**: 是

**请求参数**:
```json
{
  "old_password": "原密码",
  "new_password": "新密码"
}
```

**成功响应** (200):
```json
{
  "ok": true
}
```

**错误响应** (401):
```json
{
  "error": "invalid old password"
}
```

**使用案例**:
```bash
curl -X POST http://localhost:5000/api/auth/change-password \
  -H "Content-Type: application/json" \
  -d '{"old_password":"password123","new_password":"newpass456"}' \
  --cookie cookies.txt
```

```javascript
// JavaScript fetch 示例
const response = await fetch('http://localhost:5000/api/auth/change-password', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  credentials: 'include',
  body: JSON.stringify({
    old_password: 'password123',
    new_password: 'newpass456'
  })
});
const data = await response.json();
console.log(data); // {ok: true}
```

---

## ⭐ 收藏API

### 1. 获取收藏列表

**端点**: `GET /api/favorites`

**需要认证**: 是

**成功响应** (200):
```json
[
  {
    "id": 1,
    "fav_id": 123,
    "title": "文章标题",
    "author": "作者",
    "content": "<p>文章内容</p>",
    "dateAdded": "2026-01-19T12:00:00.000Z"
  }
]
```

**错误响应** (401):
```json
{
  "error": "unauthorized"
}
```

**使用案例**:
```bash
curl http://localhost:5000/api/favorites \
  --cookie cookies.txt
```

```javascript
// JavaScript fetch 示例
const response = await fetch('http://localhost:5000/api/favorites', {
  method: 'GET',
  credentials: 'include'
});
const favorites = await response.json();
console.log(favorites); // 收藏文章数组
```

---

### 2. 添加收藏

**端点**: `POST /api/favorites`

**需要认证**: 是

**请求参数**:
```json
{
  "id": "文章ID",
  "title": "文章标题",
  "author": "作者",
  "content": "文章内容HTML"
}
```

**成功响应** (200):
```json
{
  "id": 123
}
```

**错误响应** (401):
```json
{
  "error": "unauthorized"
}
```

**使用案例**:
```bash
curl -X POST http://localhost:5000/api/favorites \
  -H "Content-Type: application/json" \
  -d '{
    "id":"article123",
    "title":"春江花月夜",
    "author":"张若虚",
    "content":"<p>春江潮水连海平，海上明月共潮生...</p>"
  }' \
  --cookie cookies.txt
```

```javascript
// JavaScript fetch 示例
const response = await fetch('http://localhost:5000/api/favorites', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  credentials: 'include',
  body: JSON.stringify({
    id: 'article123',
    title: '春江花月夜',
    author: '张若虚',
    content: '<p>春江潮水连海平，海上明月共潮生...</p>'
  })
});
const data = await response.json();
console.log(data); // {id: 123}
```

---

### 3. 删除收藏

**端点**: `DELETE /api/favorites?id={fav_id}`

**需要认证**: 是

**URL参数**:
- `id`: 收藏记录ID (必填)

**成功响应** (200):
```json
{
  "deleted": 123
}
```

**错误响应** (401):
```json
{
  "error": "unauthorized"
}
```

**使用案例**:
```bash
curl -X DELETE "http://localhost:5000/api/favorites?id=123" \
  --cookie cookies.txt
```

```javascript
// JavaScript fetch 示例
const response = await fetch('http://localhost:5000/api/favorites?id=123', {
  method: 'DELETE',
  credentials: 'include'
});
const data = await response.json();
console.log(data); // {deleted: 123}
```

---

## 📚 每日文章API

### 获取每日文章

**端点**: `GET /api/daily`

**需要认证**: 否

**说明**: 从 `https://api.qhsou.com/api/one.php` 获取每日文章并返回

**成功响应** (200):
```json
{
  "id": "abc123",
  "title": "文章标题",
  "author": "作者",
  "content": "<p>文章内容HTML</p>"
}
```

**错误响应** (502):
```json
{
  "error": "failed to fetch daily",
  "detail": "详细错误信息"
}
```

**使用案例**:
```bash
curl http://localhost:5000/api/daily
```

```javascript
// JavaScript fetch 示例
const response = await fetch('http://localhost:5000/api/daily');
const article = await response.json();
console.log(article);
// {
//   id: "abc123",
//   title: "文章标题",
//   author: "作者",
//   content: "<p>文章内容HTML</p>"
// }
```

---

## 👨‍💼 管理员API

> ⚠️ 所有管理员API需要当前用户为 `admin` 用户

### 1. 获取所有用户

**端点**: `GET /api/admin/users`

**需要认证**: 是 (仅admin)

**成功响应** (200):
```json
[
  {
    "id": 1,
    "username": "admin",
    "created_at": "2026-01-01T00:00:00.000Z"
  },
  {
    "id": 2,
    "username": "zhangsan",
    "created_at": "2026-01-15T10:30:00.000Z"
  }
]
```

**错误响应** (401):
```json
{
  "error": "unauthorized"
}
```

**错误响应** (403):
```json
{
  "error": "forbidden"
}
```

**使用案例**:
```bash
# 首先以admin登录
curl -X POST http://localhost:5000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}' \
  --cookie cookies.txt

# 获取用户列表
curl http://localhost:5000/api/admin/users \
  --cookie cookies.txt
```

```javascript
// JavaScript fetch 示例
const response = await fetch('http://localhost:5000/api/admin/users', {
  method: 'GET',
  credentials: 'include'
});
const users = await response.json();
console.log(users); // 用户数组
```

---

### 2. 删除用户

**端点**: `DELETE /api/admin/users/{user_id}`

**需要认证**: 是 (仅admin)

**URL参数**:
- `user_id`: 要删除的用户ID (必填)

**成功响应** (200):
```json
{
  "deleted": 2
}
```

**错误响应** (400):
```json
{
  "error": "cannot delete yourself"
}
```

**错误响应** (401):
```json
{
  "error": "unauthorized"
}
```

**错误响应** (403):
```json
{
  "error": "forbidden"
}
```

**使用案例**:
```bash
curl -X DELETE http://localhost:5000/api/admin/users/2 \
  --cookie cookies.txt
```

```javascript
// JavaScript fetch 示例
const response = await fetch('http://localhost:5000/api/admin/users/2', {
  method: 'DELETE',
  credentials: 'include'
});
const data = await response.json();
console.log(data); // {deleted: 2}
```

---

## 📝 完整使用示例

### 示例1: 完整的用户流程

```javascript
// 1. 注册用户
await fetch('http://localhost:5000/api/auth/register', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  credentials: 'include',
  body: JSON.stringify({ username: 'user1', password: 'pass123' })
});

// 2. 登录
await fetch('http://localhost:5000/api/auth/login', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  credentials: 'include',
  body: JSON.stringify({ username: 'user1', password: 'pass123' })
});

// 3. 获取每日文章
const articleRes = await fetch('http://localhost:5000/api/daily');
const article = await articleRes.json();

// 4. 添加收藏
await fetch('http://localhost:5000/api/favorites', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  credentials: 'include',
  body: JSON.stringify({
    id: article.id,
    title: article.title,
    author: article.author,
    content: article.content
  })
});

// 5. 获取收藏列表
const favsRes = await fetch('http://localhost:5000/api/favorites', {
  credentials: 'include'
});
const favorites = await favsRes.json();

// 6. 修改密码
await fetch('http://localhost:5000/api/auth/change-password', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  credentials: 'include',
  body: JSON.stringify({
    old_password: 'pass123',
    new_password: 'newpass456'
  })
});

// 7. 登出
await fetch('http://localhost:5000/api/auth/logout', {
  method: 'POST',
  credentials: 'include'
});
```

### 示例2: 管理员操作流程

```javascript
// 1. 以admin登录
await fetch('http://localhost:5000/api/auth/login', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  credentials: 'include',
  body: JSON.stringify({ username: 'admin', password: 'admin123' })
});

// 2. 获取所有用户
const usersRes = await fetch('http://localhost:5000/api/admin/users', {
  credentials: 'include'
});
const users = await usersRes.json();

// 3. 删除指定用户（不能删除自己）
if (users.length > 1) {
  await fetch(`http://localhost:5000/api/admin/users/${users[1].id}`, {
    method: 'DELETE',
    credentials: 'include'
  });
}
```

---

## 📊 错误码说明

| 状态码 | 说明 |
|--------|------|
| 200 | 请求成功 |
| 400 | 请求参数错误 |
| 401 | 未认证或认证失败 |
| 403 | 权限不足 |
| 502 | 上游服务错误（如每日文章API失败） |

---

## 🔧 环境变量

- `SECRET_KEY`: Flask session密钥（默认: super-secret-key）
- `ADMIN_PASSWORD`: 管理员密码（默认: admin123）
- `PORT`: 服务器端口（默认: 5000）
- `HOST`: 服务器地址（默认: 0.0.0.0）

---

## 📦 数据库结构

### users表
```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### favorites表
```sql
CREATE TABLE favorites (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    article_id TEXT NOT NULL,
    title TEXT NOT NULL,
    author TEXT,
    content TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
```

---

## 🚀 快速开始

### 启动服务器

```bash
# 使用Python
python server.py

# 使用Docker
docker-compose up
```

### 默认管理员账户

- **用户名**: admin
- **密码**: admin123 (可通过 `ADMIN_PASSWORD` 环境变量修改)

---

## 💡 注意事项

1. 所有需要认证的API都需要使用 `credentials: 'include'` 来发送cookies
2. Session会话默认在浏览器关闭后失效
3. 管理员API只能由 `admin` 用户访问
4. 每日文章API是代理到第三方服务，可能会因网络问题失败
5. 用户名必须唯一，注册时会检查重复

---

## 📞 支持与反馈

如有问题，请查看项目README或提交Issue。