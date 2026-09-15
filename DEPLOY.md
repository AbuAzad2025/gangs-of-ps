# Deployment guide

This project can run in two realistic modes:
- local development with SQLite
- production-like deployment with PostgreSQL

The default repository setup is safe and functional for local development. Production deployments should use valid environment variables and a real database.

## Prerequisites

- Python 3.11+
- pip
- Git
- optional: PostgreSQL 13+
- optional: a reverse proxy or WSGI server such as Gunicorn

## Local development

1. Create a virtual environment
   ```bash
   python -m venv .venv
   .venv\Scripts\activate
   ```

2. Install dependencies
   ```bash
   pip install -r requirements.txt
   ```

3. Set environment variables
   ```env
   SECRET_KEY=change-me
   DATABASE_URL=sqlite:///app.db
   FLASK_ENV=development
   ```

4. Start the app
   ```bash
   python run.py
   ```

The default app can run with SQLite while you develop.

## PostgreSQL deployment

Use PostgreSQL when you want a production-oriented database.

### Example environment
```env
SECRET_KEY=very-strong-random-secret
DATABASE_URL=postgresql://user:password@host:5432/gangs_of_palestine
TEST_DATABASE_URL=postgresql://user:password@host:5432/gangs_of_palestine_test
FLASK_ENV=production
```

### Create the database
```sql
CREATE DATABASE gangs_of_palestine;
CREATE DATABASE gangs_of_palestine_test;
```

### Run the app with Gunicorn
```bash
gunicorn --bind 0.0.0.0:8000 wsgi:application
```

If you use a custom app factory, verify the actual entry point in the project before deploying.

## Safety notes

- Keep `.env` files out of version control.
- Use real secrets in production.
- Keep the database connection string valid; malformed DSN values should not be committed to environment files.
- Use TLS / HTTPS in front of the service.

## Basic health check

After startup, verify the homepage or health endpoints respond successfully.

```bash
curl http://localhost:5000/
curl http://localhost:5000/api/health
```

## Release checklist

Before a production release:
- validate environment variables
- confirm database connectivity
- run pytest
- check login and essential routes
- ensure no secret or credential is committed
- verify static files and templates render correctly

## Known operational warning

The project may log a warning about an invalid PostgreSQL DSN if a malformed value is present. This is not a blocker if the app falls back to SQLite in development, but production should avoid malformed DSN values entirely.
