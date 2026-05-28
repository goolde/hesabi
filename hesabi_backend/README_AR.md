# حسابي Backend - FastAPI

## تشغيل محلي
```bash
cd hesabi_backend
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Mac/Linux:
source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env   # Windows
# أو: cp .env.example .env
uvicorn app.main:app --reload
```

افتح:
- API: http://127.0.0.1:8000
- Swagger: http://127.0.0.1:8000/docs

## ربط الواجهة HTML
بدل التخزين المحلي LocalStorage بطلبات fetch إلى:
- POST /auth/register
- POST /auth/login
- GET /dashboard
- GET/POST /contacts
- GET/POST/PUT/DELETE /transactions

ضع التوكن بعد تسجيل الدخول:
Authorization: Bearer YOUR_TOKEN

## قاعدة بيانات إنتاج
استخدم PostgreSQL:
DATABASE_URL=postgresql://USER:PASSWORD@HOST:5432/DBNAME

## أمان مهم
- لا ترفع ملف .env إلى GitHub.
- غيّر SECRET_KEY بسلسلة طويلة عشوائية.
- شغّل HTTPS فقط في الإنتاج.
- استخدم PostgreSQL Managed + نسخ احتياطي يومي.
- فعّل rate limiting وراقب محاولات الدخول.
