import os
import sys
import subprocess
from urllib.parse import urlparse
import argparse

def restore_database(backup_file, db_url):
    """Restores a PostgreSQL database from a SQL backup file."""
    
    print(f"Starting restore process...")
    print(f"Backup file: {backup_file}")
    
    if not os.path.exists(backup_file):
        print(f"Error: Backup file '{backup_file}' not found.")
        return False

    # Parse Database URL
    try:
        result = urlparse(db_url)
        user = result.username
        password = result.password
        host = result.hostname
        port = result.port or 5432
        dbname = result.path.lstrip('/')
    except Exception as e:
        print(f"Error parsing DATABASE_URL: {e}")
        return False

    # Prepare Environment
    env = os.environ.copy()
    if password:
        env['PGPASSWORD'] = password

    # Check for psql
    psql = "psql"
    # Try to find psql in common paths if on Windows
    if sys.platform == 'win32':
        possible_paths = [
            r"C:\Program Files\PostgreSQL\18\bin\psql.exe",
            r"C:\Program Files\PostgreSQL\17\bin\psql.exe",
            r"C:\Program Files\PostgreSQL\16\bin\psql.exe",
            r"C:\Program Files\PostgreSQL\15\bin\psql.exe",
            r"C:\Program Files\PostgreSQL\14\bin\psql.exe",
            r"C:\Program Files\PostgreSQL\13\bin\psql.exe",
        ]
        for path in possible_paths:
            if os.path.exists(path):
                psql = path
                break

    # Construct Command
    cmd = [
        psql,
        '-U', user,
        '-h', host,
        '-p', str(port),
        '-d', dbname,
        '-f', backup_file
    ]

    logging.info(f"Connecting to {host}:{port}/{dbname} as {user}...")
    
    try:
        # Run psql
        subprocess.run(cmd, env=env, check=True)
        print("\nRestore completed successfully!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"\nRestore failed with error code {e.returncode}.")
        return False
    except FileNotFoundError:
        print("\nError: 'psql' command not found. Please ensure PostgreSQL client tools are installed and in your PATH.")
        return False
    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}")
        return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Restore PostgreSQL database from backup.')
    parser.add_argument('backup_file', help='Path to the .sql backup file')
    parser.add_argument('db_url', help='Target Connection String (postgresql://user:pass@host:port/dbname)')
    
    args = parser.parse_args()
    
    restore_database(args.backup_file, args.db_url)
