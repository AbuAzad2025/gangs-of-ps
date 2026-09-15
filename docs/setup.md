# إعداد المشروع محليًا

هذا الملف يوضح طريقة التشغيل السريعة للمشروع في بيئة التطوير المحلية.

## المتطلبات

- Python 3.11 أو أحدث
- pip
- Git
- قاعدة بيانات اختيارية: SQLite افتراضيًا، أو PostgreSQL عند التهيئة

## 1) استنساخ المشروع

```bash
git clone <repo-url>
cd gangs-of-ps
```

## 2) إنشاء بيئة افتراضية

### Windows

```bash
python -m venv .venv
.venv\Scripts\activate
```

### macOS / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
```

## 3) تثبيت الاعتماديات

```bash
pip install -r requirements.txt
```

إذا كنت تحتاج إلى أدوات التطوير:

```bash
pip install -r requirements-dev.txt
```

## 4) إعداد متغيرات البيئة

أنشئ ملف `.env` في root المشروع إن لزم.

### مثال أساسي (SQLite)

```env
SECRET_KEY=change-me
DATABASE_URL=sqlite:///app.db
TEST_DATABASE_URL=sqlite:///:memory:
FLASK_ENV=development
```

### مثال PostgreSQL

```env
SECRET_KEY=change-me
DATABASE_URL=postgresql://user:password@host:5432/gangs_of_palestine
TEST_DATABASE_URL=postgresql://user:password@host:5432/gangs_of_palestine_test
FLASK_ENV=production
```

## 5) تشغيل المشروع

```bash
python run.py
```

أو:

```bash
flask run
```

## 6) التحقق من التشغيل

افتح المتصفح على:

```text
http://localhost:5000
```

وللتأكد من الخدمة:

```bash
curl http://localhost:5000/api/health
```

## ملاحظات مهمة

- إذا كانت `DATABASE_URL` غير صالحة، التطبيق يتراجع آمنًا إلى SQLite في بيئة التطوير.
- لا تضع كلمات المرور أو بيانات الإنتاج في المستودع.
- استخدم لقيم حقيقية فقط عند النشر.

## Next steps

- اقرأ [faq.md](./faq.md) للتعرف على الأسئلة الشائعة.
- اقرأ [deploy.md](./deploy.md) إذا كنت تستعد للنشر.
- اقرأ [troubleshooting.md](./troubleshooting.md) إذا ظهرت مشاكل.
