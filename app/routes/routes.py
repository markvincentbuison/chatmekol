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

    return render_template("user_dashboard.html", name=name, email=email, picture=picture)
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
@routes.route('/dashboardx', methods=['GET', 'POST'])
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
        # Fetch the username, is_admin, is_verified, and profile picture for the logged-in user
        cursor.execute("SELECT username, is_admin, is_verified, picture FROM users WHERE id=%s", (session['user_id'],))
        user = cursor.fetchone()
        
        # Check if user data was found
        if not user:
            flash('No user found. Please log in again.', 'danger')
            return redirect(url_for('routes.logout'))

        # Extract user information
        username, is_admin, is_verified, picture = user

        # Save is_admin, is_verified, and picture in session for future use
        session['is_admin'] = is_admin
        session['is_verified'] = is_verified
        session['picture'] = picture  # Save profile picture path in session

        # Debugging: Log the user data
        print(f"User found: {username}, is_admin: {is_admin}, is_verified: {is_verified}, picture: {picture}")
        
        # Render appropriate dashboard based on user role
        if is_admin:
            print(f"Rendering admin dashboard for {username}")
            return render_template('admin_dashboard.html', username=username, is_verified=is_verified, picture=picture)
        else:
            print(f"Rendering user dashboard for {username}")
            return render_template('user_dashboard.html', username=username, is_verified=is_verified, picture=picture)
    
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
        conn = get_db_connection()
        cursor = conn.cursor()

        # 🛑 FIRST: Check if email already exists
        cursor.execute("SELECT * FROM users WHERE email_address = %s", (email_address,))
        existing_email = cursor.fetchone()
        if existing_email:
            flash('This email is already registered. Please log in.', 'danger')
            return redirect(url_for('routes.index'))

        # 🛑 SECOND: Check if username already exists separately
        cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
        existing_username = cursor.fetchone()
        if existing_username:
            flash('Username already taken. Please choose another.', 'danger')
            return redirect(url_for('routes.index'))

        # 🛡 Hash password
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        verification_token = generate_token(email_address)
        verification_expiry = datetime.utcnow() + timedelta(hours=1)
        default_profile_picture = 'static/background/bp1.png'

        # Insert user data
        cursor.execute("""
            INSERT INTO users (username, password, email_address, verification_token, verification_token_expiry, is_verified, picture)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (username, hashed_password, email_address, verification_token, verification_expiry, False, default_profile_picture))

        conn.commit()
        send_verification_email_function(email_address, verification_token, username)
        flash('Signup successful! Please verify your email.', 'success')

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
# Function to generate a token
def generate_token(email_address):
    serializer = URLSafeTimedSerializer(app.config['SECRET_KEY'])
    return serializer.dumps(email_address, salt=app.config['SECURITY_PASSWORD_SALT'])
#===RESENDING VERIFICATION EMAIL=============================================================================================
def send_email(subject, body, recipient):
    """Send an email with the provided subject, body, and recipient."""
    msg = Message(subject, recipients=[recipient])
    msg.body = body  # The plain-text body of the email
    
    try:
        mail.send(msg)
        logging.info(f"Email successfully sent to {recipient}")
    except Exception as e:
        logging.error(f"Error sending email to {recipient}: {e}")
#===RESENDING VERIFICATION EMAIL=============================================================================================
def send_verification_email_function(email, token, username):
    """Sends a verification email to the user with a unique token."""
    subject = "Verify Your Email - TunNer"
    verification_link = url_for('routes.verify_email', token=token, _external=True)
    
    body = f"""
Hi {username}, 

🎉 Welcome to TunNer! We're excited to have you on board.

To complete your registration, please verify your email address by clicking the link below:
🔗 {verification_link}

This link will expire after a short period, so be sure to verify soon!
If you didn’t sign up for TunNer, please ignore this email.

Cheers,
✨ The TunNer Team
"""
    try:
        send_email(subject, body, email)
        logging.info(f"Verification email sent to {email}.")
    except Exception as e:
        logging.error(f"Failed to send verification email to {email}: {e}")
#=====THIS IS A LINK CLICK IN GMAIL TO VERIFY IN THE BACKEND==================================================================================================================
def send_verification_email(user_email, verification_link):
    from_email = 'markvincentbuison@gmail.com'  # Replace with your email
    to_email = user_email
    subject = "Verify Your Email Now!"
    
    # Create the email content with UTF-8 encoding
    message = f"""
    Hi {user_email},

    🎉 Welcome to TunNer Team! We're excited to have you on board.

    To complete your registration, please verify your email address by clicking the link below:
    🔗 {verification_link}

    This link will expire after a short period, so be sure to verify soon!  
    If you didn’t sign up for TunNer, please ignore this email.

    Cheers,
    ✨ The TunNer Team
    """
    # Prepare the email message
    msg = MIMEMultipart()
    msg['From'] = from_email
    msg['To'] = to_email
    msg['Subject'] = subject
    msg.attach(MIMEText(message, 'plain', 'utf-8'))  # Ensure UTF-8 encoding

    try:
        # Send the email
        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.starttls()  # Start TLS encryption
            server.login(from_email, 'your-email-password')  # Log in to your email account
            server.sendmail(from_email, to_email, msg.as_string())  # Send the email
    except Exception as e:
        print(f"Failed to send email: {e}")

#====Email verification route==========================================================================================================
@routes.route('/verify-email/<token>')
def verify_email(token):
    conn = get_db_connection()  # Use get_db_connection instead of create_connection
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    try:
        print(f"Verification token received: {token}")  # Debugging: Print token received

        # Check if the token exists in the database
        cursor.execute("SELECT * FROM users WHERE verification_token=%s", (token,))
        user = cursor.fetchone()

        if user:
            print(f"User found: {user}")  # Debugging: Log the user found
            # Update the user record to set is_verified and clear verification_token
            cursor.execute("UPDATE users SET is_verified=TRUE, verification_token=NULL WHERE verification_token=%s", (token,))
            conn.commit()
            flash("Email verified successfully.", 'success')
            return redirect(url_for('routes.dashboard'))  # Redirect to dashboard or any page after successful verification
        else:
            print("Token not found or expired!")  # Debugging: Print error
            flash("Invalid or expired verification link.", 'danger')

    except psycopg2.errors.DatabaseError as e:
        print(f"Error during verification: {e}")
        conn.rollback()  # Rollback in case of an error
        flash("An error occurred while verifying your email. Please try again later.", 'danger')
    finally:
        cursor.close()
        conn.close()

    return redirect(url_for('routes.index'))  # Redirect back to homepage if something went wrong
# ======UPLOAD PICTURE===========================================================================================================
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

@routes.route('/upload_picture', methods=['POST'])
def upload_picture():
    if 'file' not in request.files:
        return redirect(request.url)
    file = request.files['file']
    
    if file.filename == '':
        return redirect(request.url)
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        # Save the file in the UPLOAD_FOLDER
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        
        # Update the session with the new picture's file path
        session['picture'] = url_for('static', filename=f'background/{filename}')
        
        return redirect(url_for('dashboard'))

    return "File type not allowed", 400
#=============================================================================================================================================================================
#=============================================================================================================================================================================
#=============================================================================================================================================================================
#=============================================================================================================================================================================        
#=============================================================================================================================================================================
#=============================================================================================================================================================================
#=============================================================================================================================================================================
#=============================================================================================================================================================================
#=============================================================================================================================================================================
#=============================================================================================================================================================================
#=============================================================================================================================================================================
#=============================================================================================================================================================================
#=============================================================================================================================================================================
#=============================================================================================================================================================================
#=============================================================================================================================================================================
#=============================================================================================================================================================================
#=============================================================================================================================================================================
#=============================================================================================================================================================================
#=============================================================================================================================================================================
@routes.route('/forgot-password', methods=['POST'])
def forgot_password():
    email = request.form.get('forgot_email')
    if not email:
        flash('Please enter your email address.', 'warning')
        return redirect(url_for('routes.index'))

    conn = get_db_connection()  # Use get_db_connection instead of create_connection
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cursor.execute("SELECT * FROM users WHERE email_address=%s", (email,))
    user = cursor.fetchone()

    if user:
        reset_token = generate_token(email)  # Pass the email to generate_token
        cursor.execute("UPDATE users SET reset_token=%s WHERE email_address=%s", (reset_token, email))
        conn.commit()

        # Fetch the username from the user object and pass it to send_reset_email
        username = user['username']
        send_reset_email(email, reset_token, username)  # Pass the username to the email function
        
        flash('A password reset link has been sent to your email.', 'info')
    else:
        flash('Email not found.', 'danger')

    cursor.close()
    conn.close()
    return redirect(url_for('routes.index'))

def generate_token(email):
    serializer = URLSafeTimedSerializer(app.config['SECRET_KEY'])
    return serializer.dumps(email, salt='password-reset')

def send_reset_email(email, reset_token, username):
    # Create the reset URL (this is where the user will go to reset their password)
    reset_url = url_for('routes.reset_password', token=reset_token, _external=True)
    
    # Email content
    subject = "Password Reset Request"
    body = f"""
    Hello {username},

    You requested a password reset. Please click the link below to reset your password:

    {reset_url}

    If you did not request this, please ignore this email.

    Best regards,
    Your Team
    """
    
    # Send the email
    send_email(email, subject, body)

def send_email(to, subject, body):
    """Send the email using Flask-Mail"""
    msg = Message(subject=subject, recipients=[to])
    msg.body = body  # Set the email body

    try:
        mail.send(msg)  # Send the email
        print("Email sent successfully!")  # Log success
    except Exception as e:
        print(f"Error sending email: {e}")  # Log failure
#===========RESET PASSWORD ============================================================================================================
@routes.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    if request.method == 'GET':
        return render_template('reset_password.html', token=token)

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
        cursor.execute("SELECT * FROM users WHERE reset_token=%s", (token,))
        user = cursor.fetchone()
        cursor.fetchall()

        if user:
            cursor.execute(
                "UPDATE users SET password=%s, reset_token=NULL WHERE reset_token=%s",
                (hashed_password, token)
            )
            conn.commit()
            flash("Your password has been reset successfully.", "success")
        else:
            flash("Invalid or expired reset token.", "danger")
    except Exception as e:
        print("Reset password error:", e)
        flash("An error occurred while resetting the password. Please try again.", "danger")
    finally:
        cursor.close()
        conn.close()

    return redirect(url_for('routes.index'))
#=============================================================================================================================================================================




