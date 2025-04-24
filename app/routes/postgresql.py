# app/routes/postgresql.py

import psycopg2
from psycopg2.extras import RealDictCursor
import os

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST"),
        database=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        port=os.getenv("DB_PORT", 5432),
        cursor_factory=RealDictCursor
    )
