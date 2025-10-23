from flask import Flask, jsonify, request
from data import qawms_data, verses_data
from functools import wraps
from datetime import datetime, timezone
import hashlib
import secrets

app = Flask(__name__)

# --- بيانات الأقوام والآيات (لغرض المثال، في تطبيق حقيقي ستكون قاعدة بيانات) ---
# تم نقلها إلى data.py


# --- تحسين الأداء: الكاش (Caching) ---
# سنستخدم ديكوريتور بسيط للكاش في الذاكرة. في الإنتاج، ستحتاج إلى Redis أو Memcached.
cache = {}

def cached(timeout=60):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            cache_key = hashlib.md5((request.path + str(request.args)).encode('utf-8')).hexdigest()
            if cache_key in cache:
                data, timestamp = cache[cache_key]
                if (app.config['START_TIME'] - timestamp).total_seconds() < timeout: # Use app start time for simplicity
                    return jsonify(data) # Return cached data

            # If not in cache or expired, call the original function
            response = f(*args, **kwargs)
            # Assuming f returns a jsonify response, we need to extract data
            # For simplicity, we'll store the direct data before jsonify
            cache[cache_key] = (response.json, app.config['START_TIME']) # Store the data and current time
            return response
        return decorated_function
    return decorator


# --- تأمين الـ API: تحديد معدل الطلبات (Rate Limiting) و API Keys و JWT ---

# 1. API Keys (مثال بسيط)
# في تطبيق حقيقي: ستكون المفاتيح مخزنة بشكل آمن في قاعدة بيانات
API_KEYS = {
    "your_super_secret_api_key_1": {"owner": "DeveloperA"},
    "your_super_secret_api_key_2": {"owner": "DeveloperB"}
}

def require_api_key(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        api_key = request.headers.get('X-API-Key')
        if not api_key or api_key not in API_KEYS:
            return jsonify({"error": "Unauthorized: Invalid or missing API Key"}), 401
        return f(*args, **kwargs)
    return decorated_function

# 2. تحديد معدل الطلبات (Rate Limiting)
# لتطبيق حقيقي، استخدم مكتبة مثل `Flask-Limiter`
# هنا مثال توضيحي بسيط جدًا يعتمد على الذاكرة وقد لا يكون فعالاً في بيئة متعددة الخوادم
rate_limit_counts = {}
RATE_LIMIT = 5 # 5 requests per minute per IP
RATE_LIMIT_WINDOW = 60 # seconds

def rate_limit(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        ip_address = request.remote_addr
        current_time = app.config['START_TIME'] # Use app start time for simplicity

        if ip_address not in rate_limit_counts:
            rate_limit_counts[ip_address] = []

        # Remove old requests outside the window
        rate_limit_counts[ip_address] = [
            t for t in rate_limit_counts[ip_address]
            if (current_time - t).total_seconds() < RATE_LIMIT_WINDOW
        ]

        if len(rate_limit_counts[ip_address]) >= RATE_LIMIT:
            return jsonify({"error": f"Rate limit exceeded. Try again in {RATE_LIMIT_WINDOW} seconds."}), 429

        rate_limit_counts[ip_address].append(current_time)
        return f(*args, **kwargs)
    return decorated_function

# 3. JWT (JSON Web Tokens)
# تستخدم للمصادقة بعد تسجيل الدخول، لغرض التوضيح فقط
# في تطبيق حقيقي: ستحتاج إلى مكتبة مثل `Flask-JWT-Extended`
# مفتاح سري لتوقيع JWT (يجب أن يكون قويًا وفي متغير بيئة في الإنتاج)
SECRET_KEY = secrets.token_urlsafe(32)
app.config['SECRET_KEY'] = SECRET_KEY # For session, not directly JWT signing here

# مثال على توليد توكن (لن نطبقه فعليًا هنا للمصادقة الكاملة)
# def create_jwt(user_id):
#     payload = {
#         'user_id': user_id,
#         'exp': datetime.utcnow() + timedelta(minutes=30)
#     }
#     return jwt.encode(payload, app.config['SECRET_KEY'], algorithm='HS256')

# --- نقاط النهاية (API Endpoints) ---

@app.route('/')
def home():
    return "مرحبًا بك في API البيانات القرآنية!"

@app.route('/qawms', methods=['GET'])
@require_api_key
@rate_limit
@cached(timeout=300) # كاش لمدة 5 دقائق
def get_qawms():
    """يرجع قائمة بكل الأقوام."""
    return jsonify({"qawms": qawms_data})

@app.route('/qawms/<int:qawm_id>', methods=['GET'])
@require_api_key
@rate_limit
@cached(timeout=300)
def get_qawm(qawm_id):
    """يرجع تفاصيل قوم معين بناءً على ID."""
    qawm = next((q for q in qawms_data if q["id"] == qawm_id), None)
    if qawm:
        return jsonify(qawm)
    return jsonify({"error": "Qawm not found"}), 404

@app.route('/verses', methods=['GET'])
@require_api_key
@rate_limit
@cached(timeout=300)
def get_all_verses():
    """يرجع قائمة بكل الآيات."""
    return jsonify({"verses": verses_data})

@app.route('/verses/<int:verse_id>', methods=['GET'])
@require_api_key
@rate_limit
@cached(timeout=300)
def get_verse(verse_id):
    """يرجع تفاصيل آية معينة بناءً على ID."""
    verse = next((v for v in verses_data if v["id"] == verse_id), None)
    if verse:
        return jsonify(verse)
    return jsonify({"error": "Verse not found"}), 404

@app.route('/qawms/<int:qawm_id>/verses', methods=['GET'])
@require_api_key
@rate_limit
@cached(timeout=300)
def get_verses_for_qawm(qawm_id):
    """يرجع الآيات المتعلقة بقوم معين."""
    qawm = next((q for q in qawms_data if q["id"] == qawm_id), None)
    if not qawm:
        return jsonify({"error": "Qawm not found"}), 404

    related_verses = [v for v in verses_data if v["qawm_id"] == qawm_id]
    return jsonify({"qawm_name": qawm["name"], "verses": related_verses})

if __name__ == '__main__':
    from datetime import datetime, timedelta, timezone

    # تخزين وقت بدء التشغيل لاستخدامه في الكاش أو تحديد معدل الطلبات
    app.config['START_TIME'] = datetime.now(timezone.utc)

    # تشغيل التطبيق في وضع الإنتاج
    app.run(debug=False)  # في بيئة الإنتاج: debug=False واستخدم خادم WSGI مثل Gunicorn
