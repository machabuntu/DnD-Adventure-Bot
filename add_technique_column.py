#!/usr/bin/env python3
"""
Скрипт для добавления столбца technique к таблице weapons
"""

from database import get_db

def add_technique_column():
    db = get_db()
    
    if not db.connect():
        print("Ошибка подключения к базе данных")
        return False
    
    try:
        # Добавляем столбец technique
        db.execute_query("ALTER TABLE weapons ADD COLUMN technique VARCHAR(50) DEFAULT 'Нет'")
        print("Столбец technique успешно добавлен к таблице weapons")
        
        # Проверяем структуру таблицы
        result = db.execute_query("DESCRIBE weapons")
        print("\nОбновленная структура таблицы weapons:")
        for field in result:
            print(f"- {field['Field']}: {field['Type']}")
            
    except Exception as e:
        print(f"Ошибка при добавлении столбца: {e}")
        return False
    finally:
        db.disconnect()
    
    return True

if __name__ == "__main__":
    add_technique_column()
