import os
from dotenv import load_dotenv

load_dotenv()  # Load environment variables from .env file

class Config:
    # ─────────── App Configurations ───────────
    SECRET_KEY = os.getenv('SECRET_KEY', 'asdasdasdasdasdasd')

    MAIL_USERNAME = os.getenv('MAIL_USERNAME', 'your_email@example.com')
    MAIL_PASSWORD = os.getenv('MAIL_PASSWORD', 'your_email_password')
    MAIL_SERVER = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.getenv('MAIL_PORT', 587))
    MAIL_USE_TLS = os.getenv('MAIL_USE_TLS', 'True') == 'True'
    MAIL_USE_SSL = os.getenv('MAIL_USE_SSL', 'False') == 'True'
    MAIL_DEFAULT_SENDER = os.getenv('MAIL_DEFAULT_SENDER', 'your_email@example.com')
    # ─────────── MySQL Configuration for Local Development ───────────
    MYSQL_HOST = os.getenv('MYSQL_HOST', 'localhost')
    MYSQL_PORT = int(os.getenv('MYSQL_PORT', 3306))
    MYSQL_USER = os.getenv('MYSQL_USER', 'root')
    MYSQL_PASSWORD = os.getenv('MYSQL_PASSWORD', 'tunnerskylitQ1@3')
    MYSQL_DB = os.getenv('MYSQL_DB', 'downloadable_apps')
    # ─────────── PostgreSQL Configuration for Production ───────────
    PG_HOST = os.getenv('PG_HOST')
    PG_PORT = int(os.getenv('PG_PORT', 5432))
    PG_USER = os.getenv('PG_USER')
    PG_PASSWORD = os.getenv('PG_PASSWORD')
    PG_DB = os.getenv('PG_DB')
    # ─────────── Environment Switching ───────────
    FLASK_ENV = os.getenv('FLASK_ENV', 'development')     # development or production
    USE_DB = os.getenv('USE_DB', 'mysql')                 # mysql or postgres
    #───────────────────────────────────────────────────────────────────────────────────────────────────────────────────
