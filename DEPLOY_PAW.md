# Deploying Gangs of Palestine on PythonAnywhere

This guide explains how to deploy the game on PythonAnywhere (PAW).

## Prerequisites
- A PythonAnywhere account.
- A GitHub repository with the code.

## Step 1: Clone the Repository
Open a Bash console on PythonAnywhere and run:
```bash
git clone https://github.com/yourusername/gangs-of-ps.git mysite
cd mysite
```

## Step 2: Create Virtual Environment
```bash
mkvirtualenv --python=/usr/bin/python3.10 myenv
pip install -r requirements.txt
```

## Step 3: Configure Database
1. Go to the **Databases** tab in PythonAnywhere.
2. Create a MySQL database (e.g., `yourusername$gangs`).
3. Note the hostname, username, and password.
4. Create a `.env` file in the project root:
   ```bash
   nano .env
   ```
   Add the following content:
   ```env
   SECRET_KEY=your-super-secret-key
   DATABASE_URL=mysql://yourusername:password@yourusername.mysql.pythonanywhere-services.com/yourusername$gangs
   FLASK_APP=run.py
   FLASK_DEBUG=0
   ```

## Step 4: Run Deployment Script
This script initializes the database, runs migrations, and seeds initial data.
```bash
python scripts/deploy_paw.py
```

## Step 5: Web App Configuration
1. Go to the **Web** tab.
2. **Add a new web app**. Choose **Manual configuration** (select Python 3.10).
3. **Virtualenv**: Enter the path to your virtualenv (e.g., `/home/yourusername/.virtualenvs/myenv`).
4. **Source code**: Enter the path to your project (e.g., `/home/yourusername/mysite`).
5. **WSGI configuration file**: Click the link to edit. Delete everything and add:
   ```python
   import sys
   import os
   from dotenv import load_dotenv

   path = '/home/yourusername/mysite'
   if path not in sys.path:
       sys.path.append(path)
   
   load_dotenv(os.path.join(path, '.env'))

   from wsgi import application
   ```
   *Note: Our included `wsgi.py` can also be used directly if you point to it, but PAW usually has its own WSGI file location. The above snippet imports our `wsgi.py`.*

6. **Static Files**:
   - URL: `/static/`
   - Directory: `/home/yourusername/mysite/static`

## Step 6: Reload
Click the green **Reload** button at the top of the Web tab.

## SEO & Sitemap
- **Robots.txt**: Accessible at `/robots.txt`.
- **Sitemap**: Accessible at `/sitemap.xml`.
- **Meta Tags**: Already optimized in `base.html` and `utils/seo.py`.

## Troubleshooting
- Check the **Error Log** in the Web tab if the site doesn't load.
- Ensure `DATABASE_URL` is correct.
- If using MySQL, ensure `mysqlclient` is installed (it is in requirements.txt).
