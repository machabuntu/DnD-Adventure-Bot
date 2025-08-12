#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Скрипт для добавления системы усиления заклинаний в базу данных.
Добавляет таблицы для хранения информации о масштабировании заклинаний.
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
        logging.FileHandler('spell_scaling_update.log', encoding='utf-8'),
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

def add_scaling_columns_to_spells(cursor):
    """Добавляет колонки для базовой информации об усилении в таблицу spells."""
    try:
        # Проверяем, существует ли колонка
        cursor.execute("""
            SELECT COUNT(*) 
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_SCHEMA = %s 
            AND TABLE_NAME = 'spells' 
            AND COLUMN_NAME = 'scaling_type'
        """, (DB_NAME,))
        
        if cursor.fetchone()[0] == 0:
            cursor.execute("""
                ALTER TABLE spells 
                ADD COLUMN scaling_type VARCHAR(50) DEFAULT NULL 
                COMMENT 'Тип усиления: cantrip_damage, slot_damage, slot_duration, slot_targets, etc.'
            """)
            logger.info("Добавлена колонка scaling_type в таблицу spells")
        
        # Добавляем колонку для базовых параметров усиления
        cursor.execute("""
            SELECT COUNT(*) 
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_SCHEMA = %s 
            AND TABLE_NAME = 'spells' 
            AND COLUMN_NAME = 'base_scaling_info'
        """, (DB_NAME,))
        
        if cursor.fetchone()[0] == 0:
            cursor.execute("""
                ALTER TABLE spells 
                ADD COLUMN base_scaling_info TEXT DEFAULT NULL 
                COMMENT 'JSON с базовой информацией об усилении'
            """)
            logger.info("Добавлена колонка base_scaling_info в таблицу spells")
            
    except mysql.connector.Error as e:
        logger.error(f"Ошибка при добавлении колонок: {e}")
        raise

def create_spell_scaling_tables(cursor):
    """Создает таблицы для системы усиления заклинаний."""
    
    # Таблица для усиления заговоров по уровню персонажа
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cantrip_scaling (
            id INT AUTO_INCREMENT PRIMARY KEY,
            spell_id INT NOT NULL,
            character_level INT NOT NULL,
            damage_dice VARCHAR(50) COMMENT 'Кости урона на этом уровне, например 2d10',
            num_beams INT DEFAULT NULL COMMENT 'Количество лучей/снарядов (для Eldritch Blast и т.п.)',
            other_effects TEXT DEFAULT NULL COMMENT 'JSON с другими эффектами усиления',
            FOREIGN KEY (spell_id) REFERENCES spells(id) ON DELETE CASCADE,
            UNIQUE KEY unique_cantrip_level (spell_id, character_level)
        ) COMMENT='Усиление заговоров в зависимости от уровня персонажа'
    """)
    logger.info("Создана таблица cantrip_scaling")
    
    # Таблица для усиления заклинаний при использовании слотов высокого уровня
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS spell_slot_scaling (
            id INT AUTO_INCREMENT PRIMARY KEY,
            spell_id INT NOT NULL,
            slot_level INT NOT NULL COMMENT 'Уровень слота (от минимального уровня заклинания до 9)',
            damage_bonus VARCHAR(50) DEFAULT NULL COMMENT 'Дополнительный урон, например +1d6',
            duration_bonus VARCHAR(100) DEFAULT NULL COMMENT 'Дополнительная длительность',
            target_bonus INT DEFAULT NULL COMMENT 'Дополнительные цели',
            other_effects TEXT DEFAULT NULL COMMENT 'JSON с другими эффектами усиления',
            FOREIGN KEY (spell_id) REFERENCES spells(id) ON DELETE CASCADE,
            UNIQUE KEY unique_spell_slot (spell_id, slot_level)
        ) COMMENT='Усиление заклинаний при использовании слотов высокого уровня'
    """)
    logger.info("Создана таблица spell_slot_scaling")
    
    # Таблица для хранения специальных правил усиления
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS spell_scaling_rules (
            id INT AUTO_INCREMENT PRIMARY KEY,
            spell_id INT NOT NULL,
            rule_type VARCHAR(50) NOT NULL COMMENT 'Тип правила: damage_per_slot, healing_per_slot, etc.',
            rule_value VARCHAR(100) NOT NULL COMMENT 'Значение правила, например 1d8',
            rule_description TEXT COMMENT 'Текстовое описание правила',
            FOREIGN KEY (spell_id) REFERENCES spells(id) ON DELETE CASCADE
        ) COMMENT='Специальные правила усиления заклинаний'
    """)
    logger.info("Создана таблица spell_scaling_rules")

def populate_cantrip_scaling_data(cursor):
    """Заполняет данные об усилении заговоров."""
    
    # Получаем ID заговоров
    cursor.execute("SELECT id, name FROM spells WHERE level = 0")
    cantrips = {name: id for id, name in cursor.fetchall()}
    
    cantrip_scaling_data = []
    
    # Fire Bolt - урон увеличивается
    if 'Fire Bolt' in cantrips:
        spell_id = cantrips['Fire Bolt']
        cantrip_scaling_data.extend([
            (spell_id, 1, '1d10', None, None),
            (spell_id, 5, '2d10', None, None),
            (spell_id, 11, '3d10', None, None),
            (spell_id, 17, '4d10', None, None)
        ])
    
    # Eldritch Blast - увеличивается количество лучей
    if 'Eldritch Blast' in cantrips:
        spell_id = cantrips['Eldritch Blast']
        cantrip_scaling_data.extend([
            (spell_id, 1, '1d10', 1, None),
            (spell_id, 5, '1d10', 2, json.dumps({'description': '2 луча'})),
            (spell_id, 11, '1d10', 3, json.dumps({'description': '3 луча'})),
            (spell_id, 17, '1d10', 4, json.dumps({'description': '4 луча'}))
        ])
    
    # Ray of Frost - урон увеличивается
    if 'Ray of Frost' in cantrips:
        spell_id = cantrips['Ray of Frost']
        cantrip_scaling_data.extend([
            (spell_id, 1, '1d8', None, json.dumps({'slow_effect': '10 футов'})),
            (spell_id, 5, '2d8', None, json.dumps({'slow_effect': '10 футов'})),
            (spell_id, 11, '3d8', None, json.dumps({'slow_effect': '10 футов'})),
            (spell_id, 17, '4d8', None, json.dumps({'slow_effect': '10 футов'}))
        ])
    
    # Shocking Grasp - урон увеличивается
    if 'Shocking Grasp' in cantrips:
        spell_id = cantrips['Shocking Grasp']
        cantrip_scaling_data.extend([
            (spell_id, 1, '1d8', None, None),
            (spell_id, 5, '2d8', None, None),
            (spell_id, 11, '3d8', None, None),
            (spell_id, 17, '4d8', None, None)
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

def populate_spell_slot_scaling_data(cursor):
    """Заполняет данные об усилении заклинаний при использовании слотов высокого уровня."""
    
    # Получаем ID заклинаний
    cursor.execute("SELECT id, name, level FROM spells WHERE level > 0")
    spells = {name: (id, level) for id, name, level in cursor.fetchall()}
    
    slot_scaling_data = []
    
    # Magic Missile - добавляет дополнительные снаряды
    if 'Magic Missile' in spells:
        spell_id, base_level = spells['Magic Missile']
        for slot_level in range(2, 10):  # Слоты 2-9 уровня
            additional_missiles = slot_level - base_level
            slot_scaling_data.append(
                (spell_id, slot_level, None, None, additional_missiles, 
                 json.dumps({'missiles': f'+{additional_missiles} снаряда'}))
            )
    
    # Cure Wounds - увеличивает лечение
    if 'Cure Wounds' in spells:
        spell_id, base_level = spells['Cure Wounds']
        for slot_level in range(2, 10):
            slot_scaling_data.append(
                (spell_id, slot_level, f'+{slot_level - base_level}d8', None, None,
                 json.dumps({'healing': f'Дополнительное лечение {slot_level - base_level}d8'}))
            )
    
    # Burning Hands - увеличивает урон
    if 'Burning Hands' in spells:
        spell_id, base_level = spells['Burning Hands']
        for slot_level in range(2, 10):
            slot_scaling_data.append(
                (spell_id, slot_level, f'+{slot_level - base_level}d6', None, None, None)
            )
    
    # Fireball - увеличивает урон
    if 'Fireball' in spells:
        spell_id, base_level = spells['Fireball']
        for slot_level in range(4, 10):  # Fireball - заклинание 3 уровня
            slot_scaling_data.append(
                (spell_id, slot_level, f'+{slot_level - base_level}d6', None, None, None)
            )
    
    # Hold Person - может воздействовать на дополнительные цели
    if 'Hold Person' in spells:
        spell_id, base_level = spells['Hold Person']
        for slot_level in range(3, 10):
            slot_scaling_data.append(
                (spell_id, slot_level, None, None, slot_level - base_level,
                 json.dumps({'targets': f'+{slot_level - base_level} цели'}))
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

def update_spell_scaling_types(cursor):
    """Обновляет типы усиления в таблице spells."""
    
    # Обновляем заговоры
    cursor.execute("""
        UPDATE spells 
        SET scaling_type = 'cantrip_damage',
            base_scaling_info = '{"levels": [5, 11, 17], "description": "Урон увеличивается на указанных уровнях"}'
        WHERE level = 0 AND damage IS NOT NULL
    """)
    
    # Обновляем заклинания с усилением урона
    cursor.execute("""
        UPDATE spells 
        SET scaling_type = 'slot_damage',
            base_scaling_info = '{"per_slot": "см. таблицу spell_slot_scaling"}'
        WHERE name IN ('Magic Missile', 'Burning Hands', 'Fireball', 'Cure Wounds')
    """)
    
    # Обновляем заклинания с усилением целей
    cursor.execute("""
        UPDATE spells 
        SET scaling_type = 'slot_targets',
            base_scaling_info = '{"per_slot": "+1 цель за каждый слот выше минимального"}'
        WHERE name IN ('Hold Person', 'Charm Person')
    """)
    
    logger.info("Обновлены типы усиления заклинаний")

def add_special_scaling_rules(cursor):
    """Добавляет специальные правила усиления."""
    
    # Получаем ID заклинаний
    cursor.execute("SELECT id, name FROM spells")
    spells = {name: id for id, name in cursor.fetchall()}
    
    rules_data = []
    
    # Правила для некоторых заклинаний
    if 'Scorching Ray' in spells:
        rules_data.append(
            (spells['Scorching Ray'], 'rays_per_slot', '+1', 
             'Дополнительный луч за каждый слот выше 2-го')
        )
    
    if 'Spiritual Weapon' in spells:
        rules_data.append(
            (spells['Spiritual Weapon'], 'damage_per_two_slots', '+1d8',
             'Дополнительный урон 1d8 за каждые 2 слота выше 2-го')
        )
    
    if rules_data:
        cursor.executemany("""
            INSERT INTO spell_scaling_rules (spell_id, rule_type, rule_value, rule_description)
            VALUES (%s, %s, %s, %s)
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
        WHERE s.name = 'Fire Bolt'
        ORDER BY cs.character_level
    """)
    
    logger.info("\nПример усиления заговора Fire Bolt:")
    for row in cursor.fetchall():
        logger.info(f"  Уровень {row[3]}: {row[4]} урона")

def main():
    """Основная функция."""
    conn = None
    cursor = None
    
    try:
        logger.info("Подключение к базе данных...")
        conn = connect_to_db()
        cursor = conn.cursor()
        
        logger.info("Добавление колонок в таблицу spells...")
        add_scaling_columns_to_spells(cursor)
        conn.commit()
        
        logger.info("Создание таблиц для системы усиления...")
        create_spell_scaling_tables(cursor)
        conn.commit()
        
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
        
        logger.info("\n✅ Система усиления заклинаний успешно добавлена!")
        
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
