from flask import Flask, jsonify, request
from data import qawms_data, verses_data
from functools import wraps
from datetime import datetime, timezone
import hashlib
import secrets

app = Flask(__name__)

# --- الكاش (Caching) ---
cache = {}

def cached(timeout=60):
    """ديكوريتور للكاش في الذاكرة لمدة معينة (ثواني)."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            cache_key = hashlib.md5((request.path + str(request.args)).encode('utf-8')).hexdigest()
            now = datetime.now(timezone.utc)  # الوقت الحالي
            if cache_key in cache:
                data, timestamp = cache[cache_key]
                if (now - timestamp).total_seconds() < timeout:
                    return jsonify(data)

            response = f(*args, **kwargs)
            cache[cache_key] = (response.json, now)
            return response
        return decorated_function
    return decorator

# --- حماية API Key ---
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

# --- Rate Limiting بسيط ---
rate_limit_counts = {}
RATE_LIMIT = 5  # عدد الطلبات لكل IP
RATE_LIMIT_WINDOW = 60  # ثواني

def rate_limit(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        ip_address = request.remote_addr
        now = datetime.now(timezone.utc)

        if ip_address not in rate_limit_counts:
            rate_limit_counts[ip_address] = []

        # إزالة الطلبات القديمة
        rate_limit_counts[ip_address] = [
            t for t in rate_limit_counts[ip_address]
            if (now - t).total_seconds() < RATE_LIMIT_WINDOW
        ]

        if len(rate_limit_counts[ip_address]) >= RATE_LIMIT:
            return jsonify({"error": f"Rate limit exceeded. Try again in {RATE_LIMIT_WINDOW} seconds."}), 429

        rate_limit_counts[ip_address].append(now)
        return f(*args, **kwargs)
    return decorated_function

# --- نقاط النهاية (API Endpoints) ---

@app.route('/')
def home():
    return "مرحبًا بك في API البيانات القرآنية!"

@app.route('/qawms', methods=['GET'])
@require_api_key
@rate_limit
@cached(timeout=300)
def get_qawms():
    return jsonify({"qawms": qawms_data})

@app.route('/qawms/<int:qawm_id>', methods=['GET'])
@require_api_key
@rate_limit
@cached(timeout=300)
def get_qawm(qawm_id):
    qawm = next((q for q in qawms_data if q["id"] == qawm_id), None)
    if qawm:
        return jsonify(qawm)
    return jsonify({"error": "Qawm not found"}), 404

@app.route('/verses', methods=['GET'])
@require_api_key
@rate_limit
@cached(timeout=300)
def get_all_verses():
    return jsonify({"verses": verses_data})

@app.route('/verses/<int:verse_id>', methods=['GET'])
@require_api_key
@rate_limit
@cached(timeout=300)
def get_verse(verse_id):
    verse = next((v for v in verses_data if v["id"] == verse_id), None)
    if verse:
        return jsonify(verse)
    return jsonify({"error": "Verse not found"}), 404

@app.route('/qawms/<int:qawm_id>/verses', methods=['GET'])
@require_api_key
@rate_limit
@cached(timeout=300)
def get_verses_for_qawm(qawm_id):
    qawm = next((q for q in qawms_data if q["id"] == qawm_id), None)
    if not qawm:
        return jsonify({"error": "Qawm not found"}), 404

    related_verses = [v for v in verses_data if v["qawm_id"] == qawm_id]
    return jsonify({"qawm_name": qawm["name"], "verses": related_verses})

# --- تشغيل التطبيق ---
if __name__ == '__main__':
    app.run(debug=False)
