import os
import psycopg2
from psycopg2 import pool
from dotenv import load_dotenv
import time

# Load environment variables
load_dotenv()

# PostgreSQL config
DB_HOST = os.getenv("DB_HOST", "dpg-d00ihffgi27c73bb4afg-a.virginia-postgres.render.com")
DB_PORT = os.getenv("DB_PORT", 5432)
DB_NAME = os.getenv("DB_NAME", "downloadable_app")
DB_USER = os.getenv("DB_USER", "root")
DB_PASS = os.getenv("DB_PASS", "rVIIDKOozMHH8LPqHT0dC3EfPxwFN2nP")

# Google OAuth config
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "37646923386-sq0a7ov7v6ukjo0kisv0mlnt96gv3gpc.apps.googleusercontent.com")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "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")
GOOGLE_AUTHORIZATION_URL = os.getenv("GOOGLE_AUTHORIZATION_URL", "https://accounts.google.com/o/oauth2/auth")
GOOGLE_TOKEN_URL = os.getenv("GOOGLE_TOKEN_URL", "https://oauth2.googleapis.com/token")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "https://chatmekol.onrender.com/callback")

# Global connection pool
db_pool = None

# Initialize the connection pool
def init_db_pool():
    global db_pool
    try:
        db_pool = psycopg2.pool.SimpleConnectionPool(
            1, 20,  # Minimum 1 connection, maximum 20 connections
            host=DB_HOST,
            port=DB_PORT,
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASS,
            sslmode="require",
            connect_timeout=10  # Set connection timeout to 10 seconds
        )
        print("Connection pool created successfully.")
    except Exception as e:
        print("[DB ERROR] Failed to create connection pool:", e)
        raise

# Get a database connection from the pool
def get_db_connection():
    try:
        if db_pool is None:
            init_db_pool()  # Initialize pool if not already done
        conn = db_pool.getconn()  # Get connection from the pool
        return conn
    except Exception as e:
        print("[DB ERROR] Error getting connection from pool:", e)
        raise

# Release the database connection back to the pool
def release_db_connection(conn):
    try:
        if db_pool:
            db_pool.putconn(conn)  # Return connection to the pool
    except Exception as e:
        print("[DB ERROR] Error releasing connection back to pool:", e)
        raise

# Initialize database and create tables if they do not exist
def init_db():
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Set a longer statement timeout for creating tables or long-running queries
    cur.execute("SET statement_timeout = 30000;")  # Timeout in milliseconds (30 seconds)
    
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        username VARCHAR(50) UNIQUE,
        password TEXT,
        email_address VARCHAR(255) UNIQUE NOT NULL,
        verification_token TEXT,
        verification_token_expiry TIMESTAMP,
        is_verified BOOLEAN DEFAULT FALSE,
        google_id TEXT,
        reset_token TEXT,
        reset_token_expiry TIMESTAMP,
        is_admin BOOLEAN DEFAULT FALSE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)
    conn.commit()
    release_db_connection(conn)  # Release connection back to pool

# Handle database reconnection in case of a disconnect
def get_db_connection_with_retry():
    try:
        conn = get_db_connection()
        return conn
    except psycopg2.OperationalError as e:
        print(f"[DB ERROR] Operational Error: {e}")
        time.sleep(5)  # Wait for 5 seconds before retrying
        return get_db_connection_with_retry()  # Retry connection
    except Exception as e:
        print("[DB ERROR]", e)
        raise

# Example usage:
if __name__ == "__main__":
    init_db()  # Initialize the database and create tables if they don't exist
