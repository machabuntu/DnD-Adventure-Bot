#!/usr/bin/env python3
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import get_db
from bot import format_character_display

def test_character_query():
    """Тестируем запрос для получения данных персонажа"""
    db = get_db()
    
    if not db.connection or not db.connection.is_connected():
        db.connect()
    
    print("=== Проверяем наличие персонажей в базе ===")
    
    # Проверяем персонажей
    characters = db.execute_query("SELECT * FROM characters WHERE is_active = TRUE")
    
    if not characters:
        print("❌ Нет активных персонажей в базе данных")
        return
    
    print(f"✅ Найдено {len(characters)} активных персонажей:")
    for char in characters:
        print(f"  - ID: {char['id']}, User ID: {char['user_id']}, Name: {char['name']}")
    
    print("\n=== Тестируем запрос команды /character ===")
    
    # Берем первого персонажа для теста
    test_user_id = characters[0]['user_id']
    
    character_query = """
        SELECT c.*, r.name as race_name, o.name as origin_name, cl.name as class_name,
               cl.hit_die, cl.is_spellcaster, l.proficiency_bonus
        FROM characters c
        LEFT JOIN races r ON c.race_id = r.id
        LEFT JOIN origins o ON c.origin_id = o.id
        LEFT JOIN classes cl ON c.class_id = cl.id
        LEFT JOIN levels l ON c.level = l.level
        WHERE c.user_id = %s AND c.is_active = TRUE
    """
    
    character = db.execute_query(character_query, (test_user_id,))
    
    if not character:
        print(f"❌ Не найден персонаж для user_id {test_user_id}")
        return
    
    print(f"✅ Найден персонаж: {character[0]['name']}")
    print(f"   Race: {character[0]['race_name']}")
    print(f"   Origin: {character[0]['origin_name']}")
    print(f"   Class: {character[0]['class_name']}")
    
    print("\n=== Тестируем форматирование ===")
    try:
        char_info = format_character_display(character[0], db)
        print("✅ Форматирование прошло успешно")
        print("=== Результат форматирования ===")
        print(char_info)
    except Exception as e:
        print(f"❌ Ошибка форматирования: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_character_query()
