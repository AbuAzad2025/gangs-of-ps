# Deploying on PythonAnywhere

This guide covers a simple deployment flow for PythonAnywhere. It is intentionally practical and does not assume a specific production setup beyond a standard Flask app.

## Prerequisites

- PythonAnywhere account
- project repository cloned to the server
- access to the web app dashboard

## 1. Clone and install

```bash
git clone <repo-url> mysite
cd mysite
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## 2. Configure environment variables

Create a `.env` file in the project root:

```env
SECRET_KEY=replace-with-a-real-secret
DATABASE_URL=sqlite:///app.db
FLASK_ENV=production
```

If you use PostgreSQL, replace the value with a valid PostgreSQL URL.

## 3. Start the app

For PythonAnywhere, commonly the WSGI file points to the app object. Verify whether the project expects `wsgi:application` or a custom entry point.

```python
import os
from dotenv import load_dotenv

load_dotenv()

from wsgi import application
```

## 4. Static files

Configure the web app to serve the project static directory:
```text
/static/ -> /home/<user>/mysite/static
```

## 5. Health check

After deployment, confirm:
```bash
curl https://<your-domain>/
curl https://<your-domain>/api/health
```

## Notes

- PythonAnywhere is suitable for lightweight hosting.
- For higher traffic or larger production usage, a VPS or managed hosting platform is usually more predictable.
- Keep secrets outside source control.
