# دليل نشر النظام (Deployment Guide)

هذا الدليل يشرح خطوات نشر نظام "عصابات فلسطين" على سيرفر إنتاج (Production Server) باستخدام قاعدة بيانات PostgreSQL مع الحفاظ على كافة البيانات.

## المتطلبات المسبقة (Prerequisites)

1.  **سيرفر (VPS/Dedicated):** نظام تشغيل Ubuntu/Debian أو Windows Server.
2.  **PostgreSQL:** مثبت ومشغل (Version 13+).
3.  **Python:** مثبت (Version 3.10+).
4.  **ملف النسخة الاحتياطية:** تأكد من وجود ملف `.sql` الذي تم إنشاؤه مؤخراً.

---

## الخطوات (Steps)

### 1. إعداد قاعدة البيانات على السيرفر

قم بالدخول إلى السيرفر وإنشاء قاعدة بيانات فارغة:

```bash
# الدخول إلى حساب postgres
sudo -u postgres psql

# داخل الـ shell الخاص بـ postgres:
CREATE DATABASE gangsofpalestine;
CREATE USER myuser WITH PASSWORD 'mypassword';
GRANT ALL PRIVILEGES ON DATABASE gangsofpalestine TO myuser;
\q
```

### 2. نقل الملفات

قم بنقل ملفات المشروع وملف النسخة الاحتياطية إلى السيرفر.
ملف النسخة الاحتياطية موجود في: `instance/backups/backup_YYYYMMDD_HHMMSS.sql`

### 3. تثبيت المتطلبات

```bash
pip install -r requirements.txt
```

### 4. استعادة البيانات (Restore Data)

استخدم السكربت المرفق `scripts/restore_db.py` لاستعادة البيانات إلى قاعدة البيانات الجديدة.
هذا السكربت سيقوم بنقل كل الجداول والبيانات (Seeds & User Data) كما هي.

```bash
# الصيغة: python scripts/restore_db.py [مسار_ملف_النسخة] [رابط_قاعدة_البيانات]
python scripts/restore_db.py instance/backups/backup_20260102_164604.sql postgresql://myuser:mypassword@localhost:5432/gangsofpalestine
```

### 5. إعداد متغيرات البيئة

قم بإنشاء ملف `.env` في المجلد الرئيسي للمشروع بالإعدادات التالية:

```ini
FLASK_APP=factory.py
FLASK_ENV=production
SECRET_KEY=your-secure-random-secret-key
DATABASE_URL=postgresql://myuser:mypassword@localhost:5432/gangsofpalestine
```

### 6. تشغيل النظام

يمكنك الآن تشغيل النظام باستخدام `gunicorn` (لأنظمة Linux) أو `waitress`/`flask` (لأنظمة Windows/Test).

```bash
# مثال تشغيل gunicorn
gunicorn -w 4 -b 0.0.0.0:8000 factory:app
```

---

## ملاحظات هامة

*   **التهجير (Migrations):** بما أنك قمت باستعادة قاعدة البيانات بالكامل من النسخة الاحتياطية، **لا تقم** بتشغيل `flask db upgrade` لأول مرة، لأن الجداول موجودة بالفعل.
*   **التحديثات المستقبلية:** لأي تحديثات مستقبلية في هيكلية البيانات، استخدم `flask db migrate` و `flask db upgrade` كالمعتاد.
