from flask import Flask, request, jsonify, session, send_from_directory
from flask_cors import CORS
import os
import requests
from database import init_db, get_user_by_username, create_user, verify_user, add_favorite, get_favorites, remove_favorite, get_all_users, get_user_by_id, delete_user

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'super-secret-key')
CORS(app, supports_credentials=True)

# init db on startup
DB_INIT = os.path.exists(os.path.join(os.path.dirname(__file__), 'data.db'))
if not DB_INIT:
    init_db()

# Scheme A: Root path serves frontend index.html
@app.route('/', methods=['GET'])
def index():
    return send_from_directory('.', 'index.html')

# Authentication APIs
@app.route('/api/auth/register', methods=['POST'])
def register():
    data = request.json or {}
    username = data.get('username')
    password = data.get('password')
    if not username or not password:
        return jsonify({'error': 'username和password是必填项'}), 400
    if get_user_by_username(username):
        return jsonify({'error': 'user exists'}), 400
    user_id = create_user(username, password)
    session['user_id'] = user_id
    session['username'] = username
    return jsonify({'id': user_id, 'username': username})

@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.json or {}
    username = data.get('username')
    password = data.get('password')
    ok, user_id = verify_user(username, password)
    if not ok:
        return jsonify({'error': 'invalid credentials'}), 401
    session['user_id'] = user_id
    session['username'] = username
    return jsonify({'id': user_id, 'username': username})

@app.route('/api/auth/me', methods=['GET'])
def me():
    if 'user_id' in session:
        return jsonify({'id': session['user_id'], 'username': session.get('username')})
    return jsonify({'error': 'not logged in'}), 401

@app.route('/api/auth/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'ok': True})

# Favorites CRUD (SQLite-backed)
@app.route('/api/favorites', methods=['GET', 'POST', 'DELETE'])
def favorites():
    if request.method == 'GET':
        if 'user_id' not in session:
            return jsonify({'error': 'unauthorized'}), 401
        user_id = session['user_id']
        items = get_favorites(user_id)
        return jsonify(items)

    if request.method == 'POST':
        if 'user_id' not in session:
            return jsonify({'error': 'unauthorized'}), 401
        user_id = session['user_id']
        article = request.json or {}
        fid = add_favorite(user_id, article)
        return jsonify({'id': fid})

    if request.method == 'DELETE':
        if 'user_id' not in session:
            return jsonify({'error': 'unauthorized'}), 401
        user_id = session['user_id']
        fav_id = request.args.get('id')
        if not fav_id:
            return jsonify({'error': 'id required'}), 400
        remove_favorite(user_id, int(fav_id))
        return jsonify({'deleted': int(fav_id)})

# Daily article proxy
@app.route('/api/daily', methods=['GET'])
def daily():
    try:
        resp = requests.get('https://api.qhsou.com/api/one.php', timeout=5)
        if not resp.ok:
            return jsonify({'error': 'failed to fetch daily'}), 502
        data = resp.json()
        article = {
            'id': data.get('id') or str(int.from_bytes(os.urandom(2), 'little')),
            'title': data.get('title') or data.get('c_title') or '无标题',
            'author': data.get('author') or data.get('c_author') or '未知',
            'content': data.get('content') or data.get('c_content') or '<p>暂无内容</p>'
        }
        return jsonify(article)
    except Exception as e:
        return jsonify({'error': 'failed to fetch daily', 'detail': str(e)}), 502

# Admin APIs (only admin user can access)
@app.route('/api/admin/users', methods=['GET'])
def admin_users():
    if 'user_id' not in session:
        return jsonify({'error': 'unauthorized'}), 401
    # 只有 admin 用户可以访问
    if session.get('username') != 'admin':
        return jsonify({'error': 'forbidden'}), 403
    users = get_all_users()
    return jsonify(users)

@app.route('/api/admin/users/<int:user_id>', methods=['DELETE'])
def admin_delete_user(user_id):
    if 'user_id' not in session:
        return jsonify({'error': 'unauthorized'}), 401
    # 只有 admin 用户可以访问
    if session.get('username') != 'admin':
        return jsonify({'error': 'forbidden'}), 403
    # 不能删除自己
    if user_id == session['user_id']:
        return jsonify({'error': 'cannot delete yourself'}), 400
    delete_user(user_id)
    return jsonify({'deleted': user_id})

@app.before_first_request
def create_admin_user():
    """启动时检查并创建 admin 用户"""
    admin_user = get_user_by_username('admin')
    if not admin_user:
        admin_password = os.environ.get('ADMIN_PASSWORD', 'admin123')
        if admin_password:
            try:
                create_user('admin', admin_password)
                print(f"[INFO] Admin user created with default password: {admin_password}")
            except Exception as e:
                print(f"[WARNING] Failed to create admin user: {e}")

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    host = os.environ.get('HOST', '0.0.0.0')
    app.run(host=host, port=port, debug=True)
