import sqlite3
import os
from werkzeug.security import generate_password_hash, check_password_hash

# 使用与 server.py 相同的数据目录
DATA_DIR = os.environ.get('DATA_DIR', '/app/data')
os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(DATA_DIR, 'data.db')


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        '''CREATE TABLE IF NOT EXISTS users (
           id INTEGER PRIMARY KEY AUTOINCREMENT,
           username TEXT UNIQUE NOT NULL,
           password TEXT NOT NULL,
           created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )'''
    )
    cur.execute(
        '''CREATE TABLE IF NOT EXISTS favorites (
           id INTEGER PRIMARY KEY AUTOINCREMENT,
           user_id INTEGER NOT NULL,
           title TEXT NOT NULL,
           author TEXT,
           content TEXT,
           article_id TEXT,
           date_added TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
           FOREIGN KEY(user_id) REFERENCES users(id)
        )'''
    )
    conn.commit()
    conn.close()


def get_user_by_username(username):
    conn = get_conn()
    cur = conn.execute('SELECT * FROM users WHERE username = ?', (username,))
    row = cur.fetchone()
    conn.close()
    return row


def create_user(username, password):
    hashed = generate_password_hash(password)
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('INSERT INTO users (username, password) VALUES (?, ?)', (username, hashed))
    conn.commit()
    user_id = cur.lastrowid
    conn.close()
    return user_id


def verify_user(username, password):
    user = get_user_by_username(username)
    if not user:
        return False, None
    ok = check_password_hash(user['password'], password)
    return ok, user['id'] if ok else None


def add_favorite(user_id, article):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('''INSERT INTO favorites (user_id, title, author, content, article_id)
                   VALUES (?, ?, ?, ?, ?)''',
                (user_id, article.get('title'), article.get('author'), article.get('content'), article.get('id')))
    conn.commit()
    fid = cur.lastrowid
    conn.close()
    return fid


def get_favorites(user_id):
    conn = get_conn()
    rows = conn.execute('SELECT * FROM favorites WHERE user_id = ? ORDER BY date_added DESC', (user_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def remove_favorite(user_id, fav_id):
    conn = get_conn()
    conn.execute('DELETE FROM favorites WHERE id = ? AND user_id = ?', (fav_id, user_id))
    conn.commit()
    conn.close()


def get_user_username(user_id):
    conn = get_conn()
    row = conn.execute('SELECT username FROM users WHERE id=?', (user_id,)).fetchone()
    conn.close()
    return row['username'] if row else None


def get_all_users():
    conn = get_conn()
    rows = conn.execute('SELECT id, username, created_at FROM users ORDER BY created_at DESC').fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_user_by_id(user_id):
    conn = get_conn()
    row = conn.execute('SELECT id, username, created_at FROM users WHERE id = ?', (user_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def delete_user(user_id):
    conn = get_conn()
    # 先删除用户的收藏
    conn.execute('DELETE FROM favorites WHERE user_id = ?', (user_id,))
    # 删除用户
    conn.execute('DELETE FROM users WHERE id = ?', (user_id,))
    conn.commit()
    conn.close()
