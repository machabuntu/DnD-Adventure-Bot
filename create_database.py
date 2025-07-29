import mysql.connector
from mysql.connector import Error
from config import DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME

def create_database():
    """Create the dnd_bot database if it doesn't exist"""
    try:
        # Connect to MySQL server without specifying database
        connection = mysql.connector.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            charset='utf8mb4',
            collation='utf8mb4_unicode_ci'
        )
        
        cursor = connection.cursor()
        
        # Create database if it doesn't exist
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {DB_NAME} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
        print(f"Database '{DB_NAME}' created successfully or already exists")
        
        cursor.close()
        connection.close()
        
        return True
        
    except Error as e:
        print(f"Error creating database: {e}")
        return False

if __name__ == "__main__":
    if create_database():
        print("Database creation successful")
        
        # Now initialize the database schema
        from database import db
        if db.connect():
            if db.init_database():
                print("Database schema initialized successfully")
            else:
                print("Failed to initialize database schema")
            db.disconnect()
    else:
        print("Failed to create database")
