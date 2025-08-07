#!/usr/bin/env python3
"""Script to check and update database structure"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import get_db

def check_and_update_structure():
    db = get_db()
    if not db.connection or not db.connection.is_connected():
        db.connect()
    
    print("Checking current database structure...")
    
    # Check characters table structure
    print("\n=== Characters table structure ===")
    try:
        result = db.execute_query("DESCRIBE characters")
        for row in result:
            print(f"{row['Field']}: {row['Type']} ({row['Null']}, {row['Key']}, {row['Default']})")
    except Exception as e:
        print(f"Error checking characters table: {e}")
    
    # Check if armor_class column exists
    print("\n=== Checking for armor_class column ===")
    try:
        columns_result = db.execute_query("SHOW COLUMNS FROM characters LIKE 'armor_class'")
        if not columns_result:
            print("armor_class column does not exist. Adding it...")
            db.execute_query("ALTER TABLE characters ADD COLUMN armor_class INT DEFAULT 10")
            print("✅ Added armor_class column")
        else:
            print("✅ armor_class column already exists")
    except Exception as e:
        print(f"❌ Error checking/adding armor_class column: {e}")
    
    # Check if enemy_attacks table exists
    print("\n=== Checking for enemy_attacks table ===")
    try:
        tables_result = db.execute_query("SHOW TABLES LIKE 'enemy_attacks'")
        if not tables_result:
            print("enemy_attacks table does not exist. Creating it...")
            create_table_sql = """
            CREATE TABLE enemy_attacks (
                id INT PRIMARY KEY AUTO_INCREMENT,
                enemy_id INT NOT NULL,
                name VARCHAR(100) NOT NULL,
                damage VARCHAR(20) NOT NULL,
                bonus INT NOT NULL DEFAULT 0,
                FOREIGN KEY (enemy_id) REFERENCES enemies(id) ON DELETE CASCADE
            )
            """
            db.execute_query(create_table_sql)
            print("✅ Created enemy_attacks table")
        else:
            print("✅ enemy_attacks table already exists")
    except Exception as e:
        print(f"❌ Error checking/creating enemy_attacks table: {e}")
    
    # Check enemies table structure
    print("\n=== Enemies table structure ===")
    try:
        result = db.execute_query("DESCRIBE enemies")
        for row in result:
            print(f"{row['Field']}: {row['Type']} ({row['Null']}, {row['Key']}, {row['Default']})")
    except Exception as e:
        print(f"Error checking enemies table: {e}")
    
    print("\n=== Database structure check complete ===")

if __name__ == "__main__":
    check_and_update_structure()
