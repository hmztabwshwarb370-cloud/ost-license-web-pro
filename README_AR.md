# OST TECH License Manager - Web Pro

منصة تراخيص موحدة تعمل على الإنترنت لإدارة طلبات تفعيل جميع مشاريعك.

## التشغيل المحلي

```bat
python -m pip install -r requirements.txt
python app.py
```

افتح:

```text
http://127.0.0.1:7070
```

الدخول الافتراضي:

```text
admin
admin
```

## متغيرات البيئة المهمة

غيّرها عند النشر:

```text
SECRET_KEY=ضع_مفتاح_سري_قوي
ADMIN_USER=admin
ADMIN_PASS=كلمة_مرور_قوية
DATABASE_PATH=/app/instance/licenses.db
```

## رابط استقبال طلبات التفعيل

بعد النشر على الإنترنت، سيكون مثل:

```text
https://your-domain.com/api/activation_request
```

ضع هذا الرابط داخل نسخة أي مشروع تريد ربطه بالتراخيص.

## API

### طلب تفعيل

POST `/api/activation_request`

```json
{
  "product_code":"MOSQUE_MANAGER",
  "client_name":"اسم العميل",
  "phone":"رقم الهاتف",
  "device_id":"بصمة الجهاز",
  "device_label":"اسم الجهاز",
  "app_version":"1.0"
}
```

### تفعيل الكود

POST `/api/activate`

```json
{
  "product_code":"MOSQUE_MANAGER",
  "device_id":"بصمة الجهاز",
  "license_code":"OST-XXXX-XXXX-XXXX-XXXX"
}
```

### التحقق من الترخيص

POST `/api/verify`

```json
{
  "product_code":"MOSQUE_MANAGER",
  "device_id":"بصمة الجهاز",
  "license_code":"OST-XXXX-XXXX-XXXX-XXXX"
}
```

## النشر المقترح

يمكن نشرها على:

- Render
- Railway
- VPS
- Docker

الأفضل لاحقاً ربطها بدومين مثل:

```text
https://license.ost-tech.com
```
