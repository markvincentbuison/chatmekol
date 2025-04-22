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

#---------------------------------------------------------------------------------------------------
# Load environment variables from .env file
load_dotenv()

# Define CLIENT_SECRETS_FILE globally by using a helper function
def get_client_secrets_file():
    host = request.host
    if "127.0.0.1" in host or "localhost" in host or "192.168." in host or "ngrok" in host:
        return os.path.join(
            pathlib.Path(__file__).parent.parent.parent, 'certs', 'client_secret_dev.json'
        )
    else:
        return os.path.join(
            pathlib.Path(__file__).parent.parent.parent, 'certs', 'client_secret_prod.json'
        )

# Blueprint setup for Google OAuth routes
google_bp = Blueprint('google_bp', __name__)

# Load Google OAuth Client ID from environment
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_OAUTH_CLIENT_ID")

#--------------------------------------------------------------------------------------------------
# Get the redirect URI. Always use the Render callback URL for production.
def get_redirect_uri():
    host = request.host
    if "127.0.0.1" in host or "localhost" in host:
        # When testing locally, return the localhost URL
        return "https://127.0.0.1:5000/callback"  # Change to ngrok URL if using ngrok
    return "https://google-test-signin.onrender.com/callback"  # Your production callback URL

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
@google_bp.route("/login")
def login():
    # Replace with your actual deployed URL
    deployed_url = "https://google-test-signin.onrender.com"

    # Check if the request is coming from the deployed URL or allow localhost
    if deployed_url not in request.host and "127.0.0.1" not in request.host and "192.168." not in request.host:
        print("Google OAuth login is disabled. Please use the deployed URL.")
        return "Google Login is only allowed from the deployed URL.", 403

    redirect_uri = get_redirect_uri()  # Get the correct redirect URI for the environment
    print(f"Redirect URI being used: {redirect_uri}")
    
    flow = Flow.from_client_secrets_file(
        client_secrets_file=get_client_secrets_file(),  # Use the helper function here
        scopes=[
            "https://www.googleapis.com/auth/userinfo.profile",
            "https://www.googleapis.com/auth/userinfo.email",
            "openid"
        ],
        redirect_uri=redirect_uri
    )

    # Generate authorization URL and state for the OAuth flow
    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true'
    )
    
    session['state'] = state  # Store the state to verify later in callback
    return redirect(authorization_url)

#--------------------------------------------------------------------------------------------------
# Google OAuth callback route
@google_bp.route("/callback")
def callback():
    print("Google OAuth callback triggered.")
    redirect_uri = get_redirect_uri()  # Ensure correct redirect URI
    print(f"Using redirect URI: {redirect_uri}")
    
    # Debug print: output the full authorization response URL
    print(f"Authorization Response URL: {request.url}")

    try:
        # Initialize the OAuth flow using the provided client secrets and redirect URI
        flow = Flow.from_client_secrets_file(
            client_secrets_file=get_client_secrets_file(),  # Use the helper function here
            scopes=[
                "https://www.googleapis.com/auth/userinfo.profile",
                "https://www.googleapis.com/auth/userinfo.email",
                "openid"
            ],
            redirect_uri=redirect_uri
        )

        # Fetch the token from the authorization response URL
        flow.fetch_token(authorization_response=request.url)

        # After fetching the token, get the credentials
        credentials = flow.credentials

        # Verifying and decoding the ID token from Google's response
        print("Verifying ID token...")
        request_obj = Request()  # Instantiate the Request object
        id_info = id_token.verify_oauth2_token(
            credentials._id_token,
            request_obj,  # Pass the request object to verify
            GOOGLE_CLIENT_ID  # Pass the correct client ID
        )
        print("ID token verified!")

        # Save user info to the session
        session["google_id"] = id_info.get("sub")
        session["name"] = id_info.get("name", "Guest")
        session["email"] = id_info.get("email")
        session["picture"] = id_info.get("picture", "")

        print(f"Logged in as: {session['email']}")
        return redirect("/dashboard")  # Redirect to the dashboard after successful login

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
    print("Index route is being accessed")
    return render_template("index.html")

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
