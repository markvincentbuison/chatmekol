import psycopg2
from psycopg2.extras import RealDictCursor
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def get_db_connection():
    try:
        return psycopg2.connect(
            dsn=os.getenv("DATABASE_URL"),  # FULL connection string
            cursor_factory=RealDictCursor
        )
    except Exception as e:
        print("PostgreSQL Connection Error:", e)
        return None
