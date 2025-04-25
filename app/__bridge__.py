# app/__bridge__.py

import os
from flask import Flask
from dotenv import load_dotenv
from datetime import timedelta
from app.routes.routes_new import routes_new
from app.extensions.mail import mail  # Import 'mail' from extensions
from app.routes.routes import google_bp  # ✅ Corrected import
# No need to import create_connection globally

# Load environment variables from .env file
load_dotenv()

def create_app():
    app = Flask(__name__)

    # Initialize the mail extension
    mail.init_app(app)

    # Register blueprints
    app.register_blueprint(routes_new)
    app.register_blueprint(google_bp)

    # Secret key and session configuration
    app.secret_key = os.getenv("SECRET_KEY", "asdasdasdasdasdasd")  # Default value for development
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=30)

    env = os.getenv("FLASK_ENV", "production")

    # Session cookie configuration based on environment
    if env == "development":
        app.config.update(
            SESSION_COOKIE_SECURE=False,  # Allow HTTP for local dev
            SESSION_COOKIE_HTTPONLY=True,
            SESSION_COOKIE_SAMESITE='Lax',  # 'Lax' works better for local testing
            PERMANENT_SESSION_LIFETIME=timedelta(days=31),
        )
    else:
        app.config.update(
            SESSION_COOKIE_SECURE=True,  # HTTPS only
            SESSION_COOKIE_HTTPONLY=True,
            SESSION_COOKIE_SAMESITE='None',  # Required for cross-site in production
            PERMANENT_SESSION_LIFETIME=timedelta(days=31),
        )

    # Database configuration
    app.config['DB_NAME'] = os.getenv('DB_NAME', 'downloadable_app')
    app.config['DB_USER'] = os.getenv('DB_USER', 'root')
    app.config['DB_PASSWORD'] = os.getenv('DB_PASSWORD', 'yourpassword')
    app.config['DB_HOST'] = os.getenv('DB_HOST', 'localhost')
    app.config['DB_PORT'] = os.getenv('DB_PORT', '5432')

    # Import create_connection inside the function
    from app.mysql_connect import create_connection

    # Example usage of the connection
    connection = create_connection()
    if connection:
        print("Database connected successfully!")

    return app
