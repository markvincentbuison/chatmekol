import os
import psycopg2
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# PostgreSQL config
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT", 5432)
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASS = os.getenv("DB_PASS")

def get_db_connection():
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASS,
            sslmode="require"  # optional depende kung HTTPS prod ka
        )
        return conn
    except Exception as e:
        print("[DB ERROR]", e)
        raise

def release_db_connection(conn):
    if conn:
        conn.close()
