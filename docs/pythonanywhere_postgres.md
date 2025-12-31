# إعداد Postgres على PythonAnywhere (أوامر محفوظة)

## 1) معلومات الاتصال

استخدم القيم من صفحة Postgres في PythonAnywhere:

- Host: `Azad-4977.postgres.pythonanywhere-services.com`
- Port: `14977`
- Superuser: `super`

صيغة `DATABASE_URL` للتطبيق:

```text
DATABASE_URL=postgresql://super:<PASSWORD>@Azad-4977.postgres.pythonanywhere-services.com:14977/<DBNAME>
```

لا تضع كلمة المرور داخل GitHub أو داخل الكود. ضعها فقط في Environment Variables في PythonAnywhere.

## 2) فحص الاتصال من داخل بايثون

على PythonAnywhere (Bash console) أو محلياً:

```bash
python scripts/db_check.py
```

هذا السكربت يطبع:
- نسخة السيرفر
- اسم الداتابيس الحالية
- اسم المستخدم المتصل
- عدد جداول public
- نسخة alembic (إذا موجودة)

## 3) أوامر psql الأساسية (داخل Postgres Console)

داخل Postgres Console:

```sql
\conninfo
\l
\du
```

إنشاء قاعدة بيانات:

```sql
CREATE DATABASE gangsofpalestine;
```

إنشاء مستخدم للتطبيق (مستحسن بدل super):

```sql
CREATE ROLE gop_app LOGIN PASSWORD '<APP_PASSWORD>';
GRANT ALL PRIVILEGES ON DATABASE gangsofpalestine TO gop_app;
```

بعد ذلك استخدم:

```text
DATABASE_URL=postgresql://gop_app:<APP_PASSWORD>@Azad-4977.postgres.pythonanywhere-services.com:14977/gangsofpalestine
```

## 4) استيراد نسخة كاملة (Dump/Restore)

الطريقة المقترحة:
1) خذ ملف dump من المحلي باستخدام `pg_dump` أو استخدم الملف الموجود عندك داخل `instance/backups/*.dump`.
2) ارفع الملف إلى PythonAnywhere (Files).
3) من Bash console على PythonAnywhere نفّذ:

```bash
pg_restore -h Azad-4977.postgres.pythonanywhere-services.com -p 14977 -U super -d gangsofpalestine --clean --if-exists full_backup_XXXX.dump
```

ملاحظة: `--clean --if-exists` تعني حذف الجداول القديمة وإعادة إنشائها من الـ dump.

