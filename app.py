import os, sqlite3, hashlib, hmac, secrets, json
from datetime import datetime, timedelta
from functools import wraps
from flask import Flask, request, jsonify, render_template, redirect, url_for, session, flash
from flask_cors import CORS

APP_NAME = 'OST TECH License Manager'
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get('DATABASE_PATH', os.path.join(BASE_DIR, 'instance', 'licenses.db'))
SECRET_KEY = os.environ.get('SECRET_KEY', 'CHANGE_ME_OST_LICENSE_SECRET')
ADMIN_USER = os.environ.get('ADMIN_USER', 'admin')
ADMIN_PASS = os.environ.get('ADMIN_PASS', 'admin')

app = Flask(__name__)
app.secret_key = SECRET_KEY
CORS(app)

os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

def now():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')

def conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c

def init_db():
    with conn() as c:
        c.executescript('''
        CREATE TABLE IF NOT EXISTS products(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS requests(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_code TEXT NOT NULL,
            client_name TEXT NOT NULL,
            phone TEXT NOT NULL,
            email TEXT,
            device_id TEXT NOT NULL,
            device_label TEXT,
            app_version TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            license_code TEXT,
            notes TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS licenses(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id INTEGER,
            product_code TEXT NOT NULL,
            client_name TEXT NOT NULL,
            phone TEXT NOT NULL,
            device_id TEXT NOT NULL,
            license_code TEXT UNIQUE NOT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            max_activations INTEGER DEFAULT 1,
            expires_at TEXT,
            created_at TEXT NOT NULL
        );
        ''')
        c.execute(
            "INSERT OR IGNORE INTO products(code,name,created_at) VALUES(?,?,?)",
            ('MOSQUE_MANAGER', 'نظام إدارة المساجد والمعاهد', now())
        )
        c.commit()

init_db()

def rows(query, args=()):
    with conn() as c:
        return [dict(r) for r in c.execute(query, args).fetchall()]

def one(query, args=()):
    with conn() as c:
        r = c.execute(query, args).fetchone()
        return dict(r) if r else None

def make_license(product_code, device_id, days=None):
    raw = f'{product_code}|{device_id}|{secrets.token_hex(8)}|{now()}'
    digest = hmac.new(SECRET_KEY.encode(), raw.encode(), hashlib.sha256).hexdigest().upper()
    return 'OST-' + '-'.join([digest[i:i+4] for i in range(0, 16, 4)])

def login_required(fn):
    @wraps(fn)
    def wrapper(*a, **kw):
        if not session.get('admin'):
            return redirect(url_for('login'))
        return fn(*a, **kw)
    return wrapper

@app.route('/')
def home():
    return redirect(url_for('dashboard') if session.get('admin') else url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form.get('username') == ADMIN_USER and request.form.get('password') == ADMIN_PASS:
            session['admin'] = True
            return redirect(url_for('dashboard'))
        flash('بيانات الدخول غير صحيحة')
    return render_template('login.html', app_name=APP_NAME)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    stats = {
        'pending': one("SELECT COUNT(*) c FROM requests WHERE status='pending'")['c'],
        'approved': one("SELECT COUNT(*) c FROM requests WHERE status='approved'")['c'],
        'licenses': one("SELECT COUNT(*) c FROM licenses")['c'],
        'products': one("SELECT COUNT(*) c FROM products")['c'],
    }
    reqs = rows('SELECT * FROM requests ORDER BY id DESC LIMIT 200')
    products = rows('SELECT * FROM products ORDER BY id DESC')
    return render_template('dashboard.html', stats=stats, reqs=reqs, products=products, app_name=APP_NAME)

@app.route('/products', methods=['POST'])
@login_required
def add_product():
    code = request.form.get('code', '').strip().upper().replace(' ', '_')
    name = request.form.get('name', '').strip()
    if code and name:
        try:
            with conn() as c:
                c.execute('INSERT INTO products(code,name,created_at) VALUES(?,?,?)', (code, name, now()))
                c.commit()
            flash('تمت إضافة المنتج')
        except Exception as e:
            flash('تعذر إضافة المنتج: ' + str(e))
    return redirect(url_for('dashboard'))

@app.route('/approve/<int:req_id>', methods=['POST'])
@login_required
def approve(req_id):
    r = one('SELECT * FROM requests WHERE id=?', (req_id,))
    if not r:
        flash('الطلب غير موجود')
        return redirect(url_for('dashboard'))

    code = make_license(r['product_code'], r['device_id'])

    with conn() as c:
        c.execute('''INSERT INTO licenses(request_id,product_code,client_name,phone,device_id,license_code,status,created_at)
                     VALUES(?,?,?,?,?,?,?,?)''',
                  (req_id, r['product_code'], r['client_name'], r['phone'], r['device_id'], code, 'active', now()))
        c.execute("UPDATE requests SET status='approved', license_code=?, updated_at=? WHERE id=?",
                  (code, now(), req_id))
        c.commit()

    flash('تم إصدار كود التفعيل')
    return redirect(url_for('dashboard'))

@app.route('/reject/<int:req_id>', methods=['POST'])
@login_required
def reject(req_id):
    with conn() as c:
        c.execute("UPDATE requests SET status='rejected', updated_at=? WHERE id=?", (now(), req_id))
        c.commit()
    return redirect(url_for('dashboard'))

@app.route('/revoke/<int:lic_id>', methods=['POST'])
@login_required
def revoke(lic_id):
    with conn() as c:
        c.execute("UPDATE licenses SET status='revoked' WHERE id=?", (lic_id,))
        c.commit()
    flash('تم إلغاء الترخيص')
    return redirect(url_for('licenses'))

@app.route('/licenses')
@login_required
def licenses():
    lics = rows('SELECT * FROM licenses ORDER BY id DESC')
    return render_template('licenses.html', lics=lics, app_name=APP_NAME)

@app.route('/api/activation_request', methods=['GET', 'POST'])
def api_activation_request():
    # يدعم الطلب من النظام سواء أرسل GET أو POST أو JSON
    data = request.get_json(silent=True) or request.form.to_dict() or request.args.to_dict() or {}

    required = ['product_code', 'client_name', 'phone', 'device_id']
    missing = [k for k in required if not str(data.get(k, '')).strip()]

    if missing:
        return jsonify(ok=False, error='missing_fields', fields=missing), 400

    with conn() as c:
        c.execute('''INSERT INTO requests(product_code,client_name,phone,email,device_id,device_label,app_version,status,created_at,updated_at)
                     VALUES(?,?,?,?,?,?,?,?,?,?)''', (
            data.get('product_code', '').strip().upper(),
            data.get('client_name', '').strip(),
            data.get('phone', '').strip(),
            data.get('email', '').strip(),
            data.get('device_id', '').strip(),
            data.get('device_label', '').strip(),
            data.get('app_version', '').strip(),
            'pending',
            now(),
            now()
        ))
        req_id = c.lastrowid
        c.commit()

    return jsonify(ok=True, request_id=req_id, message='activation_request_received')

@app.route('/api/activate', methods=['GET', 'POST'])
def api_activate():
    data = request.get_json(silent=True) or request.form.to_dict() or request.args.to_dict() or {}

    product_code = data.get('product_code', '').strip().upper()
    device_id = data.get('device_id', '').strip()
    license_code = data.get('license_code', '').strip().upper()

    lic = one(
        'SELECT * FROM licenses WHERE product_code=? AND device_id=? AND license_code=?',
        (product_code, device_id, license_code)
    )

    if not lic:
        return jsonify(ok=False, error='invalid_license'), 403

    if lic['status'] != 'active':
        return jsonify(ok=False, error='license_not_active'), 403

    if lic.get('expires_at'):
        try:
            if datetime.strptime(lic['expires_at'], '%Y-%m-%d') < datetime.now():
                return jsonify(ok=False, error='license_expired'), 403
        except Exception:
            pass

    signed = hmac.new(
        SECRET_KEY.encode(),
        f"{product_code}|{device_id}|{license_code}".encode(),
        hashlib.sha256
    ).hexdigest()

    return jsonify(
        ok=True,
        product_code=product_code,
        device_id=device_id,
        license_code=license_code,
        signature=signed
    )

@app.route('/api/verify', methods=['GET', 'POST'])
def api_verify():
    data = request.get_json(silent=True) or request.form.to_dict() or request.args.to_dict() or {}

    lic = one(
        'SELECT * FROM licenses WHERE product_code=? AND device_id=? AND license_code=? AND status="active"',
        (
            data.get('product_code', '').strip().upper(),
            data.get('device_id', '').strip(),
            data.get('license_code', '').strip().upper()
        )
    )

    return jsonify(ok=bool(lic))

@app.route('/health')
def health():
    return jsonify(ok=True, app=APP_NAME, time=now())

if __name__ == '__main__':
    port = int(os.environ.get('PORT', '7070'))
    app.run(host='0.0.0.0', port=port, debug=False)
