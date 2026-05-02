import os
import secrets


class Config:
    # In Docker/EC2 set SECRET_KEY as an environment variable.
    # Falling back to a random value only makes sense for local dev — every
    # container restart would invalidate all active sessions otherwise.
    SECRET_KEY = os.environ.get('SECRET_KEY') or secrets.token_hex(32)

    SESSION_COOKIE_SECURE   = True   # only send cookie over HTTPS
    SESSION_COOKIE_HTTPONLY = True   # block JavaScript from reading the cookie
    SESSION_COOKIE_SAMESITE = 'Lax'  # block cross-site POST cookie riding
    REMEMBER_COOKIE_SECURE   = True
    REMEMBER_COOKIE_HTTPONLY = True

    SQLALCHEMY_DATABASE_URI = (
        os.environ.get('DATABASE_URL')
        or 'sqlite:///lightstorm_it.db'
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Flask-Mail — set these via environment variables in production
    MAIL_SERVER   = os.environ.get('MAIL_SERVER',   'smtp.gmail.com')
    MAIL_PORT     = int(os.environ.get('MAIL_PORT',  587))
    MAIL_USE_TLS  = os.environ.get('MAIL_USE_TLS',  'true').lower() == 'true'
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER', 'noreply@lightstorm.net')
    # Base URL used in verification links (override in production)
    APP_BASE_URL  = os.environ.get('APP_BASE_URL',  'http://127.0.0.1:5000')

    UPLOAD_FOLDER = os.path.join('static', 'uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB
    ALLOWED_EXTENSIONS = {
        'pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx',
        'png', 'jpg', 'jpeg', 'gif', 'txt', 'csv'
    }
