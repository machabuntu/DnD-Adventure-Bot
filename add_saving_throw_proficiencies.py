#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Скрипт для добавления информации о владении спасбросками в таблицу классов.
"""

import mysql.connector
import json
import logging
from config import DB_HOST, DB_USER, DB_PASSWORD, DB_NAME

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('add_saving_throws.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def connect_to_db():
    """Подключение к базе данных."""
    return mysql.connector.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        charset='utf8mb4',
        collation='utf8mb4_unicode_ci'
    )

def add_saving_throw_column(cursor):
    """Добавляет колонку для хранения информации о владении спасбросками."""
    try:
        # Проверяем, существует ли колонка
        cursor.execute("""
            SELECT COUNT(*) 
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_SCHEMA = %s 
            AND TABLE_NAME = 'classes' 
            AND COLUMN_NAME = 'saving_throw_proficiencies'
        """, (DB_NAME,))
        
        if cursor.fetchone()[0] == 0:
            cursor.execute("""
                ALTER TABLE classes 
                ADD COLUMN saving_throw_proficiencies TEXT 
                COMMENT 'JSON массив с названиями характеристик для спасбросков'
            """)
            logger.info("Добавлена колонка saving_throw_proficiencies в таблицу classes")
        else:
            logger.info("Колонка saving_throw_proficiencies уже существует")
            
    except mysql.connector.Error as e:
        logger.error(f"Ошибка при добавлении колонки: {e}")
        raise

def update_saving_throw_proficiencies(cursor):
    """Обновляет информацию о владении спасбросками для каждого класса."""
    
    # Данные о владении спасбросками для каждого класса
    saving_throws_data = {
        'Бард': ['Ловкость', 'Харизма'],
        'Варвар': ['Сила', 'Телосложение'],
        'Воин': ['Сила', 'Телосложение'],
        'Волшебник': ['Интеллект', 'Мудрость'],
        'Друид': ['Интеллект', 'Мудрость'],
        'Жрец': ['Мудрость', 'Харизма'],
        'Колдун': ['Мудрость', 'Харизма'],
        'Монах': ['Сила', 'Ловкость'],
        'Паладин': ['Мудрость', 'Харизма'],
        'Плут': ['Ловкость', 'Интеллект'],
        'Следопыт': ['Сила', 'Ловкость'],
        'Чародей': ['Телосложение', 'Харизма']
    }
    
    for class_name, proficiencies in saving_throws_data.items():
        proficiencies_json = json.dumps(proficiencies, ensure_ascii=False)
        
        cursor.execute("""
            UPDATE classes 
            SET saving_throw_proficiencies = %s 
            WHERE name = %s
        """, (proficiencies_json, class_name))
        
        if cursor.rowcount > 0:
            logger.info(f"Обновлен класс {class_name}: спасброски {', '.join(proficiencies)}")
        else:
            logger.warning(f"Класс {class_name} не найден в базе данных")

def verify_updates(cursor):
    """Проверяет результаты обновления."""
    cursor.execute("""
        SELECT name, saving_throw_proficiencies 
        FROM classes 
        WHERE saving_throw_proficiencies IS NOT NULL
        ORDER BY name
    """)
    
    results = cursor.fetchall()
    
    logger.info("\nРезультаты обновления:")
    for name, proficiencies_json in results:
        if proficiencies_json:
            proficiencies = json.loads(proficiencies_json)
            logger.info(f"  {name}: {', '.join(proficiencies)}")

def main():
    """Основная функция."""
    conn = None
    cursor = None
    
    try:
        logger.info("Подключение к базе данных...")
        conn = connect_to_db()
        cursor = conn.cursor()
        
        logger.info("Добавление колонки для спасбросков...")
        add_saving_throw_column(cursor)
        conn.commit()
        
        logger.info("Обновление информации о владении спасбросками...")
        update_saving_throw_proficiencies(cursor)
        conn.commit()
        
        logger.info("Проверка результатов...")
        verify_updates(cursor)
        
        logger.info("\n✅ Информация о владении спасбросками успешно добавлена!")
        
    except Exception as e:
        logger.error(f"Произошла ошибка: {e}")
        if conn:
            conn.rollback()
        raise
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

if __name__ == "__main__":
    main()
