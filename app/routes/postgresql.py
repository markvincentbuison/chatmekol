from psycopg2 import connect
from psycopg2.extras import RealDictCursor
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def get_db_connection():
    try:
        database_url = os.getenv("DATABASE_URL")
        print(f"Trying to connect with DATABASE_URL: {database_url}")  # Log the URL
        if database_url:
            return connect(
                dsn=database_url,
                cursor_factory=RealDictCursor
            )
        else:
            raise ValueError("DATABASE_URL not set")
    except Exception as e:
        print("Failed with DATABASE_URL, falling back to individual variables. Error:", e)
        try:
            print(f"Trying to connect with individual DB variables: Host={os.getenv('DB_HOST')}")  # Log individual vars
            return connect(
                host=os.getenv("DB_HOST"),
                port=os.getenv("DB_PORT"),
                dbname=os.getenv("DB_NAME"),
                user=os.getenv("DB_USER"),
                password=os.getenv("DB_PASSWORD"),
                cursor_factory=RealDictCursor
            )
        except Exception as e2:
            print("PostgreSQL Connection Error:", e2)
            return None
