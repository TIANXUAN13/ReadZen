import sqlite3
import os
from werkzeug.security import generate_password_hash, check_password_hash
from cryptography.fernet import Fernet

# 使用与 server.py 相同的数据目录
DATA_DIR = os.environ.get("DATA_DIR", "./data")
# 确保目录存在并设置正确的权限（兼容 bind mount）
os.makedirs(DATA_DIR, exist_ok=True, mode=0o775)
DB_PATH = os.path.join(DATA_DIR, "data.db")


def get_conn():
    """获取数据库连接 - 必须在 ENCRYPTION_KEY 初始化之前定义"""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    # 启用 UTF-8 支持
    conn.execute('PRAGMA encoding = "UTF-8"')
    return conn


# 加密密钥 - 生产环境应使用环境变量
ENCRYPTION_KEY = os.environ.get("ENCRYPTION_KEY")

def get_encryption_key():
    """获取加密密钥，确保数据库已初始化"""
    global ENCRYPTION_KEY
    
    if ENCRYPTION_KEY:
        return ENCRYPTION_KEY
    
    # 先确保数据库已初始化
    try:
        init_db()
    except Exception:
        pass
    
    # 尝试从数据库获取
    key_from_db = None
    try:
        conn = get_conn()
        row = conn.execute("SELECT config_value FROM system_config WHERE config_key = 'encryption_key'").fetchone()
        conn.close()
        if row and row["config_value"]:
            key_from_db = row["config_value"]
    except Exception:
        pass
    
    if key_from_db:
        ENCRYPTION_KEY = key_from_db
    else:
        ENCRYPTION_KEY = Fernet.generate_key().decode()
        try:
            conn = get_conn()
            conn.execute(
                "INSERT OR REPLACE INTO system_config (config_key, config_value, updated_at) VALUES ('encryption_key', ?, datetime('now'))",
                (ENCRYPTION_KEY,)
            )
            conn.commit()
            conn.close()
            print("[WARNING] ENCRYPTION_KEY not set. Generated and saved to database.")
        except Exception as e:
            print(f"[WARNING] ENCRYPTION_KEY not set. Generated random key (not persisted): {e}")

    return ENCRYPTION_KEY

# 初始化密钥
get_encryption_key()

_cipher = None
def get_cipher():
    global _cipher
    if _cipher is None:
        key = get_encryption_key()
        try:
            _cipher = Fernet(key.encode() if isinstance(key, str) else key)
        except Exception:
            _cipher = Fernet.generate_key()
            _cipher = Fernet(_cipher)
    return _cipher

def encrypt_password(password):
    if not password:
        return password
    cipher = get_cipher()
    return cipher.encrypt(password.encode()).decode()

def decrypt_password(encrypted_password):
    if not encrypted_password:
        return encrypted_password
    try:
        cipher = get_cipher()
        return cipher.decrypt(encrypted_password.encode()).decode()
    except Exception as e:
        print(f"[ERROR] Failed to decrypt password: {e}")
        return encrypted_password


def init_db():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """CREATE TABLE IF NOT EXISTS users (
           id INTEGER PRIMARY KEY AUTOINCREMENT,
           username TEXT UNIQUE NOT NULL,
           password TEXT NOT NULL,
           email TEXT,
           created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )"""
    )
    cur.execute(
        """CREATE TABLE IF NOT EXISTS favorites (
           id INTEGER PRIMARY KEY AUTOINCREMENT,
           user_id INTEGER NOT NULL,
           title TEXT NOT NULL,
           author TEXT,
           content TEXT,
           article_id TEXT,
           date_added TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
           FOREIGN KEY(user_id) REFERENCES users(id)
        )"""
    )
    cur.execute(
        """CREATE TABLE IF NOT EXISTS uploaded_articles (
           id INTEGER PRIMARY KEY AUTOINCREMENT,
           user_id INTEGER,
           title TEXT NOT NULL,
           author TEXT,
           content TEXT NOT NULL,
           file_name TEXT,
           file_size INTEGER,
           date_added TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
           FOREIGN KEY(user_id) REFERENCES users(id)
        )"""
    )
    cur.execute(
        """CREATE TABLE IF NOT EXISTS system_config (
           id INTEGER PRIMARY KEY AUTOINCREMENT,
           config_key TEXT UNIQUE NOT NULL,
           config_value TEXT,
           description TEXT,
           updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )"""
    )
    cur.execute(
        """CREATE TABLE IF NOT EXISTS password_resets (
           id INTEGER PRIMARY KEY AUTOINCREMENT,
           user_id INTEGER,
           email TEXT NOT NULL,
           code TEXT NOT NULL,
           expires_at TIMESTAMP NOT NULL,
           used INTEGER DEFAULT 0,
           created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
           FOREIGN KEY(user_id) REFERENCES users(id)
        )"""
    )
    
    cur.execute(
        """CREATE TABLE IF NOT EXISTS email_verifications (
           id INTEGER PRIMARY KEY AUTOINCREMENT,
           user_id INTEGER,
           email TEXT NOT NULL,
           code TEXT NOT NULL,
           type TEXT NOT NULL,
           expires_at TIMESTAMP NOT NULL,
           used INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id)
         )"""
    )
    
    cur.execute("PRAGMA table_info(users)")
    columns = [col[1] for col in cur.fetchall()]
    if 'email' not in columns:
        cur.execute("ALTER TABLE users ADD COLUMN email TEXT")
    if 'email_verified' not in columns:
        cur.execute("ALTER TABLE users ADD COLUMN email_verified INTEGER DEFAULT 0")
    if 'role' not in columns:
        cur.execute("ALTER TABLE users ADD COLUMN role TEXT DEFAULT 'user'")

    # 确保管理员账户的 role 字段正确（兼容老版本数据库）
    # 优先通过现有 admin 角色更新，其次通过用户名 admin 更新
    cur.execute("UPDATE users SET role = 'admin' WHERE role = 'admin' OR username = 'admin'")

    cur.execute("PRAGMA table_info(uploaded_articles)")
    article_columns = [col[1] for col in cur.fetchall()]
    if 'user_id' not in article_columns:
        cur.execute("ALTER TABLE uploaded_articles ADD COLUMN user_id INTEGER REFERENCES users(id)")

    # 文章源表（用于每日一文等功能的自定义来源）
    cur.execute(
        """CREATE TABLE IF NOT EXISTS article_sources (
           id INTEGER PRIMARY KEY AUTOINCREMENT,
           name TEXT NOT NULL,
           url TEXT NOT NULL,
           api_validation TEXT,
           polling_algorithm TEXT DEFAULT 'sequential',
           enabled INTEGER DEFAULT 1,
           order_index INTEGER DEFAULT 0,
           created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
           updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )"""
    )
    
    # 添加默认源（如果还不存在）
    cur.execute("SELECT COUNT(*) FROM article_sources WHERE url = ?", ("https://api.qhsou.com/api/one.php",))
    if cur.fetchone()[0] == 0:
        cur.execute(
            """INSERT INTO article_sources (name, url, api_validation, polling_algorithm, enabled, order_index)
               VALUES (?, ?, ?, ?, ?, ?)""",
            ("默认源", "https://api.qhsou.com/api/one.php", None, "sequential", 1, 0)
        )
    
    conn.commit()
    conn.close()


def get_user_by_username(username):
    conn = get_conn()
    cur = conn.execute("SELECT * FROM users WHERE username = ?", (username,))
    row = cur.fetchone()
    conn.close()
    return row


def create_user(username, password, email=None):
    hashed = generate_password_hash(password)
    conn = get_conn()
    cur = conn.cursor()
    role = 'admin' if username == 'admin' else 'user'
    cur.execute(
        "INSERT INTO users (username, password, email, role) VALUES (?, ?, ?, ?)", 
        (username, hashed, email, role)
    )
    conn.commit()
    user_id = cur.lastrowid
    conn.close()
    return user_id


def verify_user(username, password):
    user = get_user_by_username(username)
    if not user:
        return False, None
    ok = check_password_hash(user["password"], password)
    return ok, user["id"] if ok else None


def add_favorite(user_id, article):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO favorites (user_id, title, author, content, article_id)
                   VALUES (?, ?, ?, ?, ?)""",
        (
            user_id,
            article.get("title"),
            article.get("author"),
            article.get("content"),
            article.get("id"),
        ),
    )
    conn.commit()
    fid = cur.lastrowid
    conn.close()
    return fid


def get_favorites(user_id):
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM favorites WHERE user_id = ? ORDER BY date_added DESC", (user_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def remove_favorite(user_id, fav_id):
    conn = get_conn()
    conn.execute(
        "DELETE FROM favorites WHERE id = ? AND user_id = ?", (fav_id, user_id)
    )
    conn.commit()
    conn.close()


def get_user_username(user_id):
    conn = get_conn()
    row = conn.execute("SELECT username FROM users WHERE id=?", (user_id,)).fetchone()
    conn.close()
    return row["username"] if row else None


def get_all_users():
    conn = get_conn()
    rows = conn.execute(
        "SELECT id, username, created_at FROM users ORDER BY created_at DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_users_paginated(page=1, per_page=10):
    """获取分页用户列表"""
    conn = get_conn()
    offset = (page - 1) * per_page

    # 获取总数
    total_row = conn.execute("SELECT COUNT(*) as count FROM users").fetchone()
    total = total_row["count"] if total_row else 0

    # 获取分页数据
    rows = conn.execute(
        "SELECT id, username, created_at FROM users ORDER BY created_at DESC LIMIT ? OFFSET ?",
        (per_page, offset)
    ).fetchall()
    conn.close()

    return {
        "users": [dict(r) for r in rows],
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": (total + per_page - 1) // per_page if per_page > 0 else 0
    }


def delete_users(user_ids):
    """批量删除用户"""
    conn = get_conn()
    placeholders = ",".join("?" * len(user_ids))
    # 先删除用户的收藏
    conn.execute(f"DELETE FROM favorites WHERE user_id IN ({placeholders})", user_ids)
    # 删除用户
    conn.execute(f"DELETE FROM users WHERE id IN ({placeholders})", user_ids)
    conn.commit()
    conn.close()
    return len(user_ids)


def get_user_by_id(user_id):
    conn = get_conn()
    row = conn.execute(
        "SELECT id, username, created_at FROM users WHERE id = ?", (user_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def delete_user(user_id):
    conn = get_conn()
    # 先删除用户的收藏
    conn.execute("DELETE FROM favorites WHERE user_id = ?", (user_id,))
    # 删除用户
    conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()


# 上传文章相关函数
def save_uploaded_article(title, author, content, file_name="", file_size=0, user_id=None):
    """保存上传的文章（确保 UTF-8 编码）"""
    if isinstance(title, str):
        title = title.encode("utf-8").decode("utf-8")
    if isinstance(author, str):
        author = author.encode("utf-8").decode("utf-8")
    if isinstance(content, str):
        content = content.encode("utf-8").decode("utf-8")
    if isinstance(file_name, str):
        file_name = file_name.encode("utf-8").decode("utf-8")

    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO uploaded_articles (user_id, title, author, content, file_name, file_size)
                   VALUES (?, ?, ?, ?, ?, ?)""",
        (user_id, title, author, content, file_name, file_size),
    )
    conn.commit()
    article_id = cur.lastrowid
    conn.close()
    return article_id


def get_uploaded_article_by_id(article_id):
    """根据ID获取上传的文章"""
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM uploaded_articles WHERE id = ?", (article_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_uploaded_articles():
    """获取所有上传的文章"""
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM uploaded_articles ORDER BY date_added DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_uploaded_article(article_id):
    """删除上传的文章"""
    conn = get_conn()
    conn.execute("DELETE FROM uploaded_articles WHERE id = ?", (article_id,))
    conn.commit()
    conn.close()

def delete_all_uploaded_articles():
    """删除所有已上传的文章，并返回被删除的数量（若数据库不返回精确删除数，则返回前的计数）"""
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("SELECT COUNT(*) FROM uploaded_articles")
        count = cur.fetchone()[0]
        cur.execute("DELETE FROM uploaded_articles")
        conn.commit()
    except Exception:
        count = 0
        conn.rollback()
    finally:
        cur.close()
        conn.close()
    return count


def get_config(key, default=None):
    """获取系统配置"""
    conn = get_conn()
    row = conn.execute(
        "SELECT config_value FROM system_config WHERE config_key = ?", (key,)
    ).fetchone()
    conn.close()
    return row["config_value"] if row else default


def set_config(key, value, description=None):
    """设置系统配置"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO system_config (config_key, config_value, description, updated_at)
           VALUES (?, ?, ?, datetime('now'))
           ON CONFLICT(config_key) DO UPDATE SET 
           config_value = excluded.config_value,
           description = COALESCE(excluded.description, description),
           updated_at = datetime('now')""",
        (key, value, description)
    )
    conn.commit()
    conn.close()


def get_smtp_config():
    """获取 SMTP 配置"""
    config_keys = [
        'smtp_server', 'smtp_port', 'smtp_username', 'smtp_password',
        'smtp_from_name', 'smtp_from_email', 'smtp_use_ssl', 'smtp_use_tls', 'smtp_enabled'
    ]
    config = {}
    for key in config_keys:
        value = get_config(key)
        if value is not None:
            if key == 'smtp_password' and value:
                try:
                    decrypted = decrypt_password(value)
                    if decrypted:
                        value = decrypted
                    else:
                        value = None
                except Exception as e:
                    print(f"[WARNING] Failed to decrypt SMTP password: {e}")
                    value = None
            config[key] = value
    return config


def update_smtp_config(config_dict):
    """更新 SMTP 配置"""
    descriptions = {
        'smtp_server': 'SMTP服务器地址',
        'smtp_port': 'SMTP端口',
        'smtp_username': 'SMTP用户名',
        'smtp_password': 'SMTP密码（加密存储）',
        'smtp_from_name': '发件人名称',
        'smtp_from_email': '发件人邮箱',
        'smtp_use_ssl': '使用SSL',
        'smtp_use_tls': '使用TLS',
        'smtp_enabled': '启用SMTP'
    }
    for key, value in config_dict.items():
        if key == 'smtp_password' and value:
            value = encrypt_password(value)
        set_config(key, value, descriptions.get(key))


def get_user_by_email(email):
    """通过邮箱获取用户"""
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM users WHERE email = ?", (email,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def update_user_email(user_id, email):
    """更新用户邮箱"""
    conn = get_conn()
    conn.execute(
        "UPDATE users SET email = ? WHERE id = ?", (email, user_id)
    )
    conn.commit()
    conn.close()


def update_user_password(user_id, new_password):
    """更新用户密码"""
    hashed = generate_password_hash(new_password)
    conn = get_conn()
    conn.execute(
        "UPDATE users SET password = ? WHERE id = ?", (hashed, user_id)
    )
    conn.commit()
    conn.close()


def update_user_username(user_id, new_username):
    """更新用户名"""
    conn = get_conn()
    try:
        conn.execute(
            "UPDATE users SET username = ? WHERE id = ?", (new_username, user_id)
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        # 用户名已存在
        return False
    finally:
        conn.close()


def create_password_reset(email, code, expires_at, user_id=None):
    """创建密码重置记录"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO password_resets (user_id, email, code, expires_at)
           VALUES (?, ?, ?, ?)""",
        (user_id, email, code, expires_at)
    )
    conn.commit()
    reset_id = cur.lastrowid
    conn.close()
    return reset_id


def get_valid_password_reset(email, code):
    """获取有效的密码重置记录"""
    conn = get_conn()
    row = conn.execute(
        """SELECT * FROM password_resets 
           WHERE email = ? AND code = ? AND used = 0 
           AND expires_at > datetime('now')
           ORDER BY created_at DESC LIMIT 1""",
        (email, code)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def mark_password_reset_used(reset_id):
    """标记密码重置记录为已使用"""
    conn = get_conn()
    conn.execute(
        "UPDATE password_resets SET used = 1 WHERE id = ?", (reset_id,)
    )
    conn.commit()
    conn.close()


def cleanup_expired_resets():
    """清理过期的密码重置记录"""
    conn = get_conn()
    conn.execute(
        "DELETE FROM password_resets WHERE expires_at < datetime('now') OR used = 1"
    )
    conn.commit()
    conn.close()


def create_email_verification(user_id, email, code, verification_type='register', expires_at=None):
    """创建邮箱验证记录
    verification_type: 'register' 注册验证, 'change_email' 修改邮箱验证
    """
    from datetime import datetime, timedelta
    if expires_at is None:
        expires_at = datetime.now() + timedelta(minutes=30)
    
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO email_verifications (user_id, email, code, type, expires_at)
           VALUES (?, ?, ?, ?, ?)""",
        (user_id, email, code, verification_type, expires_at)
    )
    conn.commit()
    verification_id = cur.lastrowid
    conn.close()
    return verification_id


def get_valid_email_verification(email, code, verification_type=None):
    """获取有效的邮箱验证记录"""
    conn = get_conn()
    if verification_type:
        row = conn.execute(
            """SELECT * FROM email_verifications 
               WHERE email = ? AND code = ? AND type = ? AND used = 0 
               AND expires_at > datetime('now')
               ORDER BY created_at DESC LIMIT 1""",
            (email, code, verification_type)
        ).fetchone()
    else:
        row = conn.execute(
            """SELECT * FROM email_verifications 
               WHERE email = ? AND code = ? AND used = 0 
               AND expires_at > datetime('now')
               ORDER BY created_at DESC LIMIT 1""",
            (email, code)
        ).fetchone()
    conn.close()
    return dict(row) if row else None


def mark_email_verification_used(verification_id):
    """标记邮箱验证记录为已使用"""
    conn = get_conn()
    conn.execute(
        "UPDATE email_verifications SET used = 1 WHERE id = ?", (verification_id,)
    )
    conn.commit()
    conn.close()


def verify_user_email(user_id):
    """标记用户邮箱为已验证"""
    conn = get_conn()
    conn.execute(
        "UPDATE users SET email_verified = 1 WHERE id = ?", (user_id,)
    )
    conn.commit()
    conn.close()


def update_user_email_with_verification(user_id, email):
    """更新用户邮箱并标记为已验证"""
    conn = get_conn()
    conn.execute(
        "UPDATE users SET email = ?, email_verified = 1 WHERE id = ?", 
        (email, user_id)
    )
    conn.commit()
    conn.close()


def get_user_email_verified(user_id):
    """获取用户邮箱验证状态"""
    conn = get_conn()
    row = conn.execute(
        "SELECT email, email_verified FROM users WHERE id = ?", (user_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


# ---------------- Article sources management ----------------
def add_article_source(name, url, api_validation=None, polling_algorithm="sequential", enabled=1, order_index=None):
    """添加文章源，返回新插入的 id"""
    conn = get_conn()
    cur = conn.cursor()
    if order_index is None:
        # 默认放在末尾，根据现有最大 order_index +1
        row = conn.execute("SELECT MAX(order_index) as m FROM article_sources").fetchone()
        max_idx = row["m"] if row and row["m"] is not None else -1
        order_index = max_idx + 1

    cur.execute(
        """INSERT INTO article_sources (name, url, api_validation, polling_algorithm, enabled, order_index)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (name, url, api_validation, polling_algorithm, int(enabled), order_index)
    )
    conn.commit()
    sid = cur.lastrowid
    conn.close()
    return sid


def get_article_sources(enabled_only=False):
    conn = get_conn()
    if enabled_only:
        rows = conn.execute("SELECT * FROM article_sources WHERE enabled = 1 ORDER BY order_index ASC, id ASC").fetchall()
    else:
        rows = conn.execute("SELECT * FROM article_sources ORDER BY order_index ASC, id ASC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_article_source_by_id(source_id):
    conn = get_conn()
    row = conn.execute("SELECT * FROM article_sources WHERE id = ?", (source_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def update_article_source(source_id, name=None, url=None, api_validation=None, polling_algorithm=None, enabled=None, order_index=None):
    conn = get_conn()
    cur = conn.cursor()
    # 确认存在
    existing = cur.execute("SELECT * FROM article_sources WHERE id = ?", (source_id,)).fetchone()
    if not existing:
        conn.close()
        return False

    fields = []
    params = []
    if name is not None:
        fields.append("name = ?")
        params.append(name)
    if url is not None:
        fields.append("url = ?")
        params.append(url)
    if api_validation is not None:
        fields.append("api_validation = ?")
        params.append(api_validation)
    if polling_algorithm is not None:
        fields.append("polling_algorithm = ?")
        params.append(polling_algorithm)
    if enabled is not None:
        fields.append("enabled = ?")
        params.append(int(enabled))
    if order_index is not None:
        fields.append("order_index = ?")
        params.append(int(order_index))

    if not fields:
        conn.close()
        return True

    params.append(source_id)
    sql = f"UPDATE article_sources SET {', '.join(fields)}, updated_at = CURRENT_TIMESTAMP WHERE id = ?"
    cur.execute(sql, params)
    conn.commit()
    conn.close()
    return True


def delete_article_source(source_id):
    conn = get_conn()
    conn.execute("DELETE FROM article_sources WHERE id = ?", (source_id,))
    conn.commit()
    conn.close()


def toggle_article_source(source_id):
    conn = get_conn()
    cur = conn.cursor()
    row = cur.execute("SELECT enabled FROM article_sources WHERE id = ?", (source_id,)).fetchone()
    if not row:
        conn.close()
        return False
    new_val = 0 if int(row["enabled"]) else 1
    cur.execute("UPDATE article_sources SET enabled = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (new_val, source_id))
    conn.commit()
    conn.close()
    return True


def get_global_polling_algorithm(default="sequential"):
    val = get_config("global_polling_algorithm", default)
    return val if val in ("sequential", "random") else default


def set_global_polling_algorithm(algorithm):
    if algorithm not in ("sequential", "random"):
        algorithm = "sequential"
    set_config("global_polling_algorithm", algorithm, description="全局文章源轮询算法")
