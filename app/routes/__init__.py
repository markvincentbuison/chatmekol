from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask_mail import Message
from flask_dance.contrib.google import google
from flask_dance.contrib.google import make_google_blueprint, google
from app.mysql_connect import create_connection
from app.extensions.mail import mail
from app.utils import (generate_token, send_email,send_verification_email, send_reset_email)
import bcrypt
import re
import mysql.connector  # Add this import at the top of the file
#=====================GOOGLE AUTH=======================
from flask import Flask, redirect, url_for, session, flash
from flask_dance.contrib.google import make_google_blueprint, google
import mysql.connector
from app.mysql_connect import create_connection  # Assuming you have this in mysql_connect.py
# ============================================
# Blueprint Functions
# ============================================
routes = Blueprint('routes', __name__)
# ============================================
# Helper Functions
# ============================================
def validate_username(username):
    if len(username) < 3 or len(username) > 11:
        return "Username must be between 3 and 11 characters."
    if not re.match("^[A-Za-z0-9]*$", username):
        return "Username can only contain letters and numbers."
    return None

def hash_password(password):
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt)

def send_verification_email_function(email, token):
    subject = "Email Verification"
    verification_link = url_for('routes.verify_email', token=token, _external=True)
    body = f"Please verify your email by clicking the following link: {verification_link}"
    send_email(subject, body, email)

# ============================================
# Routes
# ============================================

@routes.route('/')
def index():
    return render_template('index.html')

@routes.route('/login', methods=['POST'])
def login():
    username = request.form['username']
    password = request.form['password']
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE username=%s", (username,))
    user = cursor.fetchone()
    cursor.fetchall()
    cursor.close()
    conn.close()
    if user and bcrypt.checkpw(password.encode('utf-8'), user[2].encode('utf-8')):  # Assuming password is at index 2
        session['user_id'] = user[0]
        session['username'] = user[1]
        return redirect(url_for('routes.dashboard'))
    flash('Invalid credentials, please try again.', 'danger')
    return redirect(url_for('routes.index'))

@routes.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        flash('You need to login to access the system', 'warning')
        return redirect(url_for('routes.index'))
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT username, is_verified FROM users WHERE id=%s", (session['user_id'],))
    user = cursor.fetchone()
    cursor.close()
    conn.close()
    if user:
        return render_template('dashboard.html', username=user[0], is_verified=user[1])
    flash('User not found. Please login again.', 'danger')
    return redirect(url_for('routes.logout'))

@routes.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('username', None)
    flash('You have been logged out successfully.', 'info')
    return redirect(url_for('routes.index'))

# Signup route
@routes.route('/signup', methods=['POST'])
def signup():
    username = request.form.get('username')
    password = request.form.get('password')
    email = request.form.get('email_address')
    confirmation_password = request.form.get('confirm_password')

    if not email:
        flash('Email address is required.', 'danger')
        return redirect(url_for('routes.index'))
    if (err := validate_username(username)):
        flash(err, 'danger')
        return redirect(url_for('routes.index'))
    if password != confirmation_password:
        flash('Passwords do not match.', 'danger')
        return redirect(url_for('routes.index'))

    hashed_password = hash_password(password)
    verification_token = generate_token()

    if not verification_token:
        flash('Failed to generate verification token.', 'danger')
        return redirect(url_for('routes.index'))

    try:
        conn = create_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM users WHERE username=%s OR email_address=%s", (username, email))
        if cursor.fetchone():
            flash('Username or Email already exists.', 'danger')
            return redirect(url_for('routes.index'))

        cursor.execute("""
            INSERT INTO users (username, password, email_address, verification_token, is_verified)
            VALUES (%s, %s, %s, %s, %s)
        """, (username, hashed_password, email, verification_token, 0))
        conn.commit()

        send_verification_email(email, verification_token)
        flash('Signup successful. Check your email to verify your account.', 'success')

    except Exception as e:
        print("Signup error:", e)
        flash('An error occurred during signup. Please try again.', 'danger')
    finally:
        cursor.close()
        conn.close()

    return redirect(url_for('routes.index'))

# Email verification route
@routes.route('/verify-email/<token>')
def verify_email(token):
    conn = create_connection()
    cursor = conn.cursor()

    try:
        print(f"Verification token received: {token}")  # Debugging: Print token received

        # Check if the token exists in the database
        cursor.execute("SELECT * FROM users WHERE verification_token=%s", (token,))
        user = cursor.fetchone()

        if user:
            print(f"User found: {user}")  # Debugging: Log the user found
            # Update the user record to set is_verified and clear verification_token
            cursor.execute("UPDATE users SET is_verified=1, verification_token=NULL WHERE verification_token=%s", (token,))
            conn.commit()
            flash("Email verified successfully.", 'success')
            return redirect(url_for('routes.dashboard'))  # Redirect to dashboard or any page after successful verification
        else:
            print("Token not found or expired!")  # Debugging: Print error
            flash("Invalid or expired verification link.", 'danger')

    except mysql.connector.errors.DatabaseError as e:
        print(f"Error during verification: {e}")
        conn.rollback()  # Rollback in case of an error
        flash("An error occurred while verifying your email. Please try again later.", 'danger')
    finally:
        cursor.close()
        conn.close()

    return redirect(url_for('routes.index'))  # Redirect back to homepage if something went wrong


@routes.route('/forgot-password', methods=['POST'])
def forgot_password():
    email = request.form.get('forgot_email')
    if not email:
        flash('Please enter your email address.', 'warning')
        return redirect(url_for('routes.index'))

    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE email_address=%s", (email,))
    user = cursor.fetchone()
    cursor.fetchall()
    if user:
        reset_token = generate_token()
        cursor.execute("UPDATE users SET reset_token=%s WHERE email_address=%s", (reset_token, email))
        conn.commit()
        send_reset_email(email, reset_token)
        flash('A password reset link has been sent to your email.', 'info')
    else:
        flash('Email not found.', 'danger')

    cursor.close()
    conn.close()
    return redirect(url_for('routes.index'))

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

    conn = create_connection()
    cursor = conn.cursor()

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

@routes.route('/send-verification-email', methods=['POST'])
def send_verification_email_route_dashboard():
    user_id = session.get('user_id')
    if not user_id:
        flash('You need to be logged in to send verification email.', 'warning')
        return redirect(url_for('routes.index'))

    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT email_address FROM users WHERE id=%s", (user_id,))
    user = cursor.fetchone()

    if user:
        token = generate_token()
        send_verification_email_function(user[0], token)
        cursor.execute("UPDATE users SET verification_token=%s WHERE id=%s", (token, user_id))
        conn.commit()
        flash('Verification email sent. Please check your inbox.', 'success')
    else:
        flash('User not found.', 'danger')

    cursor.close()
    conn.close()
    return redirect(url_for('routes.dashboard'))
