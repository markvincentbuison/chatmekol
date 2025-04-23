import os
import pathlib
from flask import Blueprint, redirect, session, request, abort
from google_auth_oauthlib.flow import Flow
from google.oauth2 import id_token
from google.auth.transport.requests import Request
from dotenv import load_dotenv
from functools import wraps

#--------------------------------------------------------------------------------------------------
# This Import is for Templates
from flask import render_template
from flask import render_template, redirect, url_for
from app.db_connect import get_db_connection, release_db_connection

#---------------------------------------------------------------------------------------------------

# Load environment variables from .env file
load_dotenv()

# Determine if running in production
IS_PRODUCTION = os.getenv("FLASK_ENV") == "production"
#--------------------------------------------------------------------------------------------------
# Define CLIENT_SECRETS_FILE globally by using a helper function
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

# Google OAuth Login route
@google_bp.route("/login")
def login():
    if session.get("name"):
        # If the user is already logged in, redirect to the dashboard
        return redirect(url_for('google_bp.dashboard'))

    # ✅ Prevent browser from caching this login page
    response = make_response()
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'

    deployed_url = "chatmekol.onrender.com"

    # Avoid redirect loop on non-allowed hosts
    if deployed_url not in request.host and "127.0.0.1" not in request.host and "192.168." not in request.host:
        print("Blocked: OAuth login only allowed on deployed or localhost.")
        session.clear()
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

        # Store user info in the session
        session["google_id"] = id_info.get("sub")
        session["name"] = id_info.get("name", "Guest")
        session["email"] = id_info.get("email")
        session["picture"] = id_info.get("picture", "")

        print(f"Logged in as: {session['email']}")

        # Database Insert Logic (for login)
        google_id = session["google_id"]
        name = session["name"]
        email = session["email"]
        picture = session["picture"]

        # Connect to the database
        conn = get_db_connection()
        cursor = conn.cursor()

        # Check if the user exists in the database using google_id
        cursor.execute("SELECT * FROM users WHERE google_id = %s", (google_id,))
        user = cursor.fetchone()

        if user:
            # User already exists, log them in (you can update their details if needed)
            print("User found in the database. Login successful.")
        else:
            # Insert a new user if not found
            cursor.execute("""
                INSERT INTO users (username, email_address, google_id, is_verified, picture)
                VALUES (%s, %s, %s, %s, %s)
            """, (name, email, google_id, True, picture))
            conn.commit()
            print("New user inserted into the database.")

        # Release the database connection
        release_db_connection(conn)

        # Redirect to dashboard after login or new user creation
        return redirect("/dashboard")

    except Exception as e:
        print(f"Error during Google login callback: {e}")
        abort(500, f"OAuth callback failed: {e}")



#--------------------------------------------------------------------------------------------------
# Logout route to clear the session
@google_bp.route("/logout")
def logout():
    # Clear all session data to log the user out
    session.clear()

    # Redirect to home or login page with no-cache headers to prevent back navigation
    response = make_response(redirect(url_for('google_bp.login')))
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"

    return response

#--------------------------------------------------------------------------------------------------
# Index route (for demonstration purposes)
@google_bp.route("/")
def index():
    
    print("Index route is being accessed")
    return render_template("index.html")

#--------------------------------------------------------------------------------------------------
# Protected area route (for logged-in users)
@google_bp.route("/dashboard")
@login_is_required
def dashboard():
    # Retrieve session data
    name = session.get("name")
    email = session.get("email")
    picture = session.get("picture")

    # Render the template with session data
    response = make_response(render_template("dashboard.html", name=name, email=email, picture=picture))

    # Add no-cache headers to prevent the browser from caching the page
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"

    return response


#--------------------------------------------------------------------------------------------------
@google_bp.route('/login/google/authorized')
def google_authorized():
    if not google.authorized:
        flash('Authorization failed or was cancelled.', 'danger')
        return redirect(url_for('routes.index'))

    resp = google.get('/oauth2/v2/userinfo')
    if not resp.ok:
        flash('Failed to fetch user info from Google.', 'danger')
        return redirect(url_for('routes.index'))

    user_info = resp.json()
    email = user_info.get('email')
    username = user_info.get('name')
    google_id = user_info.get('id')

    if not all([email, username, google_id]):
        flash('Incomplete Google user information.', 'danger')
        return redirect(url_for('routes.index'))

    # Database logic
    conn = create_connection()
    if conn is None:
        flash('Database connection failed.', 'danger')
        return redirect(url_for('routes.index'))

    try:
        cur = conn.cursor()
        # Check if user already exists
        cur.execute("SELECT * FROM users WHERE google_id = %s", (google_id,))
        user = cur.fetchone()

        if user:
            session['user_id'] = user[0]
            session['username'] = user[1]
            session['is_admin'] = user[-2]
        else:
            # Insert new Google user
            cur.execute("""
                INSERT INTO users (username, email_address, google_id)
                VALUES (%s, %s, %s) RETURNING id, is_admin;
            """, (username, email, google_id))
            inserted_user = cur.fetchone()
            conn.commit()

            session['user_id'] = inserted_user[0]
            session['username'] = username
            session['is_admin'] = inserted_user[1]

        flash('Successfully logged in with Google!', 'success')
        return redirect(url_for('routes.dashboard'))

    except Exception as e:
        print("[Google Login DB ERROR]", e)
        flash('An error occurred during Google login.', 'danger')
        return redirect(url_for('routes.index'))

    finally:
        if conn:
            conn.close()
#--------------------------------------------------------------------------------------------------