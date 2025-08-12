#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Скрипт для импорта заговоров из JSON файла в базу данных.
Удаляет старые placeholder заклинания и добавляет реальные заговоры с их параметрами скалирования.
"""

import json
import mysql.connector
import logging
import re
from config import DB_HOST, DB_USER, DB_PASSWORD, DB_NAME

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('import_cantrips.log', encoding='utf-8'),
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

def load_cantrips_from_file(filename='Docs/заговоры.txt'):
    """Загружает заговоры из JSON файла."""
    with open(filename, 'r', encoding='utf-8') as f:
        return json.load(f)

def clear_old_cantrips(cursor):
    """Удаляет существующие заговоры из базы данных."""
    logger.info("Удаление старых заговоров...")
    
    # Сначала удаляем связанные записи из таблиц скалирования
    cursor.execute("""
        DELETE cs FROM cantrip_scaling cs
        JOIN spells s ON cs.spell_id = s.id
        WHERE s.level = 0
    """)
    logger.info(f"Удалено {cursor.rowcount} записей из cantrip_scaling")
    
    cursor.execute("""
        DELETE ssr FROM spell_scaling_rules ssr
        JOIN spells s ON ssr.spell_id = s.id
        WHERE s.level = 0
    """)
    logger.info(f"Удалено {cursor.rowcount} записей из spell_scaling_rules")
    
    # Теперь удаляем сами заговоры
    cursor.execute("DELETE FROM spells WHERE level = 0")
    logger.info(f"Удалено {cursor.rowcount} заговоров из таблицы spells")

def parse_damage_dice(damage_str):
    """Парсит строку с уроном и возвращает базовые кости урона."""
    if not damage_str:
        return None
    
    # Убираем "к" из начала, если есть (например, "к8" -> "1d8")
    if damage_str.startswith('к'):
        return '1d' + damage_str[1:]
    
    # Обрабатываем обычный формат (например, "1к6" -> "1d6")
    damage_str = damage_str.replace('к', 'd')
    
    # Для особых случаев как "1к8 или 1к12"
    if ' или ' in damage_str:
        # Берем первое значение для базового урона
        damage_str = damage_str.split(' или ')[0]
    
    return damage_str

def parse_scaling_info(scaling_rules):
    """Парсит правила скалирования и возвращает структурированную информацию."""
    if not scaling_rules:
        return None, None
    
    scaling_levels = []
    scaling_pattern = None
    
    # Паттерны для поиска информации о скалировании
    level_pattern = r'(\d+)-м.*?уровн'
    damage_pattern = r'(\d+)[кd](\d+)'
    
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

def import_cantrips(cursor, cantrips):
    """Импортирует заговоры в базу данных."""
    logger.info(f"Импорт {len(cantrips)} заговоров...")
    
    for cantrip in cantrips:
        # Подготавливаем данные для вставки
        name = cantrip['Русское название']
        base_damage = parse_damage_dice(cantrip.get('Базовый урон'))
        damage_type = cantrip.get('Тип урона')
        description = cantrip.get('Краткое описание', '')
        is_combat = cantrip.get('Наносит ли заклинание урон', False)
        is_area_of_effect = cantrip.get('Воздействует ли заклинание на площадь', False)
        saving_throw = cantrip.get('Характеристика спасброска')
        classes = cantrip.get('список классов с этим заклинанием', [])
        scaling_rules = cantrip.get('Правила скалирования при повышении уровня')
        
        # Преобразуем список классов в JSON
        available_classes = json.dumps(classes, ensure_ascii=False) if classes else None
        
        # Определяем тип скалирования
        scaling_type = None
        base_scaling_info = None
        
        if scaling_rules:
            scaling_levels, pattern = parse_scaling_info(scaling_rules)
            
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
        
        # Вставляем заговор в базу данных
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
        
        logger.info(f"Добавлен заговор: {name}")

def add_cantrip_scaling_data(cursor, cantrips):
    """Добавляет данные о скалировании заговоров."""
    logger.info("Добавление данных о скалировании заговоров...")
    
    # Получаем ID добавленных заговоров
    cursor.execute("SELECT id, name, base_scaling_info FROM spells WHERE level = 0")
    spell_data = cursor.fetchall()
    
    scaling_data = []
    
    for spell_id, name, scaling_info_json in spell_data:
        if not scaling_info_json:
            continue
        
        scaling_info = json.loads(scaling_info_json)
        scaling_rules = scaling_info.get('description', '')
        
        # Находим соответствующий заговор из исходных данных
        original_cantrip = next((c for c in cantrips if c['Русское название'] == name), None)
        if not original_cantrip:
            continue
        
        base_damage = parse_damage_dice(original_cantrip.get('Базовый урон'))
        if not base_damage:
            continue
        
        # Парсим правила скалирования для определения урона на разных уровнях
        if 'Мистический заряд' in name:
            # Особый случай - увеличивается количество лучей, а не урон
            scaling_data.extend([
                (spell_id, 1, '1d10', 1, None),
                (spell_id, 5, '1d10', 2, json.dumps({'description': '2 луча'}, ensure_ascii=False)),
                (spell_id, 11, '1d10', 3, json.dumps({'description': '3 луча'}, ensure_ascii=False)),
                (spell_id, 17, '1d10', 4, json.dumps({'description': '4 луча'}, ensure_ascii=False))
            ])
        elif 'Уход за умирающим' in name:
            # Особый случай - увеличивается дистанция
            scaling_data.extend([
                (spell_id, 1, None, None, json.dumps({'range': '5 футов'}, ensure_ascii=False)),
                (spell_id, 5, None, None, json.dumps({'range': '30 футов'}, ensure_ascii=False)),
                (spell_id, 11, None, None, json.dumps({'range': '60 футов'}, ensure_ascii=False)),
                (spell_id, 17, None, None, json.dumps({'range': '120 футов'}, ensure_ascii=False))
            ])
        elif 'урон увеличивается' in scaling_rules.lower() or 'урон оружия изменяется' in scaling_rules.lower():
            # Парсим уровни и соответствующий урон
            if 'Дубинка' in name:
                # Особый случай для дубинки
                scaling_data.extend([
                    (spell_id, 1, '1d8', None, None),
                    (spell_id, 5, '1d10', None, None),
                    (spell_id, 11, '1d12', None, None),
                    (spell_id, 17, '2d6', None, None)
                ])
            elif 'Погребальный звон' in name:
                # Особый случай - урон зависит от состояния цели
                scaling_data.extend([
                    (spell_id, 1, '1d8', None, json.dumps({'note': '1d12 против раненых'}, ensure_ascii=False)),
                    (spell_id, 5, '2d8', None, json.dumps({'note': '2d12 против раненых'}, ensure_ascii=False)),
                    (spell_id, 11, '3d8', None, json.dumps({'note': '3d12 против раненых'}, ensure_ascii=False)),
                    (spell_id, 17, '4d8', None, json.dumps({'note': '4d12 против раненых'}, ensure_ascii=False))
                ])
            elif 'Меткий удар' in name:
                # Особый случай - дополнительный урон излучением
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
    
    # Вставляем данные о скалировании
    if scaling_data:
        cursor.executemany("""
            INSERT INTO cantrip_scaling (spell_id, character_level, damage_dice, num_beams, other_effects)
            VALUES (%s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE 
                damage_dice = VALUES(damage_dice),
                num_beams = VALUES(num_beams),
                other_effects = VALUES(other_effects)
        """, scaling_data)
        logger.info(f"Добавлено {len(scaling_data)} записей о скалировании заговоров")

def verify_import(cursor):
    """Проверяет результаты импорта."""
    cursor.execute("SELECT COUNT(*) FROM spells WHERE level = 0")
    cantrip_count = cursor.fetchone()[0]
    logger.info(f"Всего заговоров в базе: {cantrip_count}")
    
    cursor.execute("SELECT COUNT(*) FROM cantrip_scaling")
    scaling_count = cursor.fetchone()[0]
    logger.info(f"Записей о скалировании: {scaling_count}")
    
    # Показываем примеры импортированных заговоров
    cursor.execute("""
        SELECT name, damage, damage_type, available_classes 
        FROM spells 
        WHERE level = 0 
        LIMIT 5
    """)
    
    logger.info("\nПримеры импортированных заговоров:")
    for name, damage, damage_type, classes in cursor.fetchall():
        classes_list = json.loads(classes) if classes else []
        logger.info(f"  - {name}: урон {damage} ({damage_type}), классы: {', '.join(classes_list[:3])}")

def main():
    """Основная функция."""
    conn = None
    cursor = None
    
    try:
        logger.info("Подключение к базе данных...")
        conn = connect_to_db()
        cursor = conn.cursor()
        
        logger.info("Загрузка заговоров из файла...")
        cantrips = load_cantrips_from_file()
        logger.info(f"Загружено {len(cantrips)} заговоров")
        
        logger.info("Очистка старых заговоров...")
        clear_old_cantrips(cursor)
        conn.commit()
        
        logger.info("Импорт новых заговоров...")
        import_cantrips(cursor, cantrips)
        conn.commit()
        
        logger.info("Добавление данных о скалировании...")
        add_cantrip_scaling_data(cursor, cantrips)
        conn.commit()
        
        logger.info("Проверка результатов импорта...")
        verify_import(cursor)
        
        logger.info("\n✅ Импорт заговоров успешно завершен!")
        
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
