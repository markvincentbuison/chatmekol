import os
from flask import Flask
from dotenv import load_dotenv
# Import the blueprint for Google OAuth from routes.py
from app.routes.routes import google_bp

# Load environment variables from .env file
load_dotenv()
#---------------------------------------------------------------------------------------------------
def create_app():
    app = Flask(__name__)
#---------------------------------------------------------------------------------------------------        
# Register the Google Auth blueprint    
#---------------------------------------------------------------------------------------------------
    app.register_blueprint(google_bp, url_prefix='/google')
#---------------------------------------------------------------------------------------------------

    
    
    
    return app
