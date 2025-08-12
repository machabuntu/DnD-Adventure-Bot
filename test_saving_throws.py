#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Тестовый скрипт для проверки системы спасбросков.
"""

import mysql.connector
from config import DB_HOST, DB_USER, DB_PASSWORD, DB_NAME
from saving_throws import saving_throw_manager

def create_test_data():
    """Создает тестовые данные для проверки."""
    conn = mysql.connector.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        charset='utf8mb4'
    )
    cursor = conn.cursor()
    
    # Создаем тестового персонажа-волшебника
    cursor.execute("""
        INSERT INTO characters (user_id, name, class_id, level, 
                               strength, dexterity, constitution, 
                               intelligence, wisdom, charisma, 
                               max_hp, current_hp, is_active)
        SELECT 123456789, 'Тестовый Маг', id, 5,
               10, 14, 12, 18, 13, 8, 30, 30, TRUE
        FROM classes WHERE name = 'Волшебник'
        ON DUPLICATE KEY UPDATE name = VALUES(name)
    """)
    
    char_id = cursor.lastrowid
    
    # Создаем тестовое приключение
    cursor.execute("""
        INSERT INTO adventures (chat_id, status)
        VALUES (123456789, 'combat')
    """)
    
    adventure_id = cursor.lastrowid
    
    # Создаем тестового врага
    cursor.execute("""
        INSERT INTO enemies (adventure_id, name, max_hp, current_hp, armor_class,
                           strength, dexterity, constitution, 
                           intelligence, wisdom, charisma, current_hp, max_hp)
        VALUES (%s, 'Тестовый Гоблин', 20, 20, 13, 
                8, 14, 10, 10, 8, 8, 20, 20)
    """, (adventure_id,))
    
    enemy_id = cursor.lastrowid
    
    conn.commit()
    cursor.close()
    conn.close()
    
    return char_id, enemy_id

def test_save_dc_calculation():
    """Тестирует вычисление DC спасброска."""
    print("\n=== Тест вычисления DC спасброска ===")
    
    # Создаем тестовые данные
    char_id, enemy_id = create_test_data()
    
    # Тестируем для волшебника 5 уровня с Интеллектом 18
    dc = saving_throw_manager.calculate_spell_save_dc(char_id)
    
    # DC = 8 + бонус мастерства (3 для 5 уровня) + модификатор Интеллекта (4 для 18 Int)
    expected_dc = 8 + 3 + 4  # = 15
    
    print(f"Персонаж: Волшебник 5 уровня (Int 18)")
    print(f"Ожидаемый DC: {expected_dc}")
    print(f"Вычисленный DC: {dc}")
    print(f"Тест {'✅ ПРОЙДЕН' if dc == expected_dc else '❌ ПРОВАЛЕН'}")
    
    return char_id, enemy_id

def test_enemy_saving_throws(char_id, enemy_id):
    """Тестирует спасброски врага."""
    print("\n=== Тест спасбросков врага ===")
    
    # Получаем DC заклинателя
    dc = saving_throw_manager.calculate_spell_save_dc(char_id)
    
    # Тест спасброска Ловкости (гоблин имеет Ловкость 14, модификатор +2)
    print(f"\nСпасбросок Ловкости против DC {dc}:")
    success, result_text = saving_throw_manager.make_saving_throw(
        enemy_id, 'enemy', 'Ловкость', dc
    )
    print(result_text)
    
    # Тест спасброска Мудрости (гоблин имеет Мудрость 8, модификатор -1)
    print(f"\nСпасбросок Мудрости против DC {dc}:")
    success, result_text = saving_throw_manager.make_saving_throw(
        enemy_id, 'enemy', 'Мудрость', dc
    )
    print(result_text)
    
    # Тест спасброска Телосложения (гоблин имеет Телосложение 10, модификатор +0)
    print(f"\nСпасбросок Телосложения против DC {dc}:")
    success, result_text = saving_throw_manager.make_saving_throw(
        enemy_id, 'enemy', 'Телосложение', dc
    )
    print(result_text)

def test_spell_saving_throw():
    """Тестирует спасбросок от конкретного заклинания."""
    print("\n=== Тест спасброска от заклинания ===")
    
    conn = mysql.connector.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        charset='utf8mb4'
    )
    cursor = conn.cursor()
    
    # Получаем ID заклинания "Волна грома" (требует спасбросок Телосложения)
    cursor.execute("SELECT id FROM spells WHERE name = 'Волна грома' AND level = 1")
    result = cursor.fetchone()
    
    if result:
        spell_id = result[0]
        char_id, enemy_id = create_test_data()
        
        print("Заклинание: Волна грома (спасбросок Телосложения)")
        success, result_text = saving_throw_manager.process_spell_saving_throw(
            spell_id, char_id, enemy_id, 'enemy'
        )
        print(result_text)
        print(f"Результат: {'Успех (половина урона)' if success else 'Провал (полный урон)'}")
    else:
        print("Заклинание 'Волна грома' не найдено в базе данных")
    
    cursor.close()
    conn.close()

def test_aoe_saving_throws():
    """Тестирует спасброски для AoE заклинания."""
    print("\n=== Тест AoE спасбросков ===")
    
    conn = mysql.connector.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        charset='utf8mb4'
    )
    cursor = conn.cursor()
    
    # Создаем персонажа и несколько врагов
    char_id, enemy1_id = create_test_data()
    
    # Создаем дополнительных врагов
    cursor.execute("SELECT adventure_id FROM enemies WHERE id = %s", (enemy1_id,))
    adventure_id = cursor.fetchone()[0]
    
    cursor.execute("""
        INSERT INTO enemies (adventure_id, name, max_hp, current_hp, armor_class,
                           strength, dexterity, constitution, 
                           intelligence, wisdom, charisma, current_hp, max_hp)
        VALUES (%s, 'Орк', 30, 30, 11, 
                16, 12, 16, 7, 11, 10, 30, 30)
    """, (adventure_id,))
    enemy2_id = cursor.lastrowid
    
    cursor.execute("""
        INSERT INTO enemies (adventure_id, name, max_hp, current_hp, armor_class,
                           strength, dexterity, constitution, 
                           intelligence, wisdom, charisma, current_hp, max_hp)
        VALUES (%s, 'Кобольд', 10, 10, 12, 
                7, 15, 9, 8, 7, 8, 10, 10)
    """, (adventure_id,))
    enemy3_id = cursor.lastrowid
    
    conn.commit()
    
    # Получаем ID AoE заклинания
    cursor.execute("SELECT id FROM spells WHERE name = 'Огненные ладони' AND level = 1")
    result = cursor.fetchone()
    
    if result:
        spell_id = result[0]
        
        print("Заклинание: Огненные ладони (AoE, спасбросок Ловкости)")
        print(f"DC спасброска: {saving_throw_manager.calculate_spell_save_dc(char_id)}")
        print()
        
        # Тестируем спасброски для всех врагов
        targets = [
            {'id': enemy1_id, 'type': 'enemy'},
            {'id': enemy2_id, 'type': 'enemy'},
            {'id': enemy3_id, 'type': 'enemy'}
        ]
        
        results = saving_throw_manager.process_aoe_saving_throws(
            spell_id, char_id, targets
        )
        
        for target in targets:
            enemy_id = target['id']
            cursor.execute("SELECT name FROM enemies WHERE id = %s", (enemy_id,))
            enemy_name = cursor.fetchone()[0]
            
            success, result_text = results[enemy_id]
            print(f"{enemy_name}:")
            print(f"  {result_text}")
            print(f"  Урон: {'половина' if success else 'полный'}")
            print()
    else:
        print("Заклинание 'Огненные ладони' не найдено в базе данных")
    
    cursor.close()
    conn.close()

def cleanup_test_data():
    """Удаляет тестовые данные."""
    conn = mysql.connector.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        charset='utf8mb4'
    )
    cursor = conn.cursor()
    
    # Удаляем тестовые данные
    cursor.execute("DELETE FROM characters WHERE name = 'Тестовый Маг'")
    cursor.execute("DELETE FROM adventures WHERE chat_id = 123456789")
    
    conn.commit()
    cursor.close()
    conn.close()
    
    print("\n✅ Тестовые данные удалены")

def main():
    """Основная функция тестирования."""
    print("=" * 60)
    print("ТЕСТИРОВАНИЕ СИСТЕМЫ СПАСБРОСКОВ")
    print("=" * 60)
    
    try:
        # Тест 1: Вычисление DC
        char_id, enemy_id = test_save_dc_calculation()
        
        # Тест 2: Спасброски врага
        test_enemy_saving_throws(char_id, enemy_id)
        
        # Тест 3: Спасбросок от заклинания
        test_spell_saving_throw()
        
        # Тест 4: AoE спасброски
        test_aoe_saving_throws()
        
        print("\n" + "=" * 60)
        print("✅ ВСЕ ТЕСТЫ ЗАВЕРШЕНЫ")
        print("=" * 60)
        
    finally:
        # Очистка тестовых данных
        cleanup_test_data()

if __name__ == "__main__":
    main()
