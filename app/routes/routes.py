import os
import pathlib
from flask import Blueprint, redirect, session, request, abort
from google_auth_oauthlib.flow import Flow
from google.oauth2 import id_token
from google.auth.transport.requests import Request
from dotenv import load_dotenv
from functools import wraps
#---------------------------------------------------------------------------------------------------
from flask import make_response
#--------------------------------------------------------------------------------------------------
from app.routes.postgresql import get_db_connection
#--------------------------------------------------------------------------------------------------
# This Import is for Templates
from flask import render_template
#--------------------------------------------------------------------------------------------------
from flask import session
#--------------------------------------------------------------------------------------------------
# Load environment variables from .env file
load_dotenv()
#--------------------------------------------------------------------------------------------------
# Determine if running in production
IS_PRODUCTION = os.getenv("FLASK_ENV") == "production"
#--------------------------------------------------------------------------------------------------
# Define CLIENT_SECRETS_FILE globally by using a helper function
def get_client_secrets_file():
    host = request.host
    if "localhost" in host or "127.0.0.1" in host or "192.168." in host or "ngrok" in host:
        return os.path.join(
            pathlib.Path(__file__).parent.parent.parent, 'certs', 'client_secret_dev.json'
        )
    return os.path.join(
        pathlib.Path(__file__).parent.parent.parent, 'certs', 'client_secret_prod.json'
    )
#--------------------------------------------------------------------------------------------------
# Blueprint setup for Google OAuth routes
google_bp = Blueprint('google_bp', __name__)
#--------------------------------------------------------------------------------------------------
# Load Google OAuth Client ID from environment
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_OAUTH_CLIENT_ID")
#--------------------------------------------------------------------------------------------------
# Get the redirect URI. Always use the Render callback URL for production.
# Get the redirect URI based on the environment
def get_redirect_uri():
    if IS_PRODUCTION:
        return "https://127.0.0.1:5000/callback"
    return "https://chatmekol.onrender.com/callback"
#--------------------------------------------------------------------------------------------------
# Login required decorator to ensure user is logged in
def login_is_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "google_id" not in session:
            return abort(401)  # Unauthorized if user is not logged in
        return f(*args, **kwargs)
    return decorated_function
#--------------------------------------------------------------------------------------------------
# Google OAuth Login route
from flask import make_response

@google_bp.route("/login/google")
def login_google():
    deployed_url = "chatmekol.onrender.com"

    # Avoid redirect loop on non-allowed hosts
    if deployed_url not in request.host and "127.0.0.1" not in request.host and "192.168." not in request.host:
        print("Blocked: OAuth login only allowed on deployed or localhost.")
        session.clear()

        # Return a response with expired cookie headers
        response = make_response("Google login not allowed from this host. Please use the official deployed link.")
        response.set_cookie('session', '', expires=0)
        return response

    redirect_uri = get_redirect_uri()
    print(f"Redirect URI being used: {redirect_uri}")

    flow = Flow.from_client_secrets_file(
        client_secrets_file=get_client_secrets_file(),
        scopes=[
            "https://www.googleapis.com/auth/userinfo.profile",
            "https://www.googleapis.com/auth/userinfo.email",
            "openid"
        ],
        redirect_uri=redirect_uri
    )

    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true'
    )

    session['state'] = state
    return redirect(authorization_url)
#--------------------------------------------------------------------------------------------------
# Google OAuth callback route
@google_bp.route("/callback")
def callback():
    print("Google OAuth callback triggered.")
    redirect_uri = get_redirect_uri()
    print(f"Using redirect URI: {redirect_uri}")

    # Debug: Full URL received from Google
    print(f"Authorization Response URL: {request.url}")

    # ✅ Insert ALLOWED_HOSTS check here
    ALLOWED_HOSTS = ["127.0.0.1", "192.168.", "chatmekol.onrender.com"]
    if not any(host in request.host for host in ALLOWED_HOSTS):
        print("Unauthorized callback host detected. Clearing session and blocking.")
        session.clear()
        response = make_response("OAuth callback not allowed from this host. Please use the official deployed URL.")
        response.set_cookie('session', '', expires=0)
        return response

    try:
        flow = Flow.from_client_secrets_file(
            client_secrets_file=get_client_secrets_file(),
            scopes=[
                "https://www.googleapis.com/auth/userinfo.profile",
                "https://www.googleapis.com/auth/userinfo.email",
                "openid"
            ],
            redirect_uri=redirect_uri
        )

        flow.fetch_token(authorization_response=request.url)
        credentials = flow.credentials

        print("Verifying ID token...")
        request_obj = Request()
        id_info = id_token.verify_oauth2_token(
            credentials._id_token,
            request_obj,
            GOOGLE_CLIENT_ID
        )
        print("ID token verified!")

        # Store Google user data in session
        session["google_id"] = id_info.get("sub")
        session["name"] = id_info.get("name", "Guest")
        session["email"] = id_info.get("email")
        session["picture"] = id_info.get("picture", "")

        print(f"Logged in as: {session['email']}")

        # Insert user data into PostgreSQL if not already in the database
        from app.routes.postgresql import get_db_connection
        conn = get_db_connection()
        cur = conn.cursor()

        # Check if user already exists by Google ID
        cur.execute("SELECT id FROM users WHERE google_id = %s", (session["google_id"],))
        existing_user = cur.fetchone()

        if not existing_user:
            cur.execute("""
                INSERT INTO users (username, email_address, google_id, picture, is_verified)
                VALUES (%s, %s, %s, %s, %s)
            """, (session["name"], session["email"], session["google_id"], session["picture"], True))
            conn.commit()

        cur.close()
        conn.close()

        # Redirect user to dashboard after successful login
        return redirect("/dashboard")

    except Exception as e:
        print(f"Error during Google login callback: {e}")
        abort(500, f"OAuth callback failed: {e}")
#--------------------------------------------------------------------------------------------------
# Logout route to clear the session
@google_bp.route("/logout")
def logout():
    session.clear()  # Clear the session to log out the user
    return redirect("/")

#--------------------------------------------------------------------------------------------------
# Index route (for demonstration purposes)
@google_bp.route("/")
def index():
    if "google_id" in session:
        return redirect("/dashboard")
    response = make_response(render_template("index.html"))
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    return response
#--------------------------------------------------------------------------------------------------
# Protected area route (for logged-in users)
@google_bp.route("/dashboard")
@login_is_required
def dashboard():
    name = session.get("name")
    email = session.get("email")
    picture = session.get("picture")

    return render_template("dashboard.html", name=name, email=email, picture=picture)
#--------------------------------------------------------------------------------------------------
@google_bp.route('/test-db')
def test_db():
    conn = get_db_connection()
    if conn:
        return "PostgreSQL connected successfully!"
    return "Connection failed."
#--------------------------------------------------------------------------------------------------