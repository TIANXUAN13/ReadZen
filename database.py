import sqlite3
import os
from werkzeug.security import generate_password_hash, check_password_hash

# 使用与 server.py 相同的数据目录
DATA_DIR = os.environ.get("DATA_DIR", "./data")
# 确保目录存在并设置正确的权限（兼容 bind mount）
os.makedirs(DATA_DIR, exist_ok=True, mode=0o775)
DB_PATH = os.path.join(DATA_DIR, "data.db")


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
    # 上传的文章存储表 - 使用 BLOB 存储中文内容确保编码正确
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
    conn.commit()
    conn.close()


def get_user_by_username(username):
    conn = get_conn()
    cur = conn.execute("SELECT * FROM users WHERE username = ?", (username,))
    row = cur.fetchone()
    conn.close()
    return row


def create_user(username, password):
    hashed = generate_password_hash(password)
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO users (username, password) VALUES (?, ?)", (username, hashed)
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
