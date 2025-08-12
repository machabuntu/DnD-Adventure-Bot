#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Скрипт для создания таблиц системы достижений в базе данных.
"""

import mysql.connector
import logging
from config import DB_HOST, DB_USER, DB_PASSWORD, DB_NAME

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('create_achievements.log', encoding='utf-8'),
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

def create_achievements_tables(cursor):
    """Создает таблицы для системы достижений."""
    
    # Таблица с описанием достижений
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS achievements (
            id INT AUTO_INCREMENT PRIMARY KEY,
            code VARCHAR(100) UNIQUE NOT NULL COMMENT 'Уникальный код достижения',
            name VARCHAR(200) NOT NULL COMMENT 'Название достижения',
            description TEXT COMMENT 'Описание достижения',
            points INT NOT NULL DEFAULT 10 COMMENT 'Очки за достижение',
            category VARCHAR(50) COMMENT 'Категория достижения',
            icon VARCHAR(10) DEFAULT '🏆' COMMENT 'Эмодзи иконка',
            is_hidden BOOLEAN DEFAULT FALSE COMMENT 'Скрытое достижение',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        ) COMMENT='Справочник достижений'
    """)
    logger.info("Создана таблица achievements")
    
    # Таблица полученных достижений пользователями
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_achievements (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id BIGINT NOT NULL COMMENT 'ID пользователя Telegram',
            achievement_id INT NOT NULL,
            achieved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            character_name VARCHAR(100) COMMENT 'Имя персонажа при получении',
            details TEXT COMMENT 'Дополнительные детали получения',
            FOREIGN KEY (achievement_id) REFERENCES achievements(id) ON DELETE CASCADE,
            UNIQUE KEY unique_user_achievement (user_id, achievement_id),
            INDEX idx_user_id (user_id),
            INDEX idx_achieved_at (achieved_at)
        ) COMMENT='Достижения пользователей'
    """)
    logger.info("Создана таблица user_achievements")
    
    # Таблица для отслеживания прогресса к достижениям
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS achievement_progress (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id BIGINT NOT NULL,
            achievement_code VARCHAR(100) NOT NULL,
            progress INT DEFAULT 0,
            target INT DEFAULT 1,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            UNIQUE KEY unique_user_progress (user_id, achievement_code),
            INDEX idx_user_progress (user_id)
        ) COMMENT='Прогресс к достижениям'
    """)
    logger.info("Создана таблица achievement_progress")

def populate_achievements(cursor):
    """Заполняет таблицу достижениями."""
    
    achievements_data = [
        # Достижения за уровни (20 достижений)
        ('level_2', 'Первые шаги', 'Достигнуть 2-го уровня', 10, 'levels', '📈', False),
        ('level_3', 'Начинающий искатель', 'Достигнуть 3-го уровня', 15, 'levels', '📈', False),
        ('level_4', 'Опытный путник', 'Достигнуть 4-го уровня', 20, 'levels', '📈', False),
        ('level_5', 'Закаленный воин', 'Достигнуть 5-го уровня', 30, 'levels', '⭐', False),
        ('level_6', 'Ветеран приключений', 'Достигнуть 6-го уровня', 35, 'levels', '⭐', False),
        ('level_7', 'Герой таверн', 'Достигнуть 7-го уровня', 40, 'levels', '⭐', False),
        ('level_8', 'Гроза подземелий', 'Достигнуть 8-го уровня', 45, 'levels', '🌟', False),
        ('level_9', 'Мастер клинка и магии', 'Достигнуть 9-го уровня', 50, 'levels', '🌟', False),
        ('level_10', 'Легенда становится', 'Достигнуть 10-го уровня', 60, 'levels', '✨', False),
        ('level_11', 'За гранью возможного', 'Достигнуть 11-го уровня', 70, 'levels', '✨', False),
        ('level_12', 'Избранный судьбой', 'Достигнуть 12-го уровня', 80, 'levels', '💫', False),
        ('level_13', 'Мифический герой', 'Достигнуть 13-го уровня', 90, 'levels', '💫', False),
        ('level_14', 'Сила стихий', 'Достигнуть 14-го уровня', 100, 'levels', '🌠', False),
        ('level_15', 'Полубог', 'Достигнуть 15-го уровня', 120, 'levels', '🌠', False),
        ('level_16', 'Воплощение силы', 'Достигнуть 16-го уровня', 140, 'levels', '⚡', False),
        ('level_17', 'Разрушитель миров', 'Достигнуть 17-го уровня', 160, 'levels', '⚡', False),
        ('level_18', 'Покоритель судьбы', 'Достигнуть 18-го уровня', 180, 'levels', '🔥', False),
        ('level_19', 'На пороге божественности', 'Достигнуть 19-го уровня', 200, 'levels', '🔥', False),
        ('level_20', 'Живая легенда', 'Достигнуть максимального 20-го уровня', 250, 'levels', '👑', False),
        
        # Достижения за урон
        ('damage_30', 'Сокрушительный удар', 'Нанести 30+ урона одним действием', 25, 'combat', '💥', False),
        ('damage_50', 'Испепеляющая мощь', 'Нанести 50+ урона одним действием', 50, 'combat', '🔥', False),
        ('damage_100', 'Апокалипсис в миниатюре', 'Нанести 100+ урона одним действием', 100, 'combat', '☄️', True),
        
        # Достижения за массовые убийства
        ('multikill_3', 'Тройное убийство', 'Убить 3 врагов одним действием', 40, 'combat', '⚔️', False),
        ('multikill_5', 'Пентакилл', 'Убить 5 врагов одним действием', 80, 'combat', '🗡️', True),
        
        # Достижения за максимальные характеристики
        ('max_strength', 'Сила титана', 'Довести Силу до 20', 50, 'stats', '💪', False),
        ('max_dexterity', 'Грация кошки', 'Довести Ловкость до 20', 50, 'stats', '🏃', False),
        ('max_constitution', 'Несокрушимый', 'Довести Телосложение до 20', 50, 'stats', '🛡️', False),
        ('max_intelligence', 'Гений', 'Довести Интеллект до 20', 50, 'stats', '🧠', False),
        ('max_wisdom', 'Мудрец', 'Довести Мудрость до 20', 50, 'stats', '🦉', False),
        ('max_charisma', 'Харизматичный лидер', 'Довести Харизму до 20', 50, 'stats', '👑', False),
        
        # Достижение за смерть
        ('character_death', 'Героическая смерть', 'Погибнуть в бою', 25, 'special', '💀', False),
        
        # Достижение за броню
        ('armor_class_20', 'Неприступная крепость', 'Иметь класс доспехов 20 или выше', 40, 'defense', '🏰', False),
        
        # Достижения за низкие характеристики
        ('dump_strength', 'Хилый', 'Создать персонажа с Силой ниже 5', 15, 'funny', '🦴', True),
        ('dump_dexterity', 'Неуклюжий', 'Создать персонажа с Ловкостью ниже 5', 15, 'funny', '🦥', True),
        ('dump_constitution', 'Хрупкий', 'Создать персонажа с Телосложением ниже 5', 15, 'funny', '🍃', True),
        ('dump_intelligence', 'Простодушный', 'Создать персонажа с Интеллектом ниже 5', 15, 'funny', '🪨', True),
        ('dump_wisdom', 'Наивный', 'Создать персонажа с Мудростью ниже 5', 15, 'funny', '🙈', True),
        ('dump_charisma', 'Отталкивающий', 'Создать персонажа с Харизмой ниже 5', 15, 'funny', '🦨', True),
        
        # Дополнительные интересные достижения
        ('first_character', 'Добро пожаловать!', 'Создать первого персонажа', 5, 'special', '👋', False),
        ('first_kill', 'Первая кровь', 'Убить первого врага', 10, 'combat', '🗡️', False),
        ('first_spell', 'Начинающий маг', 'Использовать первое заклинание', 10, 'magic', '✨', False),
        ('critical_hit', 'Критический успех!', 'Нанести критический удар', 15, 'combat', '🎯', False),
        ('critical_miss', 'Эпический провал', 'Критически промахнуться', 10, 'funny', '😅', True),
        ('survivor', 'Выживший', 'Выжить с 1 HP', 30, 'special', '🍀', True),
        ('glass_cannon', 'Стеклянная пушка', 'Иметь максимальную атаку и минимальную защиту', 25, 'funny', '💎', True),
        ('tank', 'Живой щит', 'Получить 100+ урона за одно приключение и выжить', 35, 'defense', '🛡️', True),
        ('pacifist', 'Пацифист', 'Завершить бой без нанесения урона', 30, 'special', '☮️', True),
        ('speedrun', 'Скоростной забег', 'Победить врага за один ход', 20, 'combat', '⚡', False),
        ('unlucky', 'Невезучий', 'Выбросить 1 на d20 три раза подряд', 25, 'funny', '🎲', True),
        ('lucky', 'Везунчик', 'Выбросить 20 на d20 три раза подряд', 50, 'special', '🍀', True),
    ]
    
    insert_query = """
        INSERT INTO achievements (code, name, description, points, category, icon, is_hidden)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            name = VALUES(name),
            description = VALUES(description),
            points = VALUES(points),
            category = VALUES(category),
            icon = VALUES(icon),
            is_hidden = VALUES(is_hidden)
    """
    
    cursor.executemany(insert_query, achievements_data)
    logger.info(f"Добавлено {len(achievements_data)} достижений")

def main():
    """Основная функция."""
    conn = None
    cursor = None
    
    try:
        logger.info("Подключение к базе данных...")
        conn = connect_to_db()
        cursor = conn.cursor()
        
        logger.info("Создание таблиц для системы достижений...")
        create_achievements_tables(cursor)
        conn.commit()
        
        logger.info("Заполнение таблицы достижениями...")
        populate_achievements(cursor)
        conn.commit()
        
        # Проверка результатов
        cursor.execute("SELECT COUNT(*) FROM achievements")
        count = cursor.fetchone()[0]
        logger.info(f"Всего достижений в базе: {count}")
        
        cursor.execute("SELECT category, COUNT(*) as cnt FROM achievements GROUP BY category")
        for category, cnt in cursor.fetchall():
            logger.info(f"  Категория '{category}': {cnt} достижений")
        
        logger.info("\n✅ Система достижений успешно создана!")
        
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
