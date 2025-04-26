# mysql_connect.py
#───────────────────────────────────────────────────────────────────────────────────────────────────────────────────
# Shared Imports
import os
from app.mysql_config import Config  # Import Config class to get DB credentials
#───────────────────────────────────────────────────────────────────────────────────────────────────────────────────
# MySQL Imports
import mysql.connector
from mysql.connector import Error as MySQLError
#───────────────────────────────────────────────────────────────────────────────────────────────────────────────────
# PostgreSQL Imports
import psycopg2
from psycopg2 import OperationalError as PostgresError
#───────────────────────────────────────────────────────────────────────────────────────────────────────────────────
# Legacy/Generic MySQL Connection Function
def create_connection():  # connected to login
    if Config.USE_DB == 'postgres':
        return create_postgres_connection()
    return create_mysql_connection()
#───────────────────────────────────────────────────────────────────────────────────────────────────────────────────
# Named MySQL Connection (Same functionality, more explicit)
def create_mysql_connection():
    try:
        connection = mysql.connector.connect(
            host=Config.MYSQL_HOST,
            user=Config.MYSQL_USER,
            password=Config.MYSQL_PASSWORD,
            database=Config.MYSQL_DB,
            port=Config.MYSQL_PORT
        )
        if connection.is_connected():
            print("Connected to MySQL")
            return connection
    except MySQLError as e:
        print(f"MySQL Error: {e}")
    return None

#───────────────────────────────────────────────────────────────────────────────────────────────────────────────────
# Named PostgreSQL Connection (for production)
def create_postgres_connection():
    try:
        connection = psycopg2.connect(
            host=Config.PG_HOST,
            port=Config.PG_PORT,
            user=Config.PG_USER,
            password=Config.PG_PASSWORD,
            dbname=Config.PG_DB
        )
        print("Connected to PostgreSQL")
        return connection
    except PostgresError as e:
        print(f"PostgreSQL Error: {e}")
    return None

#───────────────────────────────────────────────────────────────────────────────────────────────────────────────────
# Unified Dynamic Connection Function
def create_dynamic_connection():
    if Config.USE_DB == 'postgres':
        return create_postgres_connection()
    else:
        return create_mysql_connection()

#───────────────────────────────────────────────────────────────────────────────────────────────────────────────────
# Test connections when running this file directly
if __name__ == "__main__":
    print("Testing Legacy Connection:")
    create_connection()

    print("Testing Explicit MySQL Connection:")
    create_mysql_connection()

    print("Testing Dynamic (Auto-Switching) Connection:")
    create_dynamic_connection()
#───────────────────────────────────────────────────────────────────────────────────────────────────────────────────
