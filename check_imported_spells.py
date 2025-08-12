#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import mysql.connector
from config import DB_HOST, DB_USER, DB_PASSWORD, DB_NAME

conn = mysql.connector.connect(
    host=DB_HOST, 
    user=DB_USER, 
    password=DB_PASSWORD, 
    database=DB_NAME, 
    charset='utf8mb4'
)
cursor = conn.cursor()

# Проверяем количество заклинаний
cursor.execute('SELECT COUNT(*) FROM spells WHERE level = 1')
print(f'Заклинаний 1-го уровня: {cursor.fetchone()[0]}')

cursor.execute('SELECT COUNT(*) FROM spells WHERE level = 0')
print(f'Заговоров (0-й уровень): {cursor.fetchone()[0]}')

# Примеры заклинаний 1-го уровня
cursor.execute('SELECT name, damage, damage_type, scaling_type FROM spells WHERE level = 1 LIMIT 10')
print('\nПримеры заклинаний 1-го уровня:')
for row in cursor.fetchall():
    print(f'  - {row[0]}: урон {row[1]} ({row[2]}), скалирование: {row[3]}')

# Проверяем скалирование
cursor.execute("""
    SELECT s.name, ss.slot_level, ss.damage_bonus 
    FROM spells s 
    JOIN spell_slot_scaling ss ON s.id = ss.spell_id 
    WHERE s.name = 'Волшебная стрела' 
    ORDER BY ss.slot_level 
    LIMIT 5
""")
print('\nСкалирование заклинания "Волшебная стрела":')
for row in cursor.fetchall():
    print(f'  Слот {row[1]}: бонус урона {row[2]}')

cursor.close()
conn.close()
