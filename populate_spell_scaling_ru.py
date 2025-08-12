#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Скрипт для заполнения данных об усилении заклинаний на русском языке.
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
        logging.FileHandler('spell_scaling_populate_ru.log', encoding='utf-8'),
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

def populate_cantrip_scaling_data(cursor):
    """Заполняет данные об усилении заговоров."""
    
    # Получаем ID заговоров
    cursor.execute("SELECT id, name FROM spells WHERE level = 0")
    cantrips = {name: id for id, name in cursor.fetchall()}
    
    cantrip_scaling_data = []
    
    # Огненный снаряд (Fire Bolt) - урон увеличивается
    if 'Огненный снаряд' in cantrips:
        spell_id = cantrips['Огненный снаряд']
        cantrip_scaling_data.extend([
            (spell_id, 1, '1d10', None, None),
            (spell_id, 5, '2d10', None, None),
            (spell_id, 11, '3d10', None, None),
            (spell_id, 17, '4d10', None, None)
        ])
    
    # Сглаз (Eldritch Blast) - увеличивается количество лучей
    if 'Сглаз' in cantrips:
        spell_id = cantrips['Сглаз']
        cantrip_scaling_data.extend([
            (spell_id, 1, '1d10', 1, None),
            (spell_id, 5, '1d10', 2, json.dumps({'description': '2 луча'})),
            (spell_id, 11, '1d10', 3, json.dumps({'description': '3 луча'})),
            (spell_id, 17, '1d10', 4, json.dumps({'description': '4 луча'}))
        ])
    
    # Ледяной луч (Ray of Frost) - урон увеличивается
    if 'Ледяной луч' in cantrips:
        spell_id = cantrips['Ледяной луч']
        cantrip_scaling_data.extend([
            (spell_id, 1, '1d8', None, json.dumps({'slow_effect': '10 футов'})),
            (spell_id, 5, '2d8', None, json.dumps({'slow_effect': '10 футов'})),
            (spell_id, 11, '3d8', None, json.dumps({'slow_effect': '10 футов'})),
            (spell_id, 17, '4d8', None, json.dumps({'slow_effect': '10 футов'}))
        ])
    
    # Священное пламя (Sacred Flame) - урон увеличивается
    if 'Священное пламя' in cantrips:
        spell_id = cantrips['Священное пламя']
        cantrip_scaling_data.extend([
            (spell_id, 1, '1d8', None, None),
            (spell_id, 5, '2d8', None, None),
            (spell_id, 11, '3d8', None, None),
            (spell_id, 17, '4d8', None, None)
        ])
    
    # Брызги яда (Poison Spray) - урон увеличивается
    if 'Брызги яда' in cantrips:
        spell_id = cantrips['Брызги яда']
        cantrip_scaling_data.extend([
            (spell_id, 1, '1d12', None, None),
            (spell_id, 5, '2d12', None, None),
            (spell_id, 11, '3d12', None, None),
            (spell_id, 17, '4d12', None, None)
        ])
    
    # Порыв грома (Thunderclap) - урон увеличивается
    if 'Порыв грома' in cantrips:
        spell_id = cantrips['Порыв грома']
        cantrip_scaling_data.extend([
            (spell_id, 1, '1d6', None, None),
            (spell_id, 5, '2d6', None, None),
            (spell_id, 11, '3d6', None, None),
            (spell_id, 17, '4d6', None, None)
        ])
    
    # Вставляем данные
    if cantrip_scaling_data:
        cursor.executemany("""
            INSERT INTO cantrip_scaling (spell_id, character_level, damage_dice, num_beams, other_effects)
            VALUES (%s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE 
                damage_dice = VALUES(damage_dice),
                num_beams = VALUES(num_beams),
                other_effects = VALUES(other_effects)
        """, cantrip_scaling_data)
        logger.info(f"Добавлено {len(cantrip_scaling_data)} записей усиления заговоров")
    else:
        logger.warning("Нет данных для добавления усиления заговоров")

def populate_spell_slot_scaling_data(cursor):
    """Заполняет данные об усилении заклинаний при использовании слотов высокого уровня."""
    
    # Получаем ID заклинаний
    cursor.execute("SELECT id, name, level FROM spells WHERE level > 0")
    spells = {name: (id, level) for id, name, level in cursor.fetchall()}
    
    slot_scaling_data = []
    
    # Магическая стрела (Magic Missile) - добавляет дополнительные снаряды
    if 'Магическая стрела' in spells:
        spell_id, base_level = spells['Магическая стрела']
        for slot_level in range(2, 10):  # Слоты 2-9 уровня
            additional_missiles = slot_level - base_level
            slot_scaling_data.append(
                (spell_id, slot_level, None, None, additional_missiles, 
                 json.dumps({'missiles': f'+{additional_missiles} снаряда'}))
            )
    
    # Исцеление ран (Cure Wounds) - увеличивает лечение
    if 'Исцеление ран' in spells:
        spell_id, base_level = spells['Исцеление ран']
        for slot_level in range(2, 10):
            slot_scaling_data.append(
                (spell_id, slot_level, f'+{slot_level - base_level}d8', None, None,
                 json.dumps({'healing': f'Дополнительное лечение {slot_level - base_level}d8'}))
            )
    
    # Жгучие руки (Burning Hands) - увеличивает урон
    if 'Жгучие руки' in spells:
        spell_id, base_level = spells['Жгучие руки']
        for slot_level in range(2, 10):
            slot_scaling_data.append(
                (spell_id, slot_level, f'+{slot_level - base_level}d6', None, None, None)
            )
    
    # Огненный шар (Fireball) - увеличивает урон (внимание: в базе он 2 уровня, но по правилам должен быть 3)
    if 'Огненный шар' in spells:
        spell_id, base_level = spells['Огненный шар']
        # Начинаем с уровня на 1 выше базового
        for slot_level in range(base_level + 1, 10):
            slot_scaling_data.append(
                (spell_id, slot_level, f'+{slot_level - base_level}d6', None, None, None)
            )
    
    # Молния (Lightning Bolt) - увеличивает урон
    if 'Молния' in spells:
        spell_id, base_level = spells['Молния']
        for slot_level in range(base_level + 1, 10):
            slot_scaling_data.append(
                (spell_id, slot_level, f'+{slot_level - base_level}d6', None, None, None)
            )
    
    # Удержание личности (Hold Person) - может воздействовать на дополнительные цели
    if 'Удержание личности' in spells:
        spell_id, base_level = spells['Удержание личности']
        for slot_level in range(base_level + 1, 10):
            slot_scaling_data.append(
                (spell_id, slot_level, None, None, slot_level - base_level,
                 json.dumps({'targets': f'+{slot_level - base_level} цели'}))
            )
    
    # Очарование личности (Charm Person) - может воздействовать на дополнительные цели
    if 'Очарование личности' in spells:
        spell_id, base_level = spells['Очарование личности']
        for slot_level in range(base_level + 1, 10):
            slot_scaling_data.append(
                (spell_id, slot_level, None, None, slot_level - base_level,
                 json.dumps({'targets': f'+{slot_level - base_level} цели'}))
            )
    
    # Сон (Sleep) - увеличивает количество HP затрагиваемых существ
    if 'Сон' in spells:
        spell_id, base_level = spells['Сон']
        for slot_level in range(2, 10):
            additional_hp = (slot_level - base_level) * 2  # +2d8 за уровень
            slot_scaling_data.append(
                (spell_id, slot_level, None, None, None,
                 json.dumps({'additional_hp': f'+{additional_hp}d8 HP'}))
            )
    
    # Вставляем данные
    if slot_scaling_data:
        cursor.executemany("""
            INSERT INTO spell_slot_scaling 
            (spell_id, slot_level, damage_bonus, duration_bonus, target_bonus, other_effects)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE 
                damage_bonus = VALUES(damage_bonus),
                duration_bonus = VALUES(duration_bonus),
                target_bonus = VALUES(target_bonus),
                other_effects = VALUES(other_effects)
        """, slot_scaling_data)
        logger.info(f"Добавлено {len(slot_scaling_data)} записей усиления заклинаний через слоты")
    else:
        logger.warning("Нет данных для добавления усиления заклинаний через слоты")

def update_spell_scaling_types(cursor):
    """Обновляет типы усиления в таблице spells."""
    
    # Обновляем заговоры с уроном
    cursor.execute("""
        UPDATE spells 
        SET scaling_type = 'cantrip_damage',
            base_scaling_info = '{"levels": [5, 11, 17], "description": "Урон увеличивается на указанных уровнях"}'
        WHERE level = 0 AND damage IS NOT NULL
    """)
    logger.info(f"Обновлены заговоры с уроном: {cursor.rowcount} записей")
    
    # Обновляем заклинания с усилением урона
    cursor.execute("""
        UPDATE spells 
        SET scaling_type = 'slot_damage',
            base_scaling_info = '{"per_slot": "Дополнительный урон за слот выше минимального"}'
        WHERE name IN ('Магическая стрела', 'Жгучие руки', 'Огненный шар', 'Молния', 
                       'Исцеление ран', 'Громовая волна', 'Огненная струя')
    """)
    logger.info(f"Обновлены заклинания с усилением урона: {cursor.rowcount} записей")
    
    # Обновляем заклинания с усилением целей
    cursor.execute("""
        UPDATE spells 
        SET scaling_type = 'slot_targets',
            base_scaling_info = '{"per_slot": "+1 цель за каждый слот выше минимального"}'
        WHERE name IN ('Удержание личности', 'Очарование личности')
    """)
    logger.info(f"Обновлены заклинания с усилением целей: {cursor.rowcount} записей")
    
    # Обновляем специальные заклинания
    cursor.execute("""
        UPDATE spells 
        SET scaling_type = 'slot_special',
            base_scaling_info = '{"type": "sleep_hp", "per_slot": "+2d8 HP за слот"}'
        WHERE name = 'Сон'
    """)
    logger.info(f"Обновлено заклинание Сон: {cursor.rowcount} записей")

def add_special_scaling_rules(cursor):
    """Добавляет специальные правила усиления."""
    
    # Получаем ID заклинаний
    cursor.execute("SELECT id, name FROM spells")
    spells = {name: id for id, name in cursor.fetchall()}
    
    rules_data = []
    
    # Правила для некоторых заклинаний
    if 'Магическая стрела' in spells:
        rules_data.append(
            (spells['Магическая стрела'], 'missiles_per_slot', '+1', 
             'Дополнительная стрела за каждый слот выше 1-го')
        )
    
    if 'Сон' in spells:
        rules_data.append(
            (spells['Сон'], 'hp_per_slot', '2d8',
             'Дополнительные 2d8 HP существ за каждый слот выше 1-го')
        )
    
    if 'Щит' in spells:
        rules_data.append(
            (spells['Щит'], 'no_scaling', 'none',
             'Заклинание не усиливается от слотов высокого уровня')
        )
    
    if rules_data:
        cursor.executemany("""
            INSERT INTO spell_scaling_rules (spell_id, rule_type, rule_value, rule_description)
            VALUES (%s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                rule_value = VALUES(rule_value),
                rule_description = VALUES(rule_description)
        """, rules_data)
        logger.info(f"Добавлено {len(rules_data)} специальных правил усиления")

def verify_updates(cursor):
    """Проверяет успешность обновлений."""
    
    cursor.execute("SELECT COUNT(*) FROM cantrip_scaling")
    cantrip_count = cursor.fetchone()[0]
    logger.info(f"Записей в cantrip_scaling: {cantrip_count}")
    
    cursor.execute("SELECT COUNT(*) FROM spell_slot_scaling")
    slot_count = cursor.fetchone()[0]
    logger.info(f"Записей в spell_slot_scaling: {slot_count}")
    
    cursor.execute("SELECT COUNT(*) FROM spell_scaling_rules")
    rules_count = cursor.fetchone()[0]
    logger.info(f"Записей в spell_scaling_rules: {rules_count}")
    
    cursor.execute("SELECT COUNT(*) FROM spells WHERE scaling_type IS NOT NULL")
    spells_with_scaling = cursor.fetchone()[0]
    logger.info(f"Заклинаний с типом усиления: {spells_with_scaling}")
    
    # Показываем примеры
    cursor.execute("""
        SELECT s.name, s.level, s.scaling_type, cs.character_level, cs.damage_dice
        FROM spells s
        JOIN cantrip_scaling cs ON s.id = cs.spell_id
        WHERE s.name = 'Огненный снаряд'
        ORDER BY cs.character_level
    """)
    
    results = cursor.fetchall()
    if results:
        logger.info("\nПример усиления заговора Огненный снаряд:")
        for row in results:
            logger.info(f"  Уровень {row[3]}: {row[4]} урона")
    
    # Показываем пример усиления через слоты
    cursor.execute("""
        SELECT s.name, s.level, ss.slot_level, ss.damage_bonus, ss.other_effects
        FROM spells s
        JOIN spell_slot_scaling ss ON s.id = ss.spell_id
        WHERE s.name = 'Магическая стрела'
        ORDER BY ss.slot_level
        LIMIT 3
    """)
    
    results = cursor.fetchall()
    if results:
        logger.info("\nПример усиления Магической стрелы через слоты:")
        for row in results:
            effects = json.loads(row[4]) if row[4] else {}
            logger.info(f"  Слот {row[2]} уровня: {effects.get('missiles', 'нет данных')}")

def main():
    """Основная функция."""
    conn = None
    cursor = None
    
    try:
        logger.info("Подключение к базе данных...")
        conn = connect_to_db()
        cursor = conn.cursor()
        
        logger.info("Заполнение данных об усилении заговоров...")
        populate_cantrip_scaling_data(cursor)
        conn.commit()
        
        logger.info("Заполнение данных об усилении заклинаний...")
        populate_spell_slot_scaling_data(cursor)
        conn.commit()
        
        logger.info("Обновление типов усиления...")
        update_spell_scaling_types(cursor)
        conn.commit()
        
        logger.info("Добавление специальных правил...")
        add_special_scaling_rules(cursor)
        conn.commit()
        
        logger.info("Проверка обновлений...")
        verify_updates(cursor)
        
        logger.info("\n✅ Данные об усилении заклинаний успешно добавлены!")
        
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
