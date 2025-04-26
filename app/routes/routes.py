import os
import pathlib
from flask import Blueprint, redirect, session, request, abort
from google_auth_oauthlib.flow import Flow
from google.oauth2 import id_token
from google.auth.transport.requests import Request
from dotenv import load_dotenv
from functools import wraps
from flask import make_response
from app.routes.postgresql import get_db_connection
from flask import render_template
from flask import session
#--------------------------------------------------------------------------------------------------
# Load environment variables from .env file
load_dotenv()
#--------------------------------------------------------------------------------------------------
# Blueprint setup for Google OAuth routes
routes = Blueprint('routes', __name__)
#--------------------------------------------------------------------------------------------------
# Determine if running in production
IS_PRODUCTION = os.getenv("FLASK_ENV") == "production"
#--------------------------------------------------------------------------------------------------
# Load Google OAuth Client ID from environment
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_OAUTH_CLIENT_ID")
#--------------------------------------------------------------------------------------------------
#--------------------------------------------------------------------------------------------------
#--------------------------------------------------------------------------------------------------
#--------------------------------------------------------------------------------------------------
#--------------------------------------------------------------------------------------------------
#--------------------------------------------------------------------------------------------------
#--------------------------------------------------------------------------------------------------
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
# Get the redirect URI. Always use the Render callback URL for production.
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
@routes.route("/login/google")
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
@routes.route("/callback")
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
@routes.route("/logout")
def logout():
    session.clear()  # Clear the session to log out the user
    return redirect("/")
#--------------------------------------------------------------------------------------------------
# Index route (for demonstration purposes)
@routes.route("/")
def index():
    if "google_id" in session:
        return redirect("/dashboard")
    response = make_response(render_template("index.html"))
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    return response
#--------------------------------------------------------------------------------------------------
# Protected area route (for logged-in users)
@routes.route("/dashboard")
@login_is_required
def dashboard():
    name = session.get("name")
    email = session.get("email")
    picture = session.get("picture")

    return render_template("dashboard.html", name=name, email=email, picture=picture)
#--------------------------------------------------------------------------------------------------
@routes.route('/test-db')
def test_db():
    conn = get_db_connection()
    if conn:
        return "PostgreSQL connected successfully!"
    return "Connection failed."
#--------------------------------------------------------------------------------------------------
#--------------------------------------------------------------------------------------------------
#--------------------------------------------------------------------------------------------------
#--------------------------------------------------------------------------------------------------
#--------------------------------------------------------------------------------------------------
#--------------------------------------------------------------------------------------------------
#--------------------------------------------------------------------------------------------------
#--------------------------------------------------------------------------------------------------
#--------------------------------------------------------------------------------------------------
#--------------------------------------------------------------------------------------------------
#--------------------------------------------------------------------------------------------------
#--------------------------------------------------------------------------------------------------
#--------------------------------------------------------------------------------------------------
#--------------------------------------------------------------------------------------------------
#--------------------------------------------------------------------------------------------------
#--------------------------------------------------------------------------------------------------
#--------------------------------------------------------------------------------------------------
#--------------------------------------------------------------------------------------------------
#--------------------------------------------------------------------------------------------------
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask_mail import Message
from flask_dance.contrib.google import google
from app.mysql_connect import create_connection
from app.extensions.mail import mail
from app.utils import (generate_token, send_email, send_verification_email, send_reset_email)
import bcrypt
import re
import mysql.connector
from datetime import datetime, timedelta
import logging
import psycopg2.extras
# =================================================================================================================
def validate_username(username):
    if len(username) < 3 or len(username) > 11:
        return "Username must be between 3 and 11 characters."
    if not re.match("^[A-Za-z0-9]*$", username):
        return "Username can only contain letters and numbers."
    return None

def hash_password(password):
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def send_verification_email_function(email, token):
    subject = "Email Verification"
    verification_link = url_for('routes.verify_email', token=token, _external=True)
    body = f"Please verify your email by clicking the following link: {verification_link}"
    send_email(subject, body, email)
#==============Login=============================================================================================
@routes.route('/login', methods=['POST'])
def login():
    # Prevent logged-in users from going back to login page
    if 'user_id' in session:
        return redirect(url_for('routes.dashboardx'))  # Redirect to dashboard if already logged in

    username = request.form['username']
    password = request.form['password']

    # Try creating a connection using get_db_connection
    conn = get_db_connection()
    if conn is None:
        flash('Failed to connect to the database.', 'danger')
        return redirect(url_for('routes.index'))

    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cursor.execute("SELECT * FROM users WHERE username=%s", (username,))
        user = cursor.fetchone()
    except Exception as e:
        print("[DB ERROR]", e)
        flash('Database error occurred.', 'danger')
        return redirect(url_for('routes.index'))
    finally:
        if conn:
            conn.close()

    if user:
        try:
            stored_hash = user[2]  # Assuming 3rd column is password hash
            if stored_hash and isinstance(stored_hash, str):
                stored_hash = stored_hash.encode('utf-8')
                if bcrypt.checkpw(password.encode('utf-8'), stored_hash):
                    session['user_id'] = user[0]
                    session['username'] = user[1]
                    session['is_admin'] = user[-2]
                    return redirect(url_for('routes.dashboardx'))
                else:
                    flash('Incorrect password.', 'danger')
            else:
                flash('Invalid password format in the database.', 'danger')
        except ValueError as e:
            print("Bcrypt error:", e)
            flash('Invalid password hash. Please contact support.', 'danger')
    else:
        flash('User not found.', 'danger')

    return redirect(url_for('routes.index'))
#=============Dashboard==============================================================================================
@routes.route('/dashboardx')
def dashboardx():
    if 'user_id' not in session:
        flash('You need to login to access the system', 'warning')
        return redirect(url_for('routes.index'))

    # Use get_db_connection instead of create_connection
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    # ✅ Fetch username, is_admin, and is_verified
    cursor.execute("SELECT username, is_admin, is_verified FROM users WHERE id=%s", (session['user_id'],))
    user = cursor.fetchone()
    cursor.close()
    conn.close()

    if user:
        username, is_admin, is_verified = user
        session['is_admin'] = is_admin
        session['is_verified'] = is_verified  # ✅ Save to session for reuse if needed
        if is_admin:
            return render_template('admin_dashboard.html', username=username, is_verified=is_verified)
        else:
            return render_template('user_dashboard.html', username=username, is_verified=is_verified)
    
    flash('User not found. Please login again.', 'danger')
    return redirect(url_for('routes.logout'))
#================Signup=========================================================================================
@routes.route('/signup', methods=['POST'])
def signup():
    username = request.form.get('username')
    password = request.form.get('password')
    email_address = request.form.get('email_address')
    confirmation_password = request.form.get('confirm_password')
    
    if not email_address:
        flash('Email address is required.', 'danger')
        return redirect(url_for('routes.index'))
    
    if (err := validate_username(username)):
        flash(err, 'danger')
        return redirect(url_for('routes.index'))
    
    if password != confirmation_password:
        flash('Passwords do not match.', 'danger')
        return redirect(url_for('routes.index'))
    
    try:
        # 🔐 Hash password using bcrypt
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        verification_token = generate_token()
        verification_expiry = datetime.utcnow() + timedelta(hours=1)
        
        conn = get_db_connection()  # Use get_db_connection instead of create_connection
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        
        # Check for existing username or email
        cursor.execute("SELECT * FROM users WHERE username=%s OR email_address=%s", (username, email_address))
        if cursor.fetchone():
            flash('Username or Email already exists.', 'danger')
            return redirect(url_for('routes.index'))
        
        cursor.execute(""" 
            INSERT INTO users (username, password, email_address, verification_token, verification_token_expiry, is_verified)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (username, hashed_password, email_address, verification_token, verification_expiry, False))
        
        conn.commit()
        send_verification_email(email_address, verification_token, username)
        flash('Signup successful. Check your email to verify your account.', 'success')
    except Exception as e:
        print(f"Signup error: {e}")
        flash('An error occurred during signup. Please try again.', 'danger')
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
    return redirect(url_for('routes.index'))
#=============Verify email=========================================================================================
@routes.route('/verify-email/<token>')
def verify_email(token):
    conn = get_db_connection()  # Use get_db_connection instead of create_connection
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    try:
        cursor.execute("SELECT * FROM users WHERE verification_token=%s", (token,))
        user = cursor.fetchone()
        if user:
            # Update is_verified to TRUE and clear the verification token
            cursor.execute("""
                UPDATE users 
                SET is_verified = TRUE, verification_token = NULL 
                WHERE email_address = %s
            """, (user['email_address'],))
            conn.commit()
            flash("Email verified successfully.", 'success')
            return redirect(url_for('routes.dashboard'))
        flash("Invalid or expired verification link.", 'danger')
    except Exception as e:
        print(f"Error during verification: {e}")
        conn.rollback()
        flash("An error occurred while verifying your email.", 'danger')
    finally:
        cursor.close()
        conn.close()
    return redirect(url_for('routes.index'))
#============================FORGOT PASSWORD========================================================================
from app.routes.postgresql import get_db_connection  # Import the get_db_connection function

@routes.route('/forgot-password', methods=['POST'])
def forgot_password():
    email_address = request.form.get('forgot_email')
    if not email_address:
        flash('Please enter your email address.', 'warning')
        return redirect(url_for('routes.index'))
    
    conn = get_db_connection()  # Use get_db_connection instead of create_connection
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    try:
        cursor.execute("SELECT * FROM users WHERE email_address=%s", (email_address,))
        user = cursor.fetchone()
        if user:
            reset_token = generate_token()
            reset_expiry = datetime.utcnow() + timedelta(hours=1)
            username = user['username']  # Now safer to access by column name
            cursor.execute(
                "UPDATE users SET reset_token=%s, reset_token_expiry=%s WHERE email_address=%s",
                (reset_token, reset_expiry, email_address)
            )
            conn.commit()
            send_reset_email(email_address, reset_token, username)
            flash('A password reset link has been sent to your email.', 'info')
        else:
            flash('Email not found. Please try again.', 'danger')
    except Exception as e:
        print(f"Error during password reset request: {e}")
        conn.rollback()
        flash('An error occurred while processing your request.', 'danger')
    finally:
        cursor.close()
        conn.close()
    
    return redirect(url_for('routes.index'))

#========================USER RESET PASSWORD========================================================================
@routes.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    if request.method == 'GET':
        return render_template('user_reset_password.html', token=token)  # ✅ updated template name

    new_password = request.form.get('new_password')
    confirm_password = request.form.get('confirm_password')

    if not new_password or not confirm_password:
        flash("Please fill out both fields.", "danger")
        return redirect(url_for('routes.reset_password', token=token))

    if new_password != confirm_password:
        flash("Passwords do not match.", "danger")
        return redirect(url_for('routes.reset_password', token=token))

    hashed_password = hash_password(new_password)

    conn = get_db_connection()  # Use get_db_connection instead of create_connection
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    try:
        cursor.execute("SELECT reset_token_expiry FROM users WHERE reset_token=%s", (token,))
        result = cursor.fetchone()

        if not result:
            flash("Invalid or expired reset token.", "danger")
        else:
            expiry_time = result['reset_token_expiry']  # safer access by column name
            if datetime.utcnow() > expiry_time:
                flash("Reset token has expired. Please request a new one.", "danger")
            else:
                cursor.execute("""
                    UPDATE users
                    SET password=%s, reset_token=NULL, reset_token_expiry=NULL
                    WHERE reset_token=%s
                """, (hashed_password, token))
                conn.commit()
                flash("Your password has been reset successfully.", "success")
    except Exception as e:
        print("Reset password error:", e)
        conn.rollback()
        flash("An error occurred while resetting the password.", "danger")
    finally:
        cursor.close()
        conn.close()

    return redirect(url_for('routes.index'))

#============Send Verification Email==================================================================================
@routes.route('/send-verification-email', methods=['POST'])
def send_verification_email_route_dashboard():
    user_id = session.get('user_id')
    if not user_id:
        flash('You need to be logged in to send verification email.', 'warning')
        return redirect(url_for('routes.index'))

    conn = get_db_connection()  # Use get_db_connection instead of create_connection
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    try:
        cursor.execute("SELECT email_address FROM users WHERE id=%s", (user_id,))
        user = cursor.fetchone()
        if user:
            email_address = user['email_address']  # safer by column name
            token = generate_token()
            cursor.execute("UPDATE users SET verification_token=%s WHERE id=%s", (token, user_id))
            conn.commit()
            send_verification_email_function(email_address, token)
            flash('Verification email sent. Please check your inbox.', 'success')
        else:
            flash('User not found.', 'danger')
    except Exception as e:
        print(f"Error during sending verification email: {e}")
        conn.rollback()
        flash('An error occurred while sending verification email.', 'danger')
    finally:
        cursor.close()
        conn.close()

    return redirect(url_for('routes.dashboard'))


#======================================================================================================================

