#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Скрипт для добавления столбца saving_throw в таблицу spells
и заполнения его для заклинаний, требующих спасброска
"""

import logging
from database import DatabaseManager

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def add_saving_throw_column():
    """Добавляет столбец saving_throw в таблицу spells"""
    
    db = DatabaseManager()
    
    try:
        # Подключаемся к базе данных
        db.connect()
        
        # Проверяем, существует ли уже столбец
        columns = db.execute_query("""
            SELECT COLUMN_NAME 
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_SCHEMA = 'dnd_bot' 
            AND TABLE_NAME = 'spells' 
            AND COLUMN_NAME = 'saving_throw'
        """)
        
        if columns:
            logger.info("Столбец saving_throw уже существует в таблице spells")
        else:
            # Добавляем столбец saving_throw
            logger.info("Добавляем столбец saving_throw в таблицу spells...")
            db.execute_query("""
                ALTER TABLE spells 
                ADD COLUMN saving_throw VARCHAR(20) DEFAULT NULL
                COMMENT 'Тип спасброска: Сила, Ловкость, Телосложение, Интеллект, Мудрость, Харизма'
            """)
            logger.info("Столбец saving_throw успешно добавлен")
        
        # Обновляем данные заклинаний с информацией о спасбросках
        update_saving_throws(db)
        
        # Проверяем результат
        verify_saving_throws(db)
        
    except Exception as e:
        logger.error(f"Ошибка при добавлении столбца: {e}")
        return False
    
    finally:
        db.disconnect()
    
    return True

def update_saving_throws(db):
    """Обновляет информацию о спасбросках для существующих заклинаний"""
    
    logger.info("Обновляем информацию о спасбросках для заклинаний...")
    
    # Словарь с заклинаниями и их спасбросками
    # Формат: (название заклинания, тип спасброска)
    spell_saving_throws = [
        # Заговоры
        ("Священное пламя", "Ловкость"),
        ("Сглаз", "Мудрость"),
        
        # 1 уровень
        ("Жгучие руки", "Ловкость"),
        ("Громовая волна", "Телосложение"),
        ("Сон", "Мудрость"),
        
        # 2 уровень
        ("Огненный шар", "Ловкость"),
        
        # 3 уровень
        ("Молния", "Ловкость"),
    ]
    
    updated_count = 0
    
    for spell_name, saving_throw in spell_saving_throws:
        result = db.execute_query("""
            UPDATE spells 
            SET saving_throw = %s 
            WHERE name = %s
        """, (saving_throw, spell_name))
        
        if result:
            logger.info(f"Обновлено заклинание '{spell_name}' - спасбросок: {saving_throw}")
            updated_count += 1
    
    logger.info(f"Обновлено {updated_count} заклинаний с информацией о спасбросках")
    
    # Также добавим некоторые новые заклинания с спасбросками для разнообразия
    new_spells_with_saves = [
        # Заговоры с спасбросками
        (0, "Брызги яда", "1d12", "яд", "Ядовитая атака по одной цели", True, False, 
         '["Чародей", "Волшебник"]', "Телосложение"),
        (0, "Порыв грома", "1d6", "громовой", "Отталкивает врага громом", True, False,
         '["Бард", "Друид", "Чародей", "Волшебник"]', "Телосложение"),
        
        # 1 уровень
        (1, "Очарование личности", None, None, "Очаровывает гуманоида", False, False,
         '["Бард", "Друид", "Чародей", "Колдун", "Волшебник"]', "Мудрость"),
        (1, "Огненная струя", "1d6", "огонь", "Линия огня длиной 15 футов", True, True,
         '["Чародей", "Волшебник"]', "Ловкость"),
        (1, "Туманное облако", None, None, "Создает область тумана", False, True,
         '["Друид", "Следопыт", "Чародей", "Волшебник"]', None),
        
        # 2 уровень  
        (2, "Удержание личности", None, None, "Парализует гуманоида", False, False,
         '["Бард", "Жрец", "Друид", "Чародей", "Колдун", "Волшебник"]', "Мудрость"),
        (2, "Раскаленный металл", "2d8", "огонь", "Нагревает металлический предмет", True, False,
         '["Бард", "Друид"]', "Телосложение"),
        (2, "Опутывание", None, None, "Удерживает существо на месте", False, False,
         '["Друид", "Следопыт"]', "Сила"),
        
        # 3 уровень
        (3, "Контрзаклинание", None, None, "Отменяет заклинание противника", False, False,
         '["Чародей", "Колдун", "Волшебник"]', None),
        (3, "Страх", None, None, "Пугает существ в конусе", False, True,
         '["Бард", "Чародей", "Колдун", "Волшебник"]', "Мудрость"),
        (3, "Замедление", None, None, "Замедляет до 6 существ", False, True,
         '["Чародей", "Волшебник"]', "Мудрость"),
    ]
    
    logger.info("Добавляем новые заклинания с спасбросками...")
    
    for spell_data in new_spells_with_saves:
        level, name, damage, damage_type, description, is_combat, is_area, classes, saving_throw = spell_data
        
        # Проверяем, существует ли уже такое заклинание
        existing = db.execute_query("SELECT id FROM spells WHERE name = %s", (name,))
        
        if not existing:
            db.execute_query("""
                INSERT INTO spells 
                (level, name, damage, damage_type, description, is_combat, is_area_of_effect, available_classes, saving_throw)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (level, name, damage, damage_type, description, is_combat, is_area, classes, saving_throw))
            
            logger.info(f"Добавлено новое заклинание: {name} (спасбросок: {saving_throw if saving_throw else 'нет'})")

def verify_saving_throws(db):
    """Проверяет, что спасброски были успешно добавлены"""
    
    logger.info("\nПроверка добавленных спасбросков...")
    
    # Получаем все заклинания со спасбросками
    spells_with_saves = db.execute_query("""
        SELECT name, level, saving_throw, is_combat, is_area_of_effect
        FROM spells 
        WHERE saving_throw IS NOT NULL
        ORDER BY level, name
    """)
    
    if spells_with_saves:
        logger.info(f"Найдено {len(spells_with_saves)} заклинаний со спасбросками:")
        
        current_level = -1
        for spell in spells_with_saves:
            if spell['level'] != current_level:
                current_level = spell['level']
                level_name = "Заговоры" if current_level == 0 else f"{current_level} уровень"
                logger.info(f"\n{level_name}:")
            
            combat_flag = "⚔️" if spell['is_combat'] else ""
            aoe_flag = "💥" if spell['is_area_of_effect'] else ""
            logger.info(f"  - {spell['name']}: {spell['saving_throw']} {combat_flag}{aoe_flag}")
    else:
        logger.warning("Не найдено заклинаний со спасбросками")
    
    # Показываем общую статистику
    total_spells = db.execute_query("SELECT COUNT(*) as count FROM spells")[0]['count']
    combat_spells = db.execute_query("SELECT COUNT(*) as count FROM spells WHERE is_combat = TRUE")[0]['count']
    spells_with_saves_count = len(spells_with_saves) if spells_with_saves else 0
    
    logger.info(f"\n📊 Статистика:")
    logger.info(f"  Всего заклинаний: {total_spells}")
    logger.info(f"  Боевых заклинаний: {combat_spells}")
    logger.info(f"  Заклинаний со спасбросками: {spells_with_saves_count}")
    
    # Проверяем распределение по типам спасбросков
    save_types = db.execute_query("""
        SELECT saving_throw, COUNT(*) as count
        FROM spells
        WHERE saving_throw IS NOT NULL
        GROUP BY saving_throw
        ORDER BY count DESC
    """)
    
    if save_types:
        logger.info(f"\n📈 Распределение по типам спасбросков:")
        for save_type in save_types:
            logger.info(f"  {save_type['saving_throw']}: {save_type['count']} заклинаний")

def main():
    """Основная функция"""
    
    logger.info("=" * 60)
    logger.info("Начинаем добавление столбца saving_throw в таблицу spells")
    logger.info("=" * 60)
    
    if add_saving_throw_column():
        logger.info("\n✅ Столбец saving_throw успешно добавлен и заполнен!")
    else:
        logger.error("\n❌ Произошла ошибка при добавлении столбца")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())
