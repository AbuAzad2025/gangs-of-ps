import os
import shutil
import subprocess
from datetime import datetime
from flask import current_app
from flask_babel import _
from urllib.parse import urlparse


class BackupManager:
    @staticmethod
    def get_db_path():
        """Returns the absolute path to the database file."""
        # Not applicable for PostgreSQL
        return None

    @staticmethod
    def get_backup_dir():
        """Returns the absolute path to the backup directory."""
        backup_dir = os.path.join(current_app.instance_path, 'backups')
        if not os.path.exists(backup_dir):
            os.makedirs(backup_dir)
        return backup_dir

    @classmethod
    def get_backups(cls):
        """Returns a list of backup files sorted by date (newest first)."""
        backup_dir = cls.get_backup_dir()
        backups = []

        if not os.path.exists(backup_dir):
            return []

        for f in os.listdir(backup_dir):
            if f.endswith(('.sql', '.dump')):
                path = os.path.join(backup_dir, f)
                try:
                    stat = os.stat(path)
                    backups.append({
                        'name': f,
                        'path': path,
                        'size': stat.st_size,
                        'size_mb': stat.st_size / (1024 * 1024),
                        'timestamp': stat.st_mtime,
                        'date': datetime.fromtimestamp(stat.st_mtime)
                    })
                except OSError:
                    continue

        # Sort by timestamp descending
        backups.sort(key=lambda x: x['timestamp'], reverse=True)
        return backups

    @staticmethod
    def _get_pg_credentials():
        # Parse DATABASE_URL
        db_url = os.environ.get('DATABASE_URL')
        if not db_url:
            return None
        # format: postgresql://user:password@host:port/dbname
        try:
            result = urlparse(db_url)
            return {
                'user': result.username,
                'password': result.password,
                'host': result.hostname,
                'port': result.port,
                'dbname': result.path.lstrip('/')
            }
        except Exception:
            return None

    @staticmethod
    def _get_pg_tool_path(tool_name):
        """Finds the path to a PostgreSQL tool (pg_dump or psql)."""
        # Check system PATH first
        if shutil.which(tool_name):
            return tool_name

        # Check common Windows paths
        possible_paths = [
            r"C:\Program Files\PostgreSQL\18\bin",
            r"C:\Program Files\PostgreSQL\17\bin",
            r"C:\Program Files\PostgreSQL\16\bin",
            r"C:\Program Files\PostgreSQL\15\bin",
            r"C:\Program Files\PostgreSQL\14\bin",
            r"C:\Program Files\PostgreSQL\13\bin",
        ]

        for p in possible_paths:
            full_path = os.path.join(p, tool_name + ".exe")
            if os.path.exists(full_path):
                return full_path

        return tool_name  # Fallback to trying the command directly

    @classmethod
    def create_backup(cls):
        """
        Creates a new backup using pg_dump.
        """
        creds = cls._get_pg_credentials()
        if not creds:
            return False, _("لم يتم العثور على إعدادات قاعدة البيانات.")

        backup_dir = cls.get_backup_dir()
        filename = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.sql"
        filepath = os.path.join(backup_dir, filename)

        # Set PGPASSWORD env var for the subprocess
        env = os.environ.copy()
        if creds['password']:
            env['PGPASSWORD'] = creds['password']

        pg_dump = cls._get_pg_tool_path('pg_dump')

        # Command: pg_dump -U user -h host -p port -d dbname -f filepath
        cmd = [
            pg_dump,
            '-U', creds['user'],
            '-h', str(creds['host']),
            '-p', str(creds['port']),
            '-F', 'p',  # plain text sql
            '-f', filepath,
            creds['dbname']
        ]

        try:
            subprocess.run(
                cmd,
                env=env,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE)
            return True, _("تم إنشاء النسخة الاحتياطية بنجاح.")
        except subprocess.CalledProcessError as e:
            return False, _("فشل إنشاء النسخة الاحتياطية: %(error)s",
                            error=e.stderr.decode('utf-8') if e.stderr else str(e))
        except FileNotFoundError:
            return False, _(
                "لم يتم العثور على أداة pg_dump. تأكد من تثبيت PostgreSQL.")
        except Exception as e:
            return False, _("حدث خطأ غير متوقع: %(error)s", error=str(e))

    @classmethod
    def restore_backup(cls, filename):
        creds = cls._get_pg_credentials()
        if not creds:
            return False, _("لم يتم العثور على إعدادات قاعدة البيانات.")

        backup_dir = cls.get_backup_dir()
        filepath = os.path.join(backup_dir, filename)

        if not os.path.exists(filepath):
            return False, _("ملف النسخة الاحتياطية غير موجود.")

        # Set PGPASSWORD env var
        env = os.environ.copy()
        if creds['password']:
            env['PGPASSWORD'] = creds['password']

        psql = cls._get_pg_tool_path('psql')

        # Command: psql -U user -h host -p port -d dbname -f filepath
        cmd = [
            psql,
            '-U', creds['user'],
            '-h', str(creds['host']),
            '-p', str(creds['port']),
            '-d', creds['dbname'],
            '-f', filepath
        ]

        try:
            subprocess.run(
                cmd,
                env=env,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE)
            return True, _("تم استعادة النسخة الاحتياطية بنجاح.")
        except subprocess.CalledProcessError as e:
            return False, _("فشل استعادة النسخة الاحتياطية: %(error)s",
                            error=e.stderr.decode('utf-8') if e.stderr else str(e))
        except FileNotFoundError:
            return False, _(
                "لم يتم العثور على أداة psql. تأكد من تثبيت PostgreSQL.")
        except Exception as e:
            return False, _("حدث خطأ غير متوقع: %(error)s", error=str(e))

    @classmethod
    def delete_backup(cls, filename):
        backup_dir = cls.get_backup_dir()
        path = os.path.join(backup_dir, filename)

        if os.path.exists(path):
            try:
                os.remove(path)
                return True, _("تم حذف النسخة الاحتياطية بنجاح.")
            except Exception as e:
                return False, _("حدث خطأ أثناء الحذف: %(error)s", error=str(e))
        else:
            return False, _("الملف غير موجود.")
