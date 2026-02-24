import sqlite3
import os
from werkzeug.security import generate_password_hash, check_password_hash
from cryptography.fernet import Fernet

# 使用与 server.py 相同的数据目录
DATA_DIR = os.environ.get("DATA_DIR", "./data")
# 确保目录存在并设置正确的权限（兼容 bind mount）
os.makedirs(DATA_DIR, exist_ok=True, mode=0o775)
DB_PATH = os.path.join(DATA_DIR, "data.db")

# 加密密钥 - 生产环境应使用环境变量
ENCRYPTION_KEY = os.environ.get("ENCRYPTION_KEY")
if not ENCRYPTION_KEY:
    ENCRYPTION_KEY = Fernet.generate_key().decode()
    print("[WARNING] ENCRYPTION_KEY not set. Generated random key.")

_cipher = None
def get_cipher():
    global _cipher
    if _cipher is None:
        try:
            _cipher = Fernet(ENCRYPTION_KEY.encode() if isinstance(ENCRYPTION_KEY, str) else ENCRYPTION_KEY)
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
    except Exception:
        return encrypted_password


def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    # 启用 UTF-8 支持
    conn.execute('PRAGMA encoding = "UTF-8"')
    return conn


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
           title TEXT NOT NULL,
           author TEXT,
           content TEXT NOT NULL,
           file_name TEXT,
           file_size INTEGER,
           date_added TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
def save_uploaded_article(title, author, content, file_name="", file_size=0):
    """保存上传的文章（确保 UTF-8 编码）"""
    # 确保字符串是 UTF-8 编码
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
        """INSERT INTO uploaded_articles (title, author, content, file_name, file_size)
                   VALUES (?, ?, ?, ?, ?)""",
        (title, author, content, file_name, file_size),
    )
    conn.commit()
    article_id = cur.lastrowid
    conn.close()
    return article_id


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
                except Exception:
                    pass
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
