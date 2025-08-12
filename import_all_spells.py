#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Объединенный скрипт для импорта заговоров и заклинаний из JSON файлов в базу данных.
Удаляет все существующие заклинания, сбрасывает автоинкремент и загружает данные заново.
Это гарантирует постоянные ID для заклинаний при условии добавления новых только в конец.
"""

import json
import mysql.connector
import logging
import re
import os
from config import DB_HOST, DB_USER, DB_PASSWORD, DB_NAME

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('import_all_spells.log', encoding='utf-8'),
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

def clear_all_spell_data(cursor):
    """Полностью очищает все данные о заклинаниях и связанные таблицы."""
    logger.info("Полная очистка данных о заклинаниях...")
    
    # Удаляем все связанные данные из зависимых таблиц
    tables_to_clear = [
        ('cantrip_scaling', 'записей из cantrip_scaling'),
        ('spell_slot_scaling', 'записей из spell_slot_scaling'),
        ('spell_scaling_rules', 'записей из spell_scaling_rules'),
        ('spells', 'заклинаний')
    ]
    
    for table, description in tables_to_clear:
        cursor.execute(f"DELETE FROM {table}")
        count = cursor.rowcount
        logger.info(f"Удалено {count} {description}")
    
    # Сбрасываем автоинкремент для всех таблиц
    logger.info("Сброс автоинкремента...")
    cursor.execute("ALTER TABLE spells AUTO_INCREMENT = 1")
    cursor.execute("ALTER TABLE cantrip_scaling AUTO_INCREMENT = 1")
    cursor.execute("ALTER TABLE spell_slot_scaling AUTO_INCREMENT = 1")
    cursor.execute("ALTER TABLE spell_scaling_rules AUTO_INCREMENT = 1")
    logger.info("Автоинкремент сброшен для всех таблиц")

def parse_damage_dice(damage_str):
    """Парсит строку с уроном и возвращает базовые кости урона."""
    if not damage_str:
        return None
    
    damage_str = str(damage_str).strip()
    
    # Убираем "к" из начала, если есть (например, "к8" -> "1d8")
    if damage_str.startswith('к'):
        return '1d' + damage_str[1:]
    
    # Убираем пробелы вокруг к/d
    damage_str = re.sub(r'\s*к\s*', 'к', damage_str)
    damage_str = re.sub(r'\s*d\s*', 'd', damage_str)
    
    # Заменяем русское "к" на английское "d"
    damage_str = damage_str.replace('к', 'd')
    
    # Обрабатываем случаи типа "1d4 + 1"
    if '+' in damage_str or '-' in damage_str:
        return damage_str
    
    # Для особых случаев как "1d8 или 1d12"
    if ' или ' in damage_str:
        damage_str = damage_str.split(' или ')[0]
    
    return damage_str

def parse_cantrip_scaling_info(scaling_rules):
    """Парсит правила скалирования заговоров."""
    if not scaling_rules:
        return None, None
    
    scaling_levels = []
    scaling_pattern = None
    
    # Паттерны для поиска информации о скалировании
    level_pattern = r'(\d+)-м.*?уровн'
    
    # Ищем уровни, на которых происходит усиление
    levels = re.findall(level_pattern, scaling_rules)
    if levels:
        scaling_levels = [int(l) for l in levels]
    
    # Определяем тип скалирования
    if 'урон увеличивается' in scaling_rules.lower():
        scaling_pattern = 'damage_increase'
    elif 'дополнительн' in scaling_rules.lower() and ('луч' in scaling_rules.lower() or 'снаряд' in scaling_rules.lower()):
        scaling_pattern = 'additional_beams'
    elif 'урон оружия изменяется' in scaling_rules.lower():
        scaling_pattern = 'weapon_damage_change'
    elif 'дистанция удваивается' in scaling_rules.lower():
        scaling_pattern = 'range_increase'
    
    return scaling_levels, scaling_pattern

def parse_spell_scaling_info(scaling_rules, level):
    """Парсит правила скалирования заклинаний."""
    if not scaling_rules:
        return None, None
    
    scaling_type = None
    base_scaling_info = {}
    
    scaling_lower = scaling_rules.lower()
    
    if level > 0:  # Для заклинаний (не заговоров)
        if 'урон увеличивается' in scaling_lower:
            scaling_type = 'slot_damage'
            damage_match = re.search(r'(\d+)[кd](\d+)', scaling_rules)
            if damage_match:
                base_scaling_info['per_slot_damage'] = f"{damage_match.group(1)}d{damage_match.group(2)}"
            base_scaling_info['description'] = scaling_rules
            
        elif 'дополнительн' in scaling_lower and ('существ' in scaling_lower or 'цел' in scaling_lower):
            scaling_type = 'slot_targets'
            target_match = re.search(r'(\d+|одно)\s+дополнительн', scaling_rules)
            if target_match:
                num = 1 if target_match.group(1) == 'одно' else int(target_match.group(1))
                base_scaling_info['additional_targets'] = num
            base_scaling_info['description'] = scaling_rules
            
        elif 'дополнительн' in scaling_lower and ('снаряд' in scaling_lower or 'дротик' in scaling_lower):
            scaling_type = 'slot_projectiles'
            base_scaling_info['description'] = scaling_rules
            
        elif 'временн' in scaling_lower and 'хит' in scaling_lower:
            scaling_type = 'slot_temp_hp'
            base_scaling_info['description'] = scaling_rules
            
        elif 'лечение' in scaling_lower:
            scaling_type = 'slot_healing'
            healing_match = re.search(r'(\d+)[кd](\d+)', scaling_rules)
            if healing_match:
                base_scaling_info['per_slot_healing'] = f"{healing_match.group(1)}d{healing_match.group(2)}"
            base_scaling_info['description'] = scaling_rules
            
        elif 'концентрац' in scaling_lower or 'длительност' in scaling_lower:
            scaling_type = 'slot_duration'
            base_scaling_info['description'] = scaling_rules
            
        elif 'радиус' in scaling_lower or 'размер' in scaling_lower or 'куб' in scaling_lower or 'сфер' in scaling_lower:
            scaling_type = 'slot_area'
            base_scaling_info['description'] = scaling_rules
            
        else:
            scaling_type = 'slot_special'
            base_scaling_info['description'] = scaling_rules
    
    return scaling_type, base_scaling_info if base_scaling_info else None

def import_cantrips(cursor, cantrips):
    """Импортирует заговоры в базу данных."""
    logger.info(f"Импорт {len(cantrips)} заговоров...")
    
    for cantrip in cantrips:
        name = cantrip['Русское название']
        base_damage = parse_damage_dice(cantrip.get('Базовый урон'))
        damage_type = cantrip.get('Тип урона')
        description = cantrip.get('Краткое описание', '')
        is_combat = cantrip.get('Наносит ли заклинание урон', False)
        is_area_of_effect = cantrip.get('Воздействует ли заклинание на площадь', False)
        saving_throw = cantrip.get('Характеристика спасброска')
        classes = cantrip.get('список классов с этим заклинанием', [])
        scaling_rules = cantrip.get('Правила скалирования при повышении уровня')
        
        available_classes = json.dumps(classes, ensure_ascii=False) if classes else None
        
        # Определяем тип скалирования
        scaling_type = None
        base_scaling_info = None
        
        if scaling_rules:
            scaling_levels, pattern = parse_cantrip_scaling_info(scaling_rules)
            
            if pattern == 'damage_increase' or pattern == 'weapon_damage_change':
                scaling_type = 'cantrip_damage'
                base_scaling_info = json.dumps({
                    'levels': scaling_levels if scaling_levels else [5, 11, 17],
                    'description': scaling_rules
                }, ensure_ascii=False)
            elif pattern == 'additional_beams':
                scaling_type = 'cantrip_beams'
                base_scaling_info = json.dumps({
                    'levels': scaling_levels if scaling_levels else [5, 11, 17],
                    'description': scaling_rules
                }, ensure_ascii=False)
            elif pattern == 'range_increase':
                scaling_type = 'cantrip_range'
                base_scaling_info = json.dumps({
                    'levels': scaling_levels if scaling_levels else [5, 11, 17],
                    'description': scaling_rules
                }, ensure_ascii=False)
        
        insert_query = """
            INSERT INTO spells 
            (level, name, damage, damage_type, description, is_combat, is_area_of_effect, 
             available_classes, saving_throw, scaling_type, base_scaling_info)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        
        cursor.execute(insert_query, (
            0,  # level = 0 для заговоров
            name,
            base_damage,
            damage_type,
            description,
            is_combat,
            is_area_of_effect,
            available_classes,
            saving_throw,
            scaling_type,
            base_scaling_info
        ))
        
        logger.debug(f"Добавлен заговор: {name}")

def import_spells(cursor, spells, level):
    """Импортирует заклинания в базу данных."""
    logger.info(f"Импорт {len(spells)} заклинаний {level} уровня...")
    
    for spell in spells:
        name = spell.get('name', '')
        base_damage = parse_damage_dice(spell.get('base_damage'))
        damage_type = spell.get('damage_type')
        description = spell.get('short_description', '')
        is_combat = spell.get('deals_damage', False)
        is_area_of_effect = spell.get('area_effect', False)
        saving_throw = spell.get('saving_throw')
        classes = spell.get('classes', [])
        scaling_rules = spell.get('scaling')
        
        available_classes = json.dumps(classes, ensure_ascii=False) if classes else None
        
        scaling_type, base_scaling_info = parse_spell_scaling_info(scaling_rules, level)
        base_scaling_info_json = json.dumps(base_scaling_info, ensure_ascii=False) if base_scaling_info else None
        
        insert_query = """
            INSERT INTO spells 
            (level, name, damage, damage_type, description, is_combat, is_area_of_effect, 
             available_classes, saving_throw, scaling_type, base_scaling_info)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        
        try:
            cursor.execute(insert_query, (
                level,
                name,
                base_damage,
                damage_type,
                description,
                is_combat,
                is_area_of_effect,
                available_classes,
                saving_throw,
                scaling_type,
                base_scaling_info_json
            ))
            logger.debug(f"Добавлено заклинание: {name}")
        except mysql.connector.Error as e:
            logger.error(f"Ошибка при добавлении заклинания {name}: {e}")

def add_cantrip_scaling_data(cursor, cantrips):
    """Добавляет данные о скалировании заговоров."""
    logger.info("Добавление данных о скалировании заговоров...")
    
    cursor.execute("SELECT id, name, base_scaling_info FROM spells WHERE level = 0")
    spell_data = cursor.fetchall()
    
    scaling_data = []
    
    for spell_id, name, scaling_info_json in spell_data:
        if not scaling_info_json:
            continue
        
        scaling_info = json.loads(scaling_info_json)
        scaling_rules = scaling_info.get('description', '')
        
        original_cantrip = next((c for c in cantrips if c['Русское название'] == name), None)
        if not original_cantrip:
            continue
        
        base_damage = parse_damage_dice(original_cantrip.get('Базовый урон'))
        if not base_damage:
            continue
        
        # Особые случаи обработки
        if 'Мистический заряд' in name:
            scaling_data.extend([
                (spell_id, 1, '1d10', 1, None),
                (spell_id, 5, '1d10', 2, json.dumps({'description': '2 луча'}, ensure_ascii=False)),
                (spell_id, 11, '1d10', 3, json.dumps({'description': '3 луча'}, ensure_ascii=False)),
                (spell_id, 17, '1d10', 4, json.dumps({'description': '4 луча'}, ensure_ascii=False))
            ])
        elif 'Уход за умирающим' in name:
            scaling_data.extend([
                (spell_id, 1, None, None, json.dumps({'range': '5 футов'}, ensure_ascii=False)),
                (spell_id, 5, None, None, json.dumps({'range': '30 футов'}, ensure_ascii=False)),
                (spell_id, 11, None, None, json.dumps({'range': '60 футов'}, ensure_ascii=False)),
                (spell_id, 17, None, None, json.dumps({'range': '120 футов'}, ensure_ascii=False))
            ])
        elif 'урон увеличивается' in scaling_rules.lower() or 'урон оружия изменяется' in scaling_rules.lower():
            if 'Дубинка' in name:
                scaling_data.extend([
                    (spell_id, 1, '1d8', None, None),
                    (spell_id, 5, '1d10', None, None),
                    (spell_id, 11, '1d12', None, None),
                    (spell_id, 17, '2d6', None, None)
                ])
            elif 'Погребальный звон' in name:
                scaling_data.extend([
                    (spell_id, 1, '1d8', None, json.dumps({'note': '1d12 против раненых'}, ensure_ascii=False)),
                    (spell_id, 5, '2d8', None, json.dumps({'note': '2d12 против раненых'}, ensure_ascii=False)),
                    (spell_id, 11, '3d8', None, json.dumps({'note': '3d12 против раненых'}, ensure_ascii=False)),
                    (spell_id, 17, '4d8', None, json.dumps({'note': '4d12 против раненых'}, ensure_ascii=False))
                ])
            elif 'Меткий удар' in name:
                scaling_data.extend([
                    (spell_id, 1, None, None, json.dumps({'bonus_damage': 'нет'}, ensure_ascii=False)),
                    (spell_id, 5, None, None, json.dumps({'bonus_damage': '1d6 излучением'}, ensure_ascii=False)),
                    (spell_id, 11, None, None, json.dumps({'bonus_damage': '2d6 излучением'}, ensure_ascii=False)),
                    (spell_id, 17, None, None, json.dumps({'bonus_damage': '3d6 излучением'}, ensure_ascii=False))
                ])
            else:
                # Стандартное увеличение урона
                damage_match = re.match(r'(\d+)d(\d+)', base_damage)
                if damage_match:
                    num_dice = int(damage_match.group(1))
                    die_size = damage_match.group(2)
                    
                    scaling_data.extend([
                        (spell_id, 1, f'{num_dice}d{die_size}', None, None),
                        (spell_id, 5, f'{num_dice * 2}d{die_size}', None, None),
                        (spell_id, 11, f'{num_dice * 3}d{die_size}', None, None),
                        (spell_id, 17, f'{num_dice * 4}d{die_size}', None, None)
                    ])
    
    if scaling_data:
        cursor.executemany("""
            INSERT INTO cantrip_scaling (spell_id, character_level, damage_dice, num_beams, other_effects)
            VALUES (%s, %s, %s, %s, %s)
        """, scaling_data)
        logger.info(f"Добавлено {len(scaling_data)} записей о скалировании заговоров")

def add_spell_scaling_data(cursor, spells, level):
    """Добавляет данные о скалировании заклинаний."""
    logger.info(f"Добавление данных о скалировании заклинаний {level} уровня...")
    
    cursor.execute("SELECT id, name, base_scaling_info FROM spells WHERE level = %s", (level,))
    spell_data = cursor.fetchall()
    
    scaling_data = []
    rules_data = []
    
    for spell_id, name, scaling_info_json in spell_data:
        if not scaling_info_json:
            continue
        
        scaling_info = json.loads(scaling_info_json)
        
        original_spell = next((s for s in spells if s.get('name') == name), None)
        if not original_spell:
            continue
        
        scaling_rules = original_spell.get('scaling', '')
        if not scaling_rules:
            continue
        
        # Добавляем правила скалирования для слотов выше базового уровня
        for slot_level in range(level + 1, 10):  # Слоты от (level+1) до 9
            damage_bonus = None
            target_bonus = None
            other_effects = {}
            
            if 'per_slot_damage' in scaling_info:
                damage_bonus = scaling_info['per_slot_damage']
                multiplier = slot_level - level
                damage_match = re.match(r'(\d+)d(\d+)', damage_bonus)
                if damage_match:
                    num_dice = int(damage_match.group(1)) * multiplier
                    die_size = damage_match.group(2)
                    damage_bonus = f"+{num_dice}d{die_size}"
            
            elif 'additional_targets' in scaling_info:
                target_bonus = scaling_info['additional_targets'] * (slot_level - level)
                other_effects['targets'] = f"+{target_bonus} целей"
            
            elif 'per_slot_healing' in scaling_info:
                healing_bonus = scaling_info['per_slot_healing']
                multiplier = slot_level - level
                healing_match = re.match(r'(\d+)d(\d+)', healing_bonus)
                if healing_match:
                    num_dice = int(healing_match.group(1)) * multiplier
                    die_size = healing_match.group(2)
                    other_effects['healing'] = f"+{num_dice}d{die_size}"
            
            # Специальные случаи
            if 'волшебная стрела' in name.lower():
                target_bonus = slot_level - level
                other_effects['projectiles'] = f"+{target_bonus} снарядов"
            
            if other_effects:
                other_effects_json = json.dumps(other_effects, ensure_ascii=False)
            else:
                other_effects_json = None
            
            if damage_bonus or target_bonus or other_effects_json:
                scaling_data.append(
                    (spell_id, slot_level, damage_bonus, None, target_bonus, other_effects_json)
                )
        
        # Добавляем специальные правила
        if 'per_slot_damage' in scaling_info:
            rules_data.append(
                (spell_id, 'damage_per_slot', scaling_info['per_slot_damage'],
                 f"Урон увеличивается на {scaling_info['per_slot_damage']} за каждый уровень ячейки выше {level}-го")
            )
        elif 'additional_targets' in scaling_info:
            rules_data.append(
                (spell_id, 'targets_per_slot', str(scaling_info['additional_targets']),
                 f"Дополнительные цели: +{scaling_info['additional_targets']} за каждый уровень ячейки выше {level}-го")
            )
    
    if scaling_data:
        cursor.executemany("""
            INSERT INTO spell_slot_scaling 
            (spell_id, slot_level, damage_bonus, duration_bonus, target_bonus, other_effects)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, scaling_data)
        logger.info(f"Добавлено {len(scaling_data)} записей о скалировании через слоты")
    
    if rules_data:
        cursor.executemany("""
            INSERT INTO spell_scaling_rules (spell_id, rule_type, rule_value, rule_description)
            VALUES (%s, %s, %s, %s)
        """, rules_data)
        logger.info(f"Добавлено {len(rules_data)} специальных правил скалирования")

def verify_import(cursor):
    """Проверяет результаты импорта."""
    logger.info("\n" + "="*60)
    logger.info("ПРОВЕРКА РЕЗУЛЬТАТОВ ИМПОРТА")
    logger.info("="*60)
    
    # Общая статистика
    cursor.execute("SELECT COUNT(*) FROM spells")
    total_spells = cursor.fetchone()[0]
    logger.info(f"Всего заклинаний в базе: {total_spells}")
    
    # Статистика по уровням
    cursor.execute("""
        SELECT level, COUNT(*) as count 
        FROM spells 
        GROUP BY level 
        ORDER BY level
    """)
    
    logger.info("\nРаспределение по уровням:")
    for level, count in cursor.fetchall():
        level_name = "Заговоры" if level == 0 else f"Уровень {level}"
        logger.info(f"  {level_name}: {count} заклинаний")
    
    # Статистика по скалированию
    cursor.execute("SELECT COUNT(*) FROM cantrip_scaling")
    cantrip_scaling = cursor.fetchone()[0]
    logger.info(f"\nЗаписей о скалировании заговоров: {cantrip_scaling}")
    
    cursor.execute("SELECT COUNT(*) FROM spell_slot_scaling")
    slot_scaling = cursor.fetchone()[0]
    logger.info(f"Записей о скалировании через слоты: {slot_scaling}")
    
    cursor.execute("SELECT COUNT(*) FROM spell_scaling_rules")
    rules_count = cursor.fetchone()[0]
    logger.info(f"Специальных правил скалирования: {rules_count}")
    
    # Примеры первых заклинаний с их ID
    logger.info("\nПервые 10 заклинаний с их ID (для проверки постоянства):")
    cursor.execute("""
        SELECT id, level, name 
        FROM spells 
        ORDER BY id 
        LIMIT 10
    """)
    
    for id, level, name in cursor.fetchall():
        level_str = "Заговор" if level == 0 else f"Ур.{level}"
        logger.info(f"  ID {id:3d}: [{level_str}] {name}")

def main():
    """Основная функция."""
    conn = None
    cursor = None
    
    try:
        logger.info("="*60)
        logger.info("НАЧАЛО ПОЛНОГО ИМПОРТА ЗАКЛИНАНИЙ")
        logger.info("="*60)
        
        logger.info("Подключение к базе данных...")
        conn = connect_to_db()
        cursor = conn.cursor()
        
        # Полная очистка всех данных о заклинаниях
        logger.info("\nЭТАП 1: Очистка базы данных")
        clear_all_spell_data(cursor)
        conn.commit()
        
        # Импорт заговоров
        logger.info("\nЭТАП 2: Импорт заговоров")
        cantrips_file = 'Docs/заговоры.txt'
        if os.path.exists(cantrips_file):
            with open(cantrips_file, 'r', encoding='utf-8') as f:
                cantrips = json.load(f)
            logger.info(f"Загружено {len(cantrips)} заговоров из файла")
            import_cantrips(cursor, cantrips)
            conn.commit()
            add_cantrip_scaling_data(cursor, cantrips)
            conn.commit()
        else:
            logger.warning(f"Файл {cantrips_file} не найден")
        
        # Импорт заклинаний по уровням
        logger.info("\nЭТАП 3: Импорт заклинаний по уровням")
        for level in range(1, 10):  # Уровни заклинаний от 1 до 9
            filename = f"Docs/{level}.txt"
            
            if not os.path.exists(filename):
                logger.info(f"Файл {filename} не найден, пропускаем уровень {level}")
                continue
            
            with open(filename, 'r', encoding='utf-8') as f:
                spells = json.load(f)
            
            if not spells:
                logger.warning(f"Файл {filename} пустой или содержит некорректные данные")
                continue
            
            logger.info(f"Загружено {len(spells)} заклинаний {level} уровня")
            import_spells(cursor, spells, level)
            conn.commit()
            add_spell_scaling_data(cursor, spells, level)
            conn.commit()
        
        # Проверка результатов
        logger.info("\nЭТАП 4: Проверка результатов")
        verify_import(cursor)
        
        logger.info("\n" + "="*60)
        logger.info("✅ ИМПОРТ УСПЕШНО ЗАВЕРШЕН!")
        logger.info("="*60)
        logger.info("\nВАЖНО: ID заклинаний теперь будут постоянными,")
        logger.info("если новые заклинания добавляются только в конец файлов.")
        
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
