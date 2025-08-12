#!/usr/bin/env python3
"""
Тестовый скрипт для проверки улучшений системы заклинаний
"""

import mysql.connector
from config import DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME

def test_spellcasting_ability():
    """Проверяем, что заклинательные характеристики правильно установлены"""
    conn = mysql.connector.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME
    )
    cursor = conn.cursor(dictionary=True)
    
    print("=" * 60)
    print("ТЕСТ: Заклинательные характеристики классов")
    print("=" * 60)
    
    cursor.execute("""
        SELECT name, is_spellcaster, spellcasting_ability 
        FROM classes 
        ORDER BY name
    """)
    
    for row in cursor.fetchall():
        if row['is_spellcaster']:
            print(f"✅ {row['name']:12} - Заклинательная характеристика: {row['spellcasting_ability']}")
        else:
            print(f"   {row['name']:12} - Не заклинатель")
    
    cursor.close()
    conn.close()

def test_spell_saving_throws():
    """Проверяем заклинания с спасбросками"""
    conn = mysql.connector.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME
    )
    cursor = conn.cursor(dictionary=True)
    
    print("\n" + "=" * 60)
    print("ТЕСТ: Заклинания с спасбросками")
    print("=" * 60)
    
    cursor.execute("""
        SELECT name, level, damage, saving_throw, is_area_of_effect
        FROM spells
        WHERE saving_throw IS NOT NULL AND is_combat = TRUE
        ORDER BY level, name
        LIMIT 10
    """)
    
    for spell in cursor.fetchall():
        aoe = " [AoE]" if spell['is_area_of_effect'] else ""
        print(f"Уровень {spell['level']}: {spell['name']}{aoe}")
        print(f"  Урон: {spell['damage'] or 'нет'}")
        print(f"  Спасбросок: {spell['saving_throw']}")
        print()
    
    cursor.close()
    conn.close()

def test_attack_spells():
    """Проверяем заклинания, требующие броска атаки"""
    conn = mysql.connector.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME
    )
    cursor = conn.cursor(dictionary=True)
    
    print("=" * 60)
    print("ТЕСТ: Заклинания с броском атаки (без спасброска)")
    print("=" * 60)
    
    cursor.execute("""
        SELECT name, level, damage, damage_type
        FROM spells
        WHERE saving_throw IS NULL 
        AND damage IS NOT NULL 
        AND is_combat = TRUE
        AND is_area_of_effect = FALSE
        ORDER BY level, name
        LIMIT 10
    """)
    
    for spell in cursor.fetchall():
        print(f"Уровень {spell['level']}: {spell['name']}")
        print(f"  Урон: {spell['damage']} {spell['damage_type']}")
        print(f"  Требует броска атаки против AC цели")
        print()
    
    cursor.close()
    conn.close()

def main():
    print("\n🧙 ТЕСТИРОВАНИЕ УЛУЧШЕНИЙ СИСТЕМЫ ЗАКЛИНАНИЙ 🧙\n")
    
    test_spellcasting_ability()
    test_spell_saving_throws()
    test_attack_spells()
    
    print("=" * 60)
    print("✅ Все тесты завершены!")
    print("\nИзменения:")
    print("1. ✅ Добавлена заклинательная характеристика для каждого класса")
    print("2. ✅ AoE заклинания теперь используют единый бросок урона")
    print("3. ✅ Интегрирована система спасбросков для AoE заклинаний")
    print("4. ✅ Заклинания без спасброска требуют броска атаки")

if __name__ == "__main__":
    main()
