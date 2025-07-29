#!/usr/bin/env python3
"""
Скрипт для проверки загруженных данных
"""

from database import get_db

def check_data():
    db = get_db()
    
    if not db.connect():
        print("Ошибка подключения к базе данных")
        return False
    
    try:
        # Проверяем происхождения
        origins = db.execute_query("SELECT name, stat_bonuses, skills, starting_money FROM origins LIMIT 3")
        print("ПРОИСХОЖДЕНИЯ:")
        for origin in origins:
            print(f"- {origin['name']}: {origin['stat_bonuses']}")
            print(f"  Навыки: {origin['skills']}")
            print(f"  Стартовые деньги: {origin['starting_money']}")
            print()
        
        # Проверяем оружие
        weapons = db.execute_query("SELECT name, damage, damage_type, technique FROM weapons WHERE weapon_type='Простое' LIMIT 5")
        print("ПРОСТОЕ ОРУЖИЕ:")
        for weapon in weapons:
            print(f"- {weapon['name']}: {weapon['damage']} {weapon['damage_type']}, прием: {weapon['technique']}")
        
        print()
        
        # Проверяем воинское оружие с приемами
        martial_weapons = db.execute_query("SELECT name, damage, damage_type, technique FROM weapons WHERE weapon_type='Воинское' LIMIT 5")
        print("ВОИНСКОЕ ОРУЖИЕ:")
        for weapon in martial_weapons:
            print(f"- {weapon['name']}: {weapon['damage']} {weapon['damage_type']}, прием: {weapon['technique']}")
            
    except Exception as e:
        print(f"Ошибка при проверке данных: {e}")
        return False
    finally:
        db.disconnect()
    
    return True

if __name__ == "__main__":
    check_data()
