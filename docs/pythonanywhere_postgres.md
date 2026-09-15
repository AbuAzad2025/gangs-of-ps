# PythonAnywhere Postgres notes

This document is a practical reference for PostgreSQL setup on PythonAnywhere. Use it as a reminder, not as a guarantee that the app must run only on Postgres.

## Default behavior

The project runs locally with SQLite by default. PostgreSQL is optional and should be used only when you intentionally configure it.

## Example Postgres URL

```env
DATABASE_URL=postgresql://user:password@host:port/dbname
```

## Example setup steps

1. Create the database in PythonAnywhere PostgreSQL.
2. Add credentials as environment variables.
3. Restart the app.
4. Validate the homepage and health endpoint.

## Quick check

```bash
python -c "from factory import create_app; app = create_app(); print(app.config['SQLALCHEMY_DATABASE_URI'])"
```

## Important

- Do not commit real passwords or DB URLs to Git.
- Do not assume Postgres is required for all environments.
- Keep the database URL valid and test it before production release.
