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
from flask import current_app
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
    # Get the session data (name, email, etc.)
    name = session.get("name")
    email = session.get("email")
    picture = session.get("picture")
    
    # Check the email verification status from the database
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # First: fetch verification status for the current email
        cursor.execute("SELECT is_verified FROM users WHERE email_address = %s", (email,))
        verification_status = cursor.fetchone()

        # Optional: fetch columns info for debug
        cursor.execute("SELECT * FROM users LIMIT 1")
        columns = [desc[0] for desc in cursor.description]
        print(f"Columns in the users table: {columns}")

    finally:
        cursor.close()
        conn.close()

    # Handle verification status safely
    if verification_status:
        is_verified = verification_status['is_verified']  # <-- fix here
    else:
        is_verified = False  # Default if no result found

    # Pass everything to the template
    return render_template("user_dashboard.html", name=name, email=email, picture=picture, is_verified=is_verified)
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
from app.extensions.mail import mail
from app.utils import (generate_token, send_email, send_verification_email, send_reset_email)
import bcrypt
import re
from datetime import datetime, timedelta
import logging
import psycopg2.extras
from flask import current_app as app
from itsdangerous import URLSafeTimedSerializer
from flask import render_template, request, redirect, url_for, flash, session

# =====Upload Picture============================================================================================================
from flask import Flask, request, redirect, url_for, session, render_template
import os
from werkzeug.utils import secure_filename
import jwt

# =================================================================================================================
def validate_username(username):
    if len(username) < 3 or len(username) > 16:
        return "Username must be between 3 and 16 characters."
    if not re.match("^[A-Za-z0-9]*$", username):
        return "Username can only contain letters and numbers."
    return None
#==============Login=============================================================================================
def hash_password(password):
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
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
@routes.route('/dashboard-manual-login')
def dashboardx():
    # Check if user is logged in by checking session for user_id
    if 'user_id' not in session:
        flash('You need to login to access the system', 'warning')
        return redirect(url_for('routes.index'))
    
    # Establish database connection
    conn = get_db_connection()
    if not conn:
        flash('Failed to connect to the database', 'danger')
        return redirect(url_for('routes.index'))
    
    # Create a cursor for executing SQL queries
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    
    try:
        # Fetch the username, email, is_admin, and is_verified for the logged-in user
        cursor.execute("SELECT username, email_address, is_admin, is_verified FROM users WHERE id=%s", (session['user_id'],))
        user = cursor.fetchone()
        
        # Check if user data was found
        if not user:
            flash('No user found. Please log in again.', 'danger')
            return redirect(url_for('routes.logout'))

        # Extract user information
        username, email, is_admin, is_verified = user

        # Save is_admin, is_verified, and email in session for future use
        session['is_admin'] = is_admin
        session['is_verified'] = is_verified
        session['email'] = email

        # Debugging: Log the user data
        print(f"User found: {username}, is_admin: {is_admin}, is_verified: {is_verified}, email: {email}")
        
        # Handle email verification status in dashboard
        if is_verified:
            print(f"User {username} is verified.")
        else:
            print(f"User {username} is not verified. Please check your email.")

        # Render appropriate dashboard based on user role
        if is_admin:
            print(f"Rendering admin dashboard for {username}")
            return render_template('admin_dashboard.html', username=username, is_verified=is_verified, email=email)
        else:
            # Provide a default profile picture
            picture = 'background/bp1.png'
            print(f"Rendering user dashboard for {username}")
            return render_template('user_dashboard.html', username=username, is_verified=is_verified, email=email, profile_picture=picture)

    except Exception as e:
        # Log any exceptions
        print(f"Error: {str(e)}")
        flash('An error occurred while fetching your data. Please try again later.', 'danger')
        return redirect(url_for('routes.index'))
    
    finally:
        # Ensure the cursor and connection are closed after the operation
        cursor.close()
        conn.close()

#=======================================================================================================================
# Signup route
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
    conn = None
    cursor = None
    try:
        # 🔐 Hash password using bcrypt
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        verification_token = generate_token(email_address)
        verification_expiry = datetime.utcnow() + timedelta(hours=1)
        conn = get_db_connection()  
        cursor = conn.cursor()
        # Check if username or email already exists
        cursor.execute("SELECT * FROM users WHERE username=%s OR email_address=%s", (username, email_address))
        if cursor.fetchone():
            flash('Username or Email already exists.', 'danger')
            return redirect(url_for('routes.index'))
        # Set the default profile picture path
        default_profile_picture = 'background/bp1.png'  # ✅ Correct path
        # Insert new user with default picture
        cursor.execute(""" 
            INSERT INTO users (username, password, email_address, verification_token, verification_token_expiry, is_verified, picture)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (username, hashed_password, email_address, verification_token, verification_expiry, False, default_profile_picture))
        conn.commit()
        send_verification_email_function(email_address, verification_token, username)
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
#=======================================================================================================================
#=======================================================================================================================
# Function to generate a token
def generate_token(email_address):
    serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    return serializer.dumps(email_address, salt=current_app.config['SECURITY_PASSWORD_SALT'])
#=======================================================================================================================
#=== FOR SIGN UP FOR SENDING A VERIFICATION TO EMAIL====================================================================
#=======================================================================================================================
#=======================================================================================================================
# Route for email verification
# Generate a verification token for email
def generate_verification_token(email):
    try:
        expiration_time = datetime.utcnow() + timedelta(hours=1)  # Token expires in 1 hour
        payload = {'email': email, 'exp': expiration_time}
        token = jwt.encode(payload, current_app.config['SECRET_KEY'], algorithm='HS256')
        return token
    except Exception as e:
        print(f"Error generating token: {e}")
        return None
#=== FOR SIGN UP FOR SENDING A VERIFICATION TO EMAIL====================================================================
# Function to confirm the verification token
def confirm_verification_token(token):
    try:
        # Try decoding the token
        payload = jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=['HS256'])
        return payload['email']
    except jwt.ExpiredSignatureError:
        raise ValueError("The token has expired.")
    except jwt.DecodeError:
        raise ValueError("Invalid token.")
    except Exception as e:
        raise ValueError(f"Error decoding token: {e}")
#=== FOR SIGN UP FOR SENDING A VERIFICATION TO EMAIL====================================================================
# Function to send the verification email
def send_verification_email_function(email, token, username):
    
    try:
        print(f"Generating verification email for {email} with token {token}")
        subject = "Email Verification"
        
        # Generate the verification URL using url_for
        verification_link = url_for('routes.verify_email', token=token, _external=True)
        
        body = f"""
        Hi {username},
        
        Thanks for signing up! Please verify your email by clicking the following link:
        {verification_link}
        
        If you did not sign up for this account, please ignore this email.
        
        Regards,
        TunNer Developer Team
        """
        
        # Debugging: Check email body and recipient
        print(f"Email body: {body}")
        print(f"Sending to: {email}")
        
        # Send the email using the send_email function
        send_email(subject, body, email)
    except Exception as e:
        print(f"Error sending verification email: {e}")
#=== FOR SIGN UP FOR SENDING A VERIFICATION TO EMAIL====================================================================
# Function to send email using Flask-Mail
def send_email(subject, body, recipient):
    try:
        print(f"Sending email to {recipient}")  # Debug line to check if the email is being triggered
        msg = Message(subject, recipients=[recipient])
        msg.body = body
        mail.send(msg)
        print("Email sent successfully!")  # Debug line to confirm email was sent
    except Exception as e:
        print(f"Error sending email: {e}")
#=== FOR SIGN UP FOR SENDING A VERIFICATION TO EMAIL====================================================================
# Route to verify the email and token
@routes.route('/verify_email/<token>', methods=['GET'])
def verify_email(token):
    try:
        # Deserialize the token using the same secret key and salt
        serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
        email_address = serializer.loads(
            token,
            salt=current_app.config['SECURITY_PASSWORD_SALT'],
            max_age=3600  # The token is valid for 1 hour
        )

        # Update the user's 'is_verified' status in the database
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET is_verified = TRUE WHERE email_address = %s", (email_address,))
        conn.commit()
        flash('Email verified successfully. You can now log in.', 'success')

    except SignatureExpired:
        flash('Verification link has expired.', 'danger')
    except Exception as e:
        flash(f'Error verifying email: {e}', 'danger')
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

    return redirect(url_for('routes.index'))
#=== FOR SIGN UP FOR SENDING A VERIFICATION TO EMAIL====================================================================
# Generate a confirmation token (alternative function)
def generate_confirmation_token(email):
    try:
        payload = {
            'email': email,
            'exp': datetime.utcnow() + timedelta(hours=1)
        }
        return jwt.encode(payload, current_app.config['SECRET_KEY'], algorithm='HS256')
    except Exception as e:
        print(f"Error generating confirmation token: {e}")
        return None
#=======================================================================================================================
#=======================================================================================================================
#=======================================================================================================================
#===========FORGOT PASSWORD PANEL=======================================================================================
#============================FORGOT PASSWORD========================================================================
# Forgot Password Route

DATABASE_URL = os.getenv("DATABASE_URL")  # Fetch the database URL from environment

@routes.route('/forgot-password', methods=['POST'])
def forgot_password():
    email = request.form.get('forgot_email')
    if not email:
        flash('Please enter a valid email address.', 'danger')
        return redirect(url_for('routes.index'))
    
    conn = None
    cursor = None
    try:
        # Establish connection to PostgreSQL database
        conn = psycopg2.connect(DATABASE_URL, sslmode='require')  # Ensure SSL connection
        cursor = conn.cursor()

        # Check if the email exists in the database
        cursor.execute("SELECT email_address, username FROM users WHERE email_address = %s", (email,))
        user = cursor.fetchone()
        
        if user:
            # Extract username from the fetched data
            username = user[1]
            
            # Generate a reset token
            reset_token = generate_reset_token(email)
            # Generate the reset link
            reset_link = url_for('routes.reset_password', token=reset_token, _external=True)
            
            # Create email subject and body
            subject = "Password Reset Request"
            body = f"""Hi {username},

You requested a password reset. Click the link below to reset your password:

{reset_link}

This link will expire in 60 seconds.

If you did not request this, you can safely ignore this email.

Best regards,
TunNer Team
"""
            
            # Send the reset email
            send_email(subject, body, email)
            flash('A password reset link has been sent to your email. The link will expire in 30 seconds.', 'success')
        else:
            flash('Email address not found.', 'danger')
    
    except Exception as e:
        print(f"Error in forgot-password route: {e}")
        flash(f"An error occurred while processing your request: {e}", 'danger')
    
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
    
    return redirect(url_for('routes.index'))

#=======================================================================================================================
# Reset Password Route
@routes.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    try:
        email = confirm_verification_token_reset(token)
        print(f"Decoded email: {email}")  # Log decoded email
        
        if request.method == 'POST':
            new_password = request.form.get('new_password')
            new_password_confirm = request.form.get('confirm_password')
            
            if new_password != new_password_confirm:
                flash('Passwords do not match.', 'danger')
                return redirect(url_for('routes.reset_password', token=token))
            
            hashed_password = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET password = %s WHERE email_address = %s", (hashed_password, email))
            conn.commit()
            flash('Password has been reset successfully. You can now log in.', 'success')
            return redirect(url_for('routes.index'))  
        return render_template('reset_password.html', token=token)  
    except ValueError as e:
        print(f"Error: {e}")
        flash('The reset link is invalid or expired.', 'danger')
        return redirect(url_for('routes.index'))
#=======================================================================================================================
# Generate Reset Token Function
def generate_reset_token(email):
    serializer = URLSafeTimedSerializer(app.secret_key)
    return serializer.dumps(email, salt='password-reset-salt')
#=======================================================================================================================
# Confirm Reset Token Function
def confirm_verification_token_reset(token, expiration=60):  # expiration is in seconds (20 = 20 seconds)
    serializer = URLSafeTimedSerializer(app.secret_key)
    try:
        email = serializer.loads(token, salt='password-reset-salt', max_age=expiration)
    except Exception as e:
        print(f"Error: {e}")
        raise ValueError("The reset link is invalid or expired.")
    return email
#=======================================================================================================================
def verify_reset_token(token):
    try:
        email = jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"])['email']
    except Exception:
        return None
    return User.query.filter_by(email=email).first()
#=======================================================================================================================
#=======================================================================================================================
#=======================================================================================================================
#=====THIS IS FACEBOOK LOGIN============================================================================================
from flask_dance.contrib.facebook import facebook
from flask import redirect, url_for, flash, render_template, session
import psycopg2

# Route for handling Facebook login callback
@routes.route('/facebook-login/callback')
def facebook_login_callback():
    if not facebook.authorized:
        flash('Login failed', 'danger')
        return redirect(url_for('routes.index'))

    # Fetch user data from Facebook
    resp = facebook.get('/me?fields=id,name,email')
    
    if resp.ok:
        user_info = resp.json()
        facebook_id = user_info['id']
        facebook_name = user_info['name']
        facebook_email = user_info.get('email')

        # Connect to PostgreSQL and create or fetch user
        user = create_or_fetch_user(facebook_id, facebook_name, facebook_email)
        
        # Set session and redirect to the dashboard
        session['user_id'] = user[0]  # Assuming user id is at index 0
        flash(f'Welcome, {facebook_name}!', 'success')
        return redirect(url_for('routes.dashboard'))  # Redirect to the dashboard
    else:
        flash('Failed to fetch user data from Facebook', 'danger')
        return redirect(url_for('routes.index'))


# Function to create a new user in the database
def create_new_user(facebook_id, name, email):
    try:
        # Connect to PostgreSQL (using your existing connection function)
        conn = get_db_connection()
        cursor = conn.cursor()

        # Insert new user into the users table
        cursor.execute(
            "INSERT INTO users (facebook_id, username, email_address) VALUES (%s, %s, %s) RETURNING id;",
            (facebook_id, name, email)
        )
        user_id = cursor.fetchone()[0]
        conn.commit()

        # Fetch and return the newly created user
        cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
        user = cursor.fetchone()
        return user  # Returning the user object
        
    except Exception as e:
        print(f"Error creating new user: {e}")
        flash('An error occurred while creating your account.', 'danger')
    finally:
        if conn:
            cursor.close()
            conn.close()

# Facebook login route
@routes.route('/login/facebook')
def facebook_login():
    if not facebook.authorized:
        return redirect(url_for('facebook.login'))  # Redirect to Facebook login if not authorized
    
    # If authorized, redirect to Facebook login callback
    return redirect(url_for('routes.facebook_login_callback'))