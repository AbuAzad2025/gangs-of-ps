# النشر

يتم دعم المشروع على أكثر من سيناريو تنفيذ، لكن القاعدة الأساسية هي: استخدم بيئة متغيرة منفصلة، قاعدة بيانات صالحة، وخادم WSGI مناسب.

## سيناريوهات النشر

### 1) التطوير المحلي

الافتراضي في المشروع هو SQLite، وهو مناسب للتطوير السريع والاختبار المحلي.

### 2) النشر على خادم VPS أو مستضيف يدعم Python

التكوين المطلوب:
- Python 3.11+
- بيئة افتراضية
- قاعدة بيانات PostgreSQL فعليّة في الإنتاج
- إعدادات env صحيحة
- خادم مثل Gunicorn أو Waitress

## مثال إعداد بيئة الإنتاج

```env
SECRET_KEY=very-strong-random-secret
DATABASE_URL=postgresql://user:password@host:5432/gangs_of_palestine
TEST_DATABASE_URL=postgresql://user:password@host:5432/gangs_of_palestine_test
FLASK_ENV=production
```

## مثال تشغيل Gunicorn

```bash
gunicorn --bind 0.0.0.0:8000 wsgi:application
```

تأكد من أن نقطة الدخول الحالية في المشروع هي `wsgi:application` أو أن الملف المقصود صحيح. إذا كان مشروعك يستخدم factory، فراجع تكوين نقطة الدخول قبل التشغيل.

## التحقق بعد النشر

بعد البدء، تحقق من الروابط الأساسية:

```bash
curl https://your-domain/
curl https://your-domain/api/health
```

## Checklist قبل النشر

- التحقق من `SECRET_KEY`
- التحقق من `DATABASE_URL`
- التحقق من وجود قاعدة البيانات المقصودة
- تشغيل pytest بنجاح
- التحقق من أن الصفحة الرئيسية/التسجيل/الصفحات الأساسية تعمل
- التأكد أن `.env` غير مضمن في Git
- التحقق من وجود HTTPS في الإنتاج

## ملاحظات أمان

- لا تضع كلمات المرور داخل الكود أو الملفات المرفقة في المستودع
- استخدم متغيرات البيئة أو مدير إعدادات آمن
- لا تعتمد على DSN غير صالح في الإنتاج

## خيارات استضافة شائعة

- VPS / Ubuntu server
- Render
- Railway
- PythonAnywhere
- Docker-based hosting

## النشر على PythonAnywhere

راجع ملف [pythonanywhere_postgres.md](./pythonanywhere_postgres.md) للاطلاع على ملاحظات عملية مرتبطة بالاستضافة.
