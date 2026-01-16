import os
from dotenv import load_dotenv

load_dotenv()

basedir = os.path.abspath(os.path.dirname(__file__))


class Config:
    # Secure fallback if not set
    SECRET_KEY = os.environ.get('SECRET_KEY') or os.urandom(24).hex()

    # Database Configuration
    # Default to SQLite for easy local development
    default_db_url = 'sqlite:///' + os.path.join(basedir, 'app.db')
    env_db_url = os.environ.get('DATABASE_URL')

    # if env_db_url and not env_db_url.startswith('postgresql://'):
    #    raise ValueError(
    #        'Only PostgreSQL is supported. '
    #        'DATABASE_URL must start with postgresql://')
    SQLALCHEMY_DATABASE_URI = env_db_url or default_db_url

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    FLASK_ADMIN_SWATCH = 'cerulean'

    # SQLAlchemy Engine Options to avoid connection exhaustion
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': int(os.environ.get('DB_POOL_SIZE', 5)),
        'max_overflow': int(os.environ.get('DB_MAX_OVERFLOW', 10)),
        'pool_recycle': int(os.environ.get('DB_POOL_RECYCLE', 1800)),
        'pool_pre_ping': True,
        'pool_timeout': int(os.environ.get('DB_POOL_TIMEOUT', 30)),
    }

    RATELIMIT_STORAGE_URI = (
        os.environ.get('RATELIMIT_STORAGE_URI') or 'memory://')

    # Security Configuration
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SECURE = (
        os.environ.get('SESSION_COOKIE_SECURE', 'False').lower() == 'true')
    SESSION_COOKIE_SAMESITE = 'Lax'
    PERMANENT_SESSION_LIFETIME = 3600  # 1 hour
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max upload
    PREFERRED_URL_SCHEME = 'https'

    # Mail Configuration
    MAIL_SERVER = os.environ.get('MAIL_SERVER') or 'smtp.gmail.com'
    MAIL_PORT = int(os.environ.get('MAIL_PORT') or 587)
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS') is not None or True
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = (
        os.environ.get('MAIL_DEFAULT_SENDER') or
        'noreply@gangsofpalestine.com')

    # Babel configuration
    LANGUAGES = ['ar', 'en']
    BABEL_DEFAULT_LOCALE = 'ar'
    BABEL_TRANSLATION_DIRECTORIES = 'translations'

    # Social Media Configuration
    DISCORD_INVITE_LINK = os.environ.get(
        'DISCORD_INVITE_LINK') or 'https://discord.gg/actHePygND'
    FACEBOOK_LINK = os.environ.get(
        'FACEBOOK_LINK') or 'https://facebook.com/GangsOfPalestine'
    TWITTER_LINK = os.environ.get(
        'TWITTER_LINK') or 'https://twitter.com/GangsOfPS'
    INSTAGRAM_LINK = os.environ.get(
        'INSTAGRAM_LINK') or 'https://instagram.com/GangsOfPS'

    # AI Configuration
    OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')


class TestConfig(Config):
    TESTING = True
    default_test_db_url = (
        'postgresql://postgres:123@127.0.0.1:5432/gangsofpalestine_test')
    env_test_db_url = os.environ.get('TEST_DATABASE_URL')
    if env_test_db_url and not (
            env_test_db_url.startswith('postgresql://') or
            env_test_db_url.startswith('sqlite://')):
        raise ValueError(
            'TEST_DATABASE_URL must start with postgresql:// or sqlite://')
    SQLALCHEMY_DATABASE_URI = env_test_db_url or default_test_db_url
    WTF_CSRF_ENABLED = False
    RATELIMIT_ENABLED = False
