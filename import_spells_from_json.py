#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Скрипт для импорта заклинаний из JSON файлов в базу данных.
Обрабатывает файлы с названиями 1.txt, 2.txt и т.д. для разных уровней заклинаний.
Удаляет старые placeholder заклинания и добавляет реальные заклинания с их параметрами скалирования.
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
        logging.FileHandler('import_spells.log', encoding='utf-8'),
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

def load_spells_from_file(filename):
    """Загружает заклинания из JSON файла."""
    if not os.path.exists(filename):
        logger.warning(f"Файл {filename} не найден")
        return None
    
    with open(filename, 'r', encoding='utf-8') as f:
        return json.load(f)

def clear_old_spells(cursor, level):
    """Удаляет существующие заклинания указанного уровня из базы данных."""
    logger.info(f"Удаление старых заклинаний {level} уровня...")
    
    # Сначала удаляем связанные записи из таблиц скалирования
    cursor.execute("""
        DELETE ss FROM spell_slot_scaling ss
        JOIN spells s ON ss.spell_id = s.id
        WHERE s.level = %s
    """, (level,))
    logger.info(f"Удалено {cursor.rowcount} записей из spell_slot_scaling")
    
    cursor.execute("""
        DELETE ssr FROM spell_scaling_rules ssr
        JOIN spells s ON ssr.spell_id = s.id
        WHERE s.level = %s
    """, (level,))
    logger.info(f"Удалено {cursor.rowcount} записей из spell_scaling_rules")
    
    # Теперь удаляем сами заклинания
    cursor.execute("DELETE FROM spells WHERE level = %s", (level,))
    logger.info(f"Удалено {cursor.rowcount} заклинаний уровня {level} из таблицы spells")

def parse_damage_dice(damage_str):
    """Парсит строку с уроном и возвращает базовые кости урона."""
    if not damage_str:
        return None
    
    # Обрабатываем различные форматы
    damage_str = str(damage_str).strip()
    
    # Убираем пробелы вокруг к/d
    damage_str = re.sub(r'\s*к\s*', 'к', damage_str)
    damage_str = re.sub(r'\s*d\s*', 'd', damage_str)
    
    # Заменяем русское "к" на английское "d"
    damage_str = damage_str.replace('к', 'd')
    
    # Обрабатываем случаи типа "1d4 + 1"
    if '+' in damage_str or '-' in damage_str:
        # Сохраняем модификаторы
        return damage_str
    
    # Для особых случаев как "1d8 или 1d12"
    if ' или ' in damage_str:
        # Берем первое значение для базового урона
        damage_str = damage_str.split(' или ')[0]
    
    return damage_str

def parse_scaling_info(scaling_rules, level):
    """Парсит правила скалирования и возвращает структурированную информацию."""
    if not scaling_rules:
        return None, None
    
    scaling_type = None
    base_scaling_info = {}
    
    # Определяем тип скалирования
    scaling_lower = scaling_rules.lower()
    
    if level > 0:  # Для заклинаний (не заговоров)
        if 'урон увеличивается' in scaling_lower:
            scaling_type = 'slot_damage'
            # Пытаемся извлечь значение увеличения урона
            damage_match = re.search(r'(\d+)[кd](\d+)', scaling_rules)
            if damage_match:
                base_scaling_info['per_slot_damage'] = f"{damage_match.group(1)}d{damage_match.group(2)}"
            base_scaling_info['description'] = scaling_rules
            
        elif 'дополнительн' in scaling_lower and ('существ' in scaling_lower or 'цел' in scaling_lower):
            scaling_type = 'slot_targets'
            # Пытаемся извлечь количество дополнительных целей
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
            # Пытаемся извлечь значение увеличения лечения
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

def import_spells(cursor, spells, level):
    """Импортирует заклинания в базу данных."""
    logger.info(f"Импорт {len(spells)} заклинаний {level} уровня...")
    
    imported_count = 0
    
    for spell in spells:
        # Подготавливаем данные для вставки
        name = spell.get('name', '')
        base_damage = parse_damage_dice(spell.get('base_damage'))
        damage_type = spell.get('damage_type')
        description = spell.get('short_description', '')
        is_combat = spell.get('deals_damage', False)
        is_area_of_effect = spell.get('area_effect', False)
        saving_throw = spell.get('saving_throw')
        classes = spell.get('classes', [])
        scaling_rules = spell.get('scaling')
        
        # Преобразуем список классов в JSON
        available_classes = json.dumps(classes, ensure_ascii=False) if classes else None
        
        # Определяем тип скалирования
        scaling_type, base_scaling_info = parse_scaling_info(scaling_rules, level)
        base_scaling_info_json = json.dumps(base_scaling_info, ensure_ascii=False) if base_scaling_info else None
        
        # Вставляем заклинание в базу данных
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
            
            imported_count += 1
            logger.info(f"Добавлено заклинание: {name}")
            
        except mysql.connector.Error as e:
            logger.error(f"Ошибка при добавлении заклинания {name}: {e}")
    
    logger.info(f"Успешно импортировано {imported_count} заклинаний {level} уровня")

def add_spell_scaling_data(cursor, spells, level):
    """Добавляет данные о скалировании заклинаний."""
    logger.info(f"Добавление данных о скалировании заклинаний {level} уровня...")
    
    # Получаем ID добавленных заклинаний
    cursor.execute("SELECT id, name, base_scaling_info FROM spells WHERE level = %s", (level,))
    spell_data = cursor.fetchall()
    
    scaling_data = []
    rules_data = []
    
    for spell_id, name, scaling_info_json in spell_data:
        if not scaling_info_json:
            continue
        
        scaling_info = json.loads(scaling_info_json)
        
        # Находим соответствующее заклинание из исходных данных
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
            
            # Определяем бонусы на основе типа скалирования
            if 'per_slot_damage' in scaling_info:
                damage_bonus = scaling_info['per_slot_damage']
                multiplier = slot_level - level
                # Парсим и умножаем кости урона
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
                # Парсим и умножаем кости лечения
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
    
    # Вставляем данные о скалировании через слоты
    if scaling_data:
        cursor.executemany("""
            INSERT INTO spell_slot_scaling 
            (spell_id, slot_level, damage_bonus, duration_bonus, target_bonus, other_effects)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE 
                damage_bonus = VALUES(damage_bonus),
                duration_bonus = VALUES(duration_bonus),
                target_bonus = VALUES(target_bonus),
                other_effects = VALUES(other_effects)
        """, scaling_data)
        logger.info(f"Добавлено {len(scaling_data)} записей о скалировании заклинаний через слоты")
    
    # Вставляем специальные правила
    if rules_data:
        cursor.executemany("""
            INSERT INTO spell_scaling_rules (spell_id, rule_type, rule_value, rule_description)
            VALUES (%s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                rule_value = VALUES(rule_value),
                rule_description = VALUES(rule_description)
        """, rules_data)
        logger.info(f"Добавлено {len(rules_data)} специальных правил скалирования")

def clear_all_placeholder_spells(cursor):
    """Удаляет все placeholder заклинания из базы данных."""
    logger.info("Удаление всех placeholder заклинаний...")
    
    # Список известных placeholder заклинаний
    placeholder_names = [
        'Fire Bolt', 'Magic Missile', 'Fireball', 'Cure Wounds', 'Shield',
        'Burning Hands', 'Charm Person', 'Detect Magic', 'Disguise Self',
        'Fog Cloud', 'Healing Word', 'Hideous Laughter', 'Identify',
        'Illusory Script', 'Jump', 'Longstrider', 'Mage Armor', 'Magic Missile',
        'Protection from Evil and Good', 'Ray of Sickness', 'Shield', 'Silent Image',
        'Sleep', 'Speak with Animals', 'Thunderwave', 'Unseen Servant',
        'Acid Splash', 'Blade Ward', 'Chill Touch', 'Dancing Lights',
        'Druidcraft', 'Eldritch Blast', 'Fire Bolt', 'Friends', 'Guidance',
        'Light', 'Mage Hand', 'Mending', 'Message', 'Minor Illusion',
        'Poison Spray', 'Prestidigitation', 'Produce Flame', 'Ray of Frost',
        'Resistance', 'Sacred Flame', 'Shillelagh', 'Shocking Grasp',
        'Spare the Dying', 'Thaumaturgy', 'Thorn Whip', 'True Strike',
        'Vicious Mockery'
    ]
    
    # Удаляем placeholder заклинания на английском
    if placeholder_names:
        placeholders = ', '.join(['%s'] * len(placeholder_names))
        
        # Удаляем связанные записи
        cursor.execute(f"""
            DELETE ss FROM spell_slot_scaling ss
            JOIN spells s ON ss.spell_id = s.id
            WHERE s.name IN ({placeholders})
        """, placeholder_names)
        
        cursor.execute(f"""
            DELETE ssr FROM spell_scaling_rules ssr
            JOIN spells s ON ssr.spell_id = s.id
            WHERE s.name IN ({placeholders})
        """, placeholder_names)
        
        cursor.execute(f"""
            DELETE cs FROM cantrip_scaling cs
            JOIN spells s ON cs.spell_id = s.id
            WHERE s.name IN ({placeholders})
        """, placeholder_names)
        
        # Удаляем сами заклинания
        cursor.execute(f"DELETE FROM spells WHERE name IN ({placeholders})", placeholder_names)
        logger.info(f"Удалено {cursor.rowcount} placeholder заклинаний")

def verify_import(cursor, level):
    """Проверяет результаты импорта."""
    cursor.execute("SELECT COUNT(*) FROM spells WHERE level = %s", (level,))
    spell_count = cursor.fetchone()[0]
    logger.info(f"Всего заклинаний {level} уровня в базе: {spell_count}")
    
    cursor.execute("""
        SELECT COUNT(*) FROM spell_slot_scaling ss
        JOIN spells s ON ss.spell_id = s.id
        WHERE s.level = %s
    """, (level,))
    scaling_count = cursor.fetchone()[0]
    logger.info(f"Записей о скалировании для заклинаний {level} уровня: {scaling_count}")
    
    # Показываем примеры импортированных заклинаний
    cursor.execute("""
        SELECT name, damage, damage_type, available_classes, scaling_type 
        FROM spells 
        WHERE level = %s 
        LIMIT 5
    """, (level,))
    
    logger.info(f"\nПримеры импортированных заклинаний {level} уровня:")
    for name, damage, damage_type, classes, scaling_type in cursor.fetchall():
        classes_list = json.loads(classes) if classes else []
        logger.info(f"  - {name}: урон {damage} ({damage_type}), классы: {', '.join(classes_list[:3])}, скалирование: {scaling_type}")

def main():
    """Основная функция."""
    conn = None
    cursor = None
    
    try:
        logger.info("Подключение к базе данных...")
        conn = connect_to_db()
        cursor = conn.cursor()
        
        # Сначала удаляем все placeholder заклинания
        logger.info("Очистка placeholder заклинаний...")
        clear_all_placeholder_spells(cursor)
        conn.commit()
        
        # Обрабатываем файлы с заклинаниями разных уровней
        for level in range(1, 10):  # Уровни заклинаний от 1 до 9
            filename = f"Docs/{level}.txt"
            
            logger.info(f"\n{'='*60}")
            logger.info(f"Обработка файла {filename} (уровень {level})")
            logger.info(f"{'='*60}")
            
            spells = load_spells_from_file(filename)
            
            if spells is None:
                logger.info(f"Файл {filename} не найден, пропускаем уровень {level}")
                continue
            
            if not spells:
                logger.warning(f"Файл {filename} пустой или содержит некорректные данные")
                continue
            
            logger.info(f"Загружено {len(spells)} заклинаний из файла {filename}")
            
            # Очистка старых заклинаний этого уровня
            clear_old_spells(cursor, level)
            conn.commit()
            
            # Импорт новых заклинаний
            import_spells(cursor, spells, level)
            conn.commit()
            
            # Добавление данных о скалировании
            add_spell_scaling_data(cursor, spells, level)
            conn.commit()
            
            # Проверка результатов импорта
            verify_import(cursor, level)
        
        logger.info("\n✅ Импорт заклинаний успешно завершен!")
        
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
