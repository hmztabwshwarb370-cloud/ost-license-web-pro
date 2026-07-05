import os
import sqlite3
from datetime import datetime
from flask import Flask, request, jsonify, render_template, redirect, url_for
from flask_cors import CORS

app = Flask(__name__)
# تفعيل الـ CORS لدعم الطلبات المتقاطعة من البرنامج المحلي
CORS(app, resources={r"/api/*": {"origins": "*"}})

DB_PATH = os.path.join(os.path.dirname(__file__), 'data', 'settings.xlsx') 
# ملاحظة: إذا كان نظامك يعتمد على قاعدة بيانات SQLite حقيقية، تأكد من مسار ملف الـ .db الصحيح هنا
DB_FILE = os.path.join(os.path.dirname(__file__), 'license.db')

def init_db():
    """تهيئة قاعدة البيانات وإنشاء جدول الطلبات إذا لم يكن موجوداً"""
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_code TEXT,
                client_name TEXT,
                phone TEXT,
                email TEXT,
                device_id TEXT,
                device_label TEXT,
                app_version TEXT,
                status TEXT,
                created_at TEXT,
                updated_at TEXT
            )
        """)
        conn.commit()

# استدعاء دالة التهيئة عند تشغيل التطبيق
init_db()

def get_db_connection():
    """إنشاء اتصال آمن مع قاعدة بيانات SQLite"""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def now_str():
    """الحصول على التوقيت الحالي بصيغة نصية مجدولة"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

@app.route("/")
def index():
    """الصفحة الرئيسية لوحة تحكم التراخيص"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM requests ORDER BY id DESC")
            reqs = cursor.fetchall()
        return render_template("index.html", requests=reqs)
    except Exception as e:
        return f"Error loading dashboard: {str(e)}", 500

@app.route("/health", methods=["GET"])
def health_check():
    """نقطة فحص سلامة وتحديث المنصة"""
    return jsonify({"status": "healthy", "version": "1.0.1-fixed-sqlite"}), 200

# دعم الـ GET و POST و OPTIONS بمرونة تامة للروابط مع أو بدون الـ Slash الأخيرة
@app.route("/api/activation_request", methods=["GET", "POST", "OPTIONS"])
@app.route("/api/activation_request/", methods=["GET", "POST", "OPTIONS"])
def api_activation_request():
    # التعامل مع طلبات الـ OPTIONS المبدئية للـ CORS المتصفحات
    if request.method == "OPTIONS":
        return "", 200

    # تجميع البيانات سواء كانت قادمة كـ JSON أو كـ Query Parameters (GET/POST)
    if request.method == "POST":
        if request.is_json:
            data = request.get_json() or {}
        else:
            data = request.form.to_dict() or {}
    else:
        data = request.args.to_dict() or {}

    # التحقق من وجود المعطيات الأساسية
    product_code = data.get("product_code", "").strip().upper()
    client_name = data.get("client_name", "").strip()
    device_id = data.get("device_id", "").strip()

    if not product_code or not client_name or not device_id:
        return jsonify({
            "ok": false, 
            "error": "Missing required fields: product_code, client_name, and device_id are mandatory."
        }), 400

    try:
        current_time = now_str()
        with get_db_connection() as conn:
            # الإصلاح الجذري: استقبال كائن الـ cursor الناتج عن الـ execute للاستعلام عن lastrowid
            cur = conn.execute("""
                INSERT INTO requests (
                    product_code, client_name, phone, email,
                    device_id, device_label, app_version,
                    status, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                product_code,
                client_name,
                data.get("phone", "").strip(),
                data.get("email", "").strip(),
                device_id,
                data.get("device_label", "").strip(),
                data.get("app_version", "").strip(),
                "pending",
                current_time,
                current_time
            ))
            
            # جلب معرف الصف المضاف حديثاً من الـ cursor وليس من الـ connection
            req_id = cur.lastrowid
            conn.commit()

        return jsonify({
            "ok": True,
            "request_id": req_id,
            "message": "Activation request registered successfully."
        }), 200

    except Exception as e:
        # إرجاع تفاصيل الخطأ بصيغة JSON واضحة بدلاً من كراش الـ HTTP 500 العام
        return jsonify({
            "ok": False,
            "error": f"Database operation failed: {str(e)}"
        }), 500

@app.route("/action/<int:req_id>/<string:status>", methods=["POST"])
def update_request_status(req_id, status):
    """تحديث حالة الطلب (قبول/رفض) من لوحة التحكم"""
    if status not in ["approved", "rejected", "pending"]:
        return "Invalid status", 400
        
    try:
        with get_db_connection() as conn:
            conn.execute(
                "UPDATE requests SET status = ?, updated_at = ? WHERE id = ?",
                (status, now_str(), req_id)
            )
            conn.commit()
        return redirect(url_for("index"))
    except Exception as e:
        return f"Error updating status: {str(e)}", 500

if __name__ == "__main__":
    # تشغيل التطبيق محلياً أو عبر خادم الـ Production
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
