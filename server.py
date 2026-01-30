import os
import re
import sqlite3
import requests
import shutil  # 新增：用于文件复制
import random
import string
import base64
import zipfile
import io
from io import BytesIO
from functools import wraps
from flask import Flask, request, jsonify, session, send_from_directory, send_file
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from captcha.image import ImageCaptcha  # 验证码图片生成

# 导入数据库函数
from database import (
    init_db,
    get_user_by_username,
    create_user,
    verify_user,
    get_favorites,
    add_favorite,
    remove_favorite,
    get_all_users,
    delete_user,
    get_uploaded_articles,
    save_uploaded_article,
    delete_uploaded_article,
    delete_all_uploaded_articles,
    DATA_DIR,
    DB_PATH,
)

PRELOADED_DB_PATH = "/app/preloaded_data/data.db"

# Docker容器中的预置数据目录路径（仅在容器中有效）
app = Flask(__name__, static_folder=".")

# 生成随机密钥作为 Secret Key（如果没有设置环境变量）
def generate_secret_key():
    """生成64字节的随机密钥"""
    return os.urandom(64).hex()

# 从环境变量获取密钥，如果未设置则生成随机密钥并记录警告
SECRET_KEY = os.environ.get("SECRET_KEY")
if not SECRET_KEY:
    SECRET_KEY = generate_secret_key()
    print(f"[WARNING] SECRET_KEY not set in environment. Generated random key: {SECRET_KEY}")
    print("[WARNING] Please set SECRET_KEY environment variable for production to maintain session persistence!")

app.secret_key = SECRET_KEY

# 根据环境变量设置调试模式，生产环境默认禁用
DEBUG_MODE = os.environ.get("FLASK_DEBUG", "false").lower() in ("true", "1", "yes")

# 设置请求体最大大小为 10MB
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # 10MB

# CORS 配置：仅允许同源请求（前端和后端在同一域名下）
# 如果前端部署在不同域名，需要设置 ALLOWED_ORIGINS 环境变量，多个域名用逗号分隔
ALLOWED_ORIGINS = os.environ.get("ALLOWED_ORIGINS", "").strip()
if ALLOWED_ORIGINS:
    origins_list = [origin.strip() for origin in ALLOWED_ORIGINS.split(",")]
    CORS(app, supports_credentials=True, origins=origins_list)
    print(f"[INFO] CORS enabled for origins: {origins_list}")
else:
    # 默认允许同源请求
    CORS(app, supports_credentials=True)
    print("[INFO] CORS enabled for same-origin requests only")

# 速率限制配置
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://"  # 使用内存存储速率限制
)

# 工具函数：从文章内容头部移除标题/作者等元信息（可选，防止上传时把元信息当作正文内容）
def strip_header_lines(text: str) -> str:
    if not isinstance(text, str):
        return text
    try:
        lines = text.splitlines()
        idx = 0
        while idx < len(lines):
            line = lines[idx].strip()
            if line == "":
                idx += 1
                continue
            # 移除以 标题、作者 开头的行，包含可能的冒号/全角冒号等
            if line.startswith("标题") or line.startswith("作者"):
                idx += 1
                continue
            break
        return "\n".join(lines[idx:])
    except Exception:
        return text

# --- 验证码系统开始 ---

# 密码强度验证
def validate_password(password: str) -> tuple[bool, str]:
    """
    验证密码强度
    要求：
    - 最少8个字符
    - 至少包含一个字母（大小写均可）
    - 至少包含一个数字
    """
    if not password:
        return False, "密码不能为空"

    if len(password) < 8:
        return False, "密码长度至少为8个字符"

    if not re.search(r'[a-zA-Z]', password):
        return False, "密码必须包含至少一个字母"

    if not re.search(r'\d', password):
        return False, "密码必须包含至少一个数字"

    return True, ""

# 验证码图片生成器
captcha_generator = ImageCaptcha(width=160, height=60)


def generate_custom_captcha(code: str, bg_color: str = '#fdfbf7', text_color: str = '#374151'):
    """生成自定义背景色的验证码图片"""
    from PIL import Image, ImageDraw, ImageFont
    import random
    
    # 图片尺寸：匹配前端容器尺寸（包含边框）
    # 容器：152px × 48px，减去边框4px得到内部区域
    width, height = 152, 48
    img = Image.new('RGB', (width, height), bg_color)
    draw = ImageDraw.Draw(img)
    
    # 字体设置
    try:
        font = ImageFont.truetype("arial.ttf", 24)
    except:
        try:
            font = ImageFont.load_default()
        except:
            font = None
    
    # 添加干扰线
    for _ in range(2):
        x1 = random.randint(0, width - 1)
        y1 = random.randint(0, height - 1)
        x2 = random.randint(0, width - 1)
        y2 = random.randint(0, height - 1)
        draw.line([(x1, y1), (x2, y2)], fill=text_color, width=1)
    
    # 添加干扰点
    for _ in range(15):
        x = random.randint(0, width - 1)
        y = random.randint(0, height - 1)
        draw.point((x, y), fill=text_color)
    
    # 动态计算字符布局，确保完全填充
    n_chars = len(code)
    
    # 使用极小的边距，让字符充分利用空间
    margin = 8
    available_width = width - 2 * margin
    char_width = available_width // n_chars if n_chars > 0 else available_width
    
    # 绘制验证码文字，完全填充整个可用宽度
    for i, char in enumerate(code):
        # 计算字符基础位置
        base_x = margin + i * char_width
        
        # 添加微小随机偏移（减少以保持填充效果）
        x = base_x + random.randint(-1, 1)
        
        # 垂直居中，加上微小偏移
        if font:
            try:
                # 获取字符实际大小以进行精确居中
                bbox = draw.textbbox((0, 0), char, font=font)
                char_width_actual = bbox[2] - bbox[0]
                char_height_actual = bbox[3] - bbox[1]
                
                # 水平居中在字符格子内
                x_offset = (char_width - char_width_actual) // 2
                x = base_x + x_offset + random.randint(-1, 1)
                
                # 垂直居中在整个图片内
                y = (height - char_height_actual) // 2 + random.randint(-2, 2)
                
                draw.text((x, y), char, fill=text_color, font=font)
            except:
                # 降级处理
                x = base_x + random.randint(-1, 1)
                y = (height - 20) // 2 + random.randint(-2, 2)
                draw.text((x, y), char, fill=text_color, font=font)
        else:
            x = base_x + random.randint(-1, 1)
            y = (height - 20) // 2 + random.randint(-2, 2)
            draw.text((x, y), char, fill=text_color)
    
    # 转换为字节流
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format='PNG')
    return img_byte_arr.getvalue()


@app.route("/api/captcha", methods=["GET"])
def get_captcha():
    """生成并返回验证码图片"""
    # 生成随机验证码
    captcha_code = "".join(random.choices(string.ascii_uppercase + string.digits, k=4))
    # 存储到会话中
    session["captcha"] = captcha_code
    session["captcha_time"] = datetime.now().timestamp()

    # 生成自定义验证码图片（使用主题色）
    image_data = generate_custom_captcha(captcha_code, bg_color='#fdfbf7', text_color='#374151')

    # 返回base64编码的图片
    return jsonify(
        {
            "captcha_image": base64.b64encode(image_data).decode("utf-8"),
            "expires_in": 300,  # 5分钟有效期
        }
    )


@app.route("/api/captcha/verify", methods=["POST"])
def verify_captcha():
    """验证验证码"""
    data = request.json or {}
    user_input = data.get("captcha", "").strip().upper()
    session_captcha = session.get("captcha")
    captcha_time = session.get("captcha_time", 0)

    # 检查验证码是否过期（5分钟）
    if datetime.now().timestamp() - captcha_time > 300:
        session.pop("captcha", None)
        session.pop("captcha_time", None)
        return jsonify({"valid": False, "error": "验证码已过期"}), 400

    # 验证验证码
    if not session_captcha:
        return jsonify({"valid": False, "error": "验证码不存在或已过期"}), 400

    if user_input != session_captcha:
        return jsonify({"valid": False, "error": "验证码错误"}), 400

    # 验证成功后清除验证码，防止重复使用
    session.pop("captcha", None)
    session.pop("captcha_time", None)

    return jsonify({"valid": True})


# --- 验证码系统结束 ---

# --- 核心修改开始 ---


def initialize_application():
    """初始化应用数据逻辑"""
    # 1. 确保数据目录存在
    if not os.path.exists(DATA_DIR):
        try:
            os.makedirs(DATA_DIR, mode=0o775, exist_ok=True)
            print(f"[INFO] Created data directory: {DATA_DIR}")
        except OSError as e:
            print(
                f"[ERROR] Failed to create data directory {DATA_DIR}. Permission denied? Error: {e}"
            )
            return  # 已处理错误，直接返回

    # 2. 检查数据库文件是否存在
    db_exists = os.path.exists(DB_PATH)
    if db_exists:
        # 数据库文件存在，检查是否可读（处理 bind mount 权限问题）
        try:
            # 尝试打开数据库验证其完整性
            test_conn = sqlite3.connect(DB_PATH)
            test_conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
            test_conn.close()
            print(f"[INFO] Valid database found at {DB_PATH}, skipping initialization.")
        except sqlite3.Error as e:
            # 数据库损坏或不可读，需要重新创建
            print(f"[WARNING] Database at {DB_PATH} is corrupted or unreadable: {e}")
            # 备份损坏的文件
            backup_path = (
                DB_PATH + f".corrupted.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            )
            try:
                shutil.move(DB_PATH, backup_path)
                print(f"[INFO] Backed up corrupted database to {backup_path}")
            except Exception as backup_error:
                print(f"[WARNING] Failed to backup database: {backup_error}")
            db_exists = False
        except PermissionError as e:
            # 权限问题，尝试修复权限
            print(f"[WARNING] Permission error accessing {DB_PATH}: {e}")
            try:
                os.chmod(DB_PATH, 0o666)
                print(f"[INFO] Attempted to fix permissions on {DB_PATH}")
            except Exception as perm_error:
                print(f"[WARNING] Failed to fix permissions: {perm_error}")

    if not db_exists:
        print(f"[INFO] Database not found or invalid at {DB_PATH}")
        # 3. 策略：如果镜像里有预置数据，先复制过来
        if os.path.exists(PRELOADED_DB_PATH):
            try:
                print(f"[INFO] Found preloaded data at {PRELOADED_DB_PATH}, copying...")
                shutil.copy2(PRELOADED_DB_PATH, DB_PATH)
                # 确保复制后的文件权限正确
                os.chmod(DB_PATH, 0o666)
                print(f"[INFO] Database initialized from preloaded data.")
            except Exception as e:
                print(f"[ERROR] Failed to copy preloaded data: {e}")
                # 复制失败（通常是权限问题），尝试创建一个新的
                print("[INFO] Attempting to create a new empty database instead...")
                init_db()
        else:
            # 4. 如果没有预置数据，直接初始化新的
            print("[INFO] No preloaded data found. Initializing new database...")
            init_db()

    # 5. 确保 admin 用户存在 (无论数据库是复制的还是新建的)
    create_admin_user()


def create_admin_user():
    """启动时检查并创建 admin 用户"""
    try:
        # 此时数据库一定存在了，建立连接检查
        # 注意：这里需要临时修改 database.py 里的 DB_PATH 或者确保 database.py 引用的是正确的全局路径
        # 由于 database.py 里的路径可能是硬编码或导入时确定的，建议在 database.py 里也做相应调整
        # 这里假设 database.py 会读取环境变量或者我们不需要修改它（如果它每次都读文件）
        # 为了保险，我们重新初始化一下 database 模块里的路径（如果那是动态的）
        # 但通常 init_db() 里的逻辑依赖 database.py 的实现。
        # 简单调用 get_user_by_username 即可，如果报错说明表结构不对，再次 init_db
        try:
            admin_user = get_user_by_username("admin")
        except sqlite3.OperationalError:
            # 如果表不存在（比如复制的文件损坏），重新建表
            init_db()
            admin_user = get_user_by_username("admin")

        if not admin_user:
            admin_password = os.environ.get("ADMIN_PASSWORD", "admin123")
            if admin_password:
                create_user("admin", admin_password)
                print(f"[INFO] Admin user created with password: {admin_password}")
    except Exception as e:
        print(f"[WARNING] Failed to check/create admin user: {e}")


# 执行初始化
with app.app_context():
    initialize_application()

# --- 核心修改结束 ---


# Scheme A: Root path serves frontend index.html
@app.route("/", methods=["GET"])
def index():
    return send_from_directory(".", "index.html")


# Authentication APIs
@app.route("/api/auth/register", methods=["POST"])
@limiter.limit("5 per hour")  # 限制注册接口每小时最多5次请求
def register():
    data = request.json or {}
    username = data.get("username")
    password = data.get("password")
    confirm_password = data.get("confirm_password", data.get("password_confirm", ""))
    captcha = data.get("captcha", "").strip().upper()

    # 用户名和密码必填验证
    if not username or not password:
        return jsonify({"error": "username和password是必填项"}), 400

    # 用户名长度限制（3-20个字符）
    if len(username) < 3 or len(username) > 20:
        return jsonify({"error": "用户名长度必须在3-20个字符之间"}), 400

    # 用户名格式验证（只允许字母、数字、下划线）
    if not re.match(r'^[a-zA-Z0-9_]+$', username):
        return jsonify({"error": "用户名只能包含字母、数字和下划线"}), 400

    # 密码强度验证
    is_valid, error_msg = validate_password(password)
    if not is_valid:
        return jsonify({"error": error_msg}), 400

    # 校验两次输入的密码是否一致
    if confirm_password != password:
        return jsonify({"error": "两次输入的密码不一致"}), 400

    # 验证码验证
    session_captcha = session.get("captcha")
    captcha_time = session.get("captcha_time", 0)

    if not session_captcha:
        return jsonify({"error": "验证码已过期，请刷新后重试"}), 400

    if datetime.now().timestamp() - captcha_time > 300:
        session.pop("captcha", None)
        session.pop("captcha_time", None)
        return jsonify({"error": "验证码已过期，请刷新后重试"}), 400

    if captcha != session_captcha:
        return jsonify({"error": "验证码错误"}), 400

    if get_user_by_username(username):
        return jsonify({"error": "user exists"}), 400

    # 验证成功后清除验证码，防止重复使用
    session.pop("captcha", None)
    session.pop("captcha_time", None)

    user_id = create_user(username, password)
    session["user_id"] = user_id
    session["username"] = username
    return jsonify({"id": user_id, "username": username})


@app.route("/api/auth/login", methods=["POST"])
@limiter.limit("30 per hour")  # 限制登录接口每小时最多30次请求（有验证码保护，可适当放宽）
def login():
    data = request.json or {}
    username = data.get("username")
    password = data.get("password")
    captcha = data.get("captcha", "").strip().upper()

    # 验证码验证（登录时也需要验证码，防止暴力破解）
    session_captcha = session.get("captcha")
    captcha_time = session.get("captcha_time", 0)

    if not session_captcha:
        return jsonify({"error": "验证码已过期，请刷新后重试"}), 400

    if datetime.now().timestamp() - captcha_time > 300:
        session.pop("captcha", None)
        session.pop("captcha_time", None)
        return jsonify({"error": "验证码已过期，请刷新后重试"}), 400

    if captcha != session_captcha:
        return jsonify({"error": "验证码错误"}), 400

    # 验证成功后清除验证码，防止重复使用
    session.pop("captcha", None)
    session.pop("captcha_time", None)

    ok, user_id = verify_user(username, password)
    if not ok:
        return jsonify({"error": "invalid credentials"}), 401
    session["user_id"] = user_id
    session["username"] = username
    return jsonify({"id": user_id, "username": username})


@app.route("/api/auth/me", methods=["GET"])
def me():
    if "user_id" in session:
        return jsonify({"id": session["user_id"], "username": session.get("username")})
    return jsonify({"error": "not logged in"}), 401


@app.route("/api/auth/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"ok": True})


@app.route("/api/auth/change-password", methods=["POST"])
@limiter.limit("5 per hour")  # 限制修改密码接口每小时最多5次请求
def change_password():
    if "user_id" not in session:
        return jsonify({"error": "unauthorized"}), 401
    data = request.json or {}
    old_password = data.get("old_password")
    new_password = data.get("new_password")
    if not old_password or not new_password:
        return jsonify({"error": "old_password and new_password are required"}), 400

    # 验证新密码强度
    is_valid, error_msg = validate_password(new_password)
    if not is_valid:
        return jsonify({"error": error_msg}), 400

    user_id = session["user_id"]
    user = get_user_by_username(session["username"])
    if not user or not check_password_hash(user["password"], old_password):
        return jsonify({"error": "invalid old password"}), 401
    from werkzeug.security import generate_password_hash

    hashed = generate_password_hash(new_password)
    # 确保这里连接的是正确的 DB_PATH
    conn = sqlite3.connect(DB_PATH)
    conn.execute("UPDATE users SET password = ? WHERE id = ?", (hashed, user_id))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


# Favorites CRUD (SQLite-backed)
@app.route("/api/favorites", methods=["GET", "POST", "DELETE"])
def favorites():
    if request.method == "GET":
        if "user_id" not in session:
            return jsonify({"error": "unauthorized"}), 401
        user_id = session["user_id"]
        items = get_favorites(user_id)
        return jsonify(items)

    if request.method == "POST":
        if "user_id" not in session:
            return jsonify({"error": "unauthorized"}), 401
        user_id = session["user_id"]
        article = request.json or {}
        fid = add_favorite(user_id, article)
        return jsonify({"id": fid})

    if request.method == "DELETE":
        if "user_id" not in session:
            return jsonify({"error": "unauthorized"}), 401
        user_id = session["user_id"]
        fav_id = request.args.get("id")
        if not fav_id:
            return jsonify({"error": "id required"}), 400
        remove_favorite(user_id, int(fav_id))
        return jsonify({"deleted": int(fav_id)})

    # 不支持的方法
    return jsonify({"error": "method not allowed"}), 405


# 上传文章相关API
@app.route("/api/uploaded", methods=["GET"])
def get_uploaded():
    """获取所有上传的文章"""
    articles = get_uploaded_articles()
    return jsonify(articles)


@app.route("/api/uploaded", methods=["POST"])
def save_uploaded():
    """保存上传的文章"""
    data = request.json or {}
    title = data.get("title")
    author = data.get("author", "佚名")
    content = data.get("content")
    file_name = data.get("fileName", "")
    file_size = data.get("fileSize", 0)

    if not title or not content:
        return jsonify({"error": "title和content是必填项"}), 400

    # 处理可能的本地文档头部元信息（如标题、作者等）
    content = strip_header_lines(content)
    # 重新评估长度/非空性
    if content is None:
        content = ""
    if not title or not content:
        return jsonify({"error": "title和content是必填项"}), 400

    # 重复校验：检查数据库中是否已存在相同标题和内容的文章
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "SELECT id FROM uploaded_articles WHERE title = ? AND content = ?",
        (title, content),
    )
    existing = cur.fetchone()
    conn.close()

    if existing:
        return jsonify({"id": existing[0], "message": "文章已存在，跳过上传"}), 200

    article_id = save_uploaded_article(title, author, content, file_name, file_size)
    return jsonify({"id": article_id})


@app.route("/api/uploaded/<int:article_id>", methods=["DELETE"])
def delete_uploaded(article_id):
    """删除上传的文章"""
    delete_uploaded_article(article_id)
    return jsonify({"deleted": article_id})


@app.route("/api/uploaded/clear", methods=["POST"])
def clear_uploaded():
    """清空上传的文章列表"""
    count = 0
    try:
        count = delete_all_uploaded_articles()
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    return jsonify({"cleared": True, "count": count})


# 收藏文章批量操作
@app.route("/api/favorites/batch-add", methods=["POST"])
def batch_add_favorites():
    """批量添加收藏（用于一键收藏所有上传的文章）"""
    if "user_id" not in session:
        return jsonify({"error": "unauthorized"}), 401

    data = request.json or {}
    articles = data.get("articles", [])

    if not articles:
        return jsonify({"error": "articles required"}), 400

    user_id = session["user_id"]
    added_count = 0

    for article in articles:
        try:
            add_favorite(user_id, article)
            added_count += 1
        except:
            continue

    return jsonify({"added": added_count})


# 批量下载收藏文章
@app.route("/api/favorites/download", methods=["POST"])
def download_favorites_zip():
    """批量下载收藏文章（返回zip文件）"""
    if "user_id" not in session:
        return jsonify({"error": "unauthorized"}), 401

    data = request.json or {}
    articles = data.get("articles", [])

    if not articles:
        return jsonify({"error": "articles required"}), 400

    # 创建内存中的zip文件
    memory_file = io.BytesIO()
    with zipfile.ZipFile(memory_file, "w", zipfile.ZIP_DEFLATED) as zf:
        for idx, article in enumerate(articles):
            title = article.get("title", f"文章{idx + 1}")
            author = article.get("author", "")
            content = article.get("content", "")

            # 清理文件名中的非法字符
            safe_title = "".join(c for c in title if c.isalnum() or c in " _-()")
            if not safe_title:
                safe_title = f"article_{idx + 1}"

            file_name = f"{safe_title}.txt"
            file_content = f"标题: {title}\n作者: {author}\n\n{content}"
            zf.writestr(file_name, file_content)

    memory_file.seek(0)

    return send_file(
        memory_file,
        mimetype="application/zip",
        as_attachment=True,
        download_name="收藏文章.zip",
    )


# Daily article proxy
@app.route("/api/daily", methods=["GET"])
@limiter.limit("100 per hour")  # 提高限制以支持健康检查频繁访问
def daily():
    """获取每日一文"""
    # 备用API列表
    api_urls = [
        "https://api.qhsou.com/api/one.php"
    ]

    article_data = None

    for api_url in api_urls:
        try:
            # 增加 verify=False 提高在受限网络环境下的兼容性
            resp = requests.get(api_url, timeout=10, verify=False)
            if resp.ok:
                data = resp.json()
                # 尝试多种API返回格式
                if isinstance(data, dict):
                    article_data = {
                        "id": data.get("id")
                        or data.get("date")
                        or str(int.from_bytes(os.urandom(2), "little")),
                        "title": data.get("title")
                        or data.get("c_title")
                        or data.get("tt")
                        or "无标题",
                        "author": data.get("author") or data.get("c_author") or "未知",
                        "content": data.get("content")
                        or data.get("c_content")
                        or data.get("text")
                        or data.get("dc")
                        or "<p>暂无内容</p>",
                    }
                    break
        except Exception as e:
            print(f"[WARNING] Failed to fetch from {api_url}: {e}")
            continue

    # 如果所有API都失败，返回错误 (状态码改为 503 避免触发网关 502)
    if not article_data:
        return jsonify(
            {
                "error": "failed to fetch daily",
                "message": '无法获取每日一文，请检查容器网络连接。你可以通过"上传中心"功能上传本地文章进行阅读。',
            }
        ), 503

    return jsonify(article_data)


# Admin APIs (only admin user can access)
@app.route("/api/admin/users", methods=["GET"])
def admin_users():
    if "user_id" not in session:
        return jsonify({"error": "unauthorized"}), 401
    if session.get("username") != "admin":
        return jsonify({"error": "forbidden"}), 403
    users = get_all_users()
    return jsonify(users)


@app.route("/api/admin/users/<int:user_id>", methods=["DELETE"])
def admin_delete_user(user_id):
    if "user_id" not in session:
        return jsonify({"error": "unauthorized"}), 401
    if session.get("username") != "admin":
        return jsonify({"error": "forbidden"}), 403
    if user_id == session["user_id"]:
        return jsonify({"error": "cannot delete yourself"}), 400
    delete_user(user_id)
    return jsonify({"deleted": user_id})


# 在应用启动时执行初始化
# 放在全局作用域，确保 Gunicorn 导入时也能执行
with app.app_context():
    try:
        initialize_application()
    except Exception as e:
        print(f"[CRITICAL] Failed to initialize application: {e}")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 15000))
    host = os.environ.get("HOST", "0.0.0.0")
    # 使用环境变量控制调试模式，生产环境默认禁用
    app.run(host=host, port=port, debug=DEBUG_MODE)
