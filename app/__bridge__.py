import os
from flask import Flask
from dotenv import load_dotenv
from app.routes.routes import routes  # ✅ Corrected import
from datetime import timedelta
from app.extensions.mail import mail
#───────────────────────────────────────────────────────────────────────────────────────────────────────────────────
# Load environment variables from .env
#───────────────────────────────────────────────────────────────────────────────────────────────────────────────────
load_dotenv()
#───────────────────────────────────────────────────────────────────────────────────────────────────────────────────
def create_app():
    app = Flask(__name__)
    app.config['SECURITY_PASSWORD_SALT'] = 'your_unique_salt_value'
    app.secret_key = os.getenv("SECRET_KEY", "asdasdasdasdasdasd")  # Default value for development
    app.register_blueprint(routes)
    # Detect environment (set FLASK_ENV=development in .env if needed)
    env = os.getenv("FLASK_ENV", "production")
    
    # Session cookie configuration
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
            # SESSION_COOKIE_DOMAIN='.yourdomain.com',  # Optional for prod with custom domain
            PERMANENT_SESSION_LIFETIME=timedelta(days=31),
        )
    # Set session expiration time (ensure it's in the create_app function)
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=30)
            # Flask-Mail config using environment variables
    app.config['MAIL_SERVER'] = 'smtp.gmail.com'
    app.config['MAIL_PORT'] = 587
    app.config['MAIL_USE_TLS'] = True
    app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
    app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
    app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_USERNAME')

    app.config['UPLOAD_FOLDER'] = 'static/background/'
    app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif'}
    

        # Initialize Flask-Mail
    mail.init_app(app)
    #───────────────────────────────────────────────────────────────────────────────────────────────────────────────────

    return app

