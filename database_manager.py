#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Единый менеджер для управления базой данных DnD бота
Включает в себя:
- Создание базы данных и схемы
- Заполнение базовыми данными
- Обновление системы заклинаний
- Инициализацию слотов заклинаний
"""

import json
import mysql.connector
from mysql.connector import Error
import logging
from config import DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class DatabaseSetupManager:
    def __init__(self):
        self.connection = None
        self.cursor = None
    
    def connect(self):
        """Establish connection to MySQL database"""
        try:
            self.connection = mysql.connector.connect(
                host=DB_HOST,
                port=DB_PORT,
                user=DB_USER,
                password=DB_PASSWORD,
                database=DB_NAME,
                charset='utf8mb4',
                collation='utf8mb4_unicode_ci'
            )
            self.cursor = self.connection.cursor(dictionary=True)
            logger.info("Successfully connected to database")
            return True
        except Error as e:
            logger.error(f"Error connecting to database: {e}")
            return False
    
    def disconnect(self):
        """Close database connection"""
        if self.cursor:
            self.cursor.close()
        if self.connection and self.connection.is_connected():
            self.connection.close()
            logger.info("Database connection closed")
    
    def execute_query(self, query, params=None):
        """Execute a query and return results"""
        try:
            if not self.connection or not self.connection.is_connected():
                self.connect()
            
            self.cursor.execute(query, params or ())
            
            if query.strip().upper().startswith(('INSERT', 'UPDATE', 'DELETE')):
                self.connection.commit()
                return self.cursor.rowcount
            else:
                return self.cursor.fetchall()
                
        except Error as e:
            logger.error(f"Error executing query: {e}")
            if self.connection:
                self.connection.rollback()
            return None
    
    def execute_many(self, query, params_list):
        """Execute a query with multiple parameter sets"""
        try:
            if not self.connection or not self.connection.is_connected():
                self.connect()
            
            self.cursor.executemany(query, params_list)
            self.connection.commit()
            return self.cursor.rowcount
            
        except Error as e:
            logger.error(f"Error executing many queries: {e}")
            if self.connection:
                self.connection.rollback()
            return None

    def create_database_if_not_exists(self):
        """Create the dnd_bot database if it doesn't exist"""
        try:
            # Connect to MySQL server without specifying database
            connection = mysql.connector.connect(
                host=DB_HOST,
                port=DB_PORT,
                user=DB_USER,
                password=DB_PASSWORD,
                charset='utf8mb4',
                collation='utf8mb4_unicode_ci'
            )
            
            cursor = connection.cursor()
            
            # Create database if it doesn't exist
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS {DB_NAME} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
            logger.info(f"Database '{DB_NAME}' created successfully or already exists")
            
            cursor.close()
            connection.close()
            
            return True
            
        except Error as e:
            logger.error(f"Error creating database: {e}")
            return False

    def init_database_schema(self):
        """Initialize database schema"""
        
        logger.info("Initializing database schema...")
        
        # Drop and recreate tables if they exist
        # Note: spells table is managed by import_cantrips_from_json.py and import_spells_from_json.py
        drop_tables = [
            "DROP TABLE IF EXISTS adventure_participants",
            "DROP TABLE IF EXISTS character_spell_slots",
            "DROP TABLE IF EXISTS character_spells",
            "DROP TABLE IF EXISTS character_skills",
            "DROP TABLE IF EXISTS character_equipment",
            "DROP TABLE IF EXISTS combat_participants",
            "DROP TABLE IF EXISTS enemy_attacks",
            "DROP TABLE IF EXISTS enemies",
            "DROP TABLE IF EXISTS adventure_messages",
            "DROP TABLE IF EXISTS chat_history",
            "DROP TABLE IF EXISTS characters",
            "DROP TABLE IF EXISTS adventures",
            "DROP TABLE IF EXISTS class_spell_slots",
            "DROP TABLE IF EXISTS weapons",
            "DROP TABLE IF EXISTS armor",
            "DROP TABLE IF EXISTS classes",
            "DROP TABLE IF EXISTS races",
            "DROP TABLE IF EXISTS origins",
            "DROP TABLE IF EXISTS levels"
        ]
        
        for drop_query in drop_tables:
            self.execute_query(drop_query)
        
        # Create tables
        create_tables = [
            # Levels table
            """
            CREATE TABLE levels (
                level INT PRIMARY KEY,
                experience_required INT NOT NULL,
                proficiency_bonus INT NOT NULL
            )
            """,
            
            # Origins table
            """
            CREATE TABLE origins (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(100) NOT NULL UNIQUE,
                stat_bonuses TEXT,  -- JSON format: {"str": 2, "dex": 1} or similar
                skills TEXT,        -- JSON format: ["skill1", "skill2"]
                starting_money INT DEFAULT 100
            )
            """,
            
            # Races table
            """
            CREATE TABLE races (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(100) NOT NULL UNIQUE
            )
            """,
            
            # Armor table
            """
            CREATE TABLE armor (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                armor_class VARCHAR(50),  -- e.g., "14 + Dex (max 2)"
                strength_requirement INT DEFAULT 0,
                weight DECIMAL(5,2) DEFAULT 0,
                price INT DEFAULT 0,
                armor_type VARCHAR(20) DEFAULT 'легкий'  -- легкий, средний, тяжелый, щит
            )
            """,
            
            # Weapons table
            """
            CREATE TABLE weapons (
                id INT AUTO_INCREMENT PRIMARY KEY,
                weapon_type VARCHAR(50),  -- простое, воинское, etc.
                name VARCHAR(100) NOT NULL,
                damage VARCHAR(20),       -- e.g., "1d8"
                damage_type VARCHAR(20),  -- e.g., "слэшинг"
                properties TEXT,          -- JSON format
                grip_type VARCHAR(20),    -- одноручное, двуручное, etc.
                weight DECIMAL(5,2) DEFAULT 0,
                price INT DEFAULT 0,
                technique VARCHAR(50)     -- техника атаки
            )
            """,
            
            # Classes table
            """
            CREATE TABLE classes (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(100) NOT NULL UNIQUE,
                primary_stat VARCHAR(20),
                hit_die INT DEFAULT 8,
                weapon_proficiency TEXT,  -- JSON format
                armor_proficiency TEXT,   -- JSON format
                skills_available TEXT,    -- JSON format: ["skill1", "skill2", ...]
                skills_count INT DEFAULT 2,
                starting_money INT DEFAULT 100,
                is_spellcaster BOOLEAN DEFAULT FALSE,
                spellcasting_ability VARCHAR(20) DEFAULT NULL  -- Intelligence, Wisdom, or Charisma
            )
            """,
            
            # Note: Spells table is created and managed by import_cantrips_from_json.py and import_spells_from_json.py
            
            # Class spell slots table
            """
            CREATE TABLE class_spell_slots (
                id INT AUTO_INCREMENT PRIMARY KEY,
                class_id INT,
                level INT,
                slot_level_1 INT DEFAULT 0,
                slot_level_2 INT DEFAULT 0,
                slot_level_3 INT DEFAULT 0,
                slot_level_4 INT DEFAULT 0,
                slot_level_5 INT DEFAULT 0,
                slot_level_6 INT DEFAULT 0,
                slot_level_7 INT DEFAULT 0,
                slot_level_8 INT DEFAULT 0,
                slot_level_9 INT DEFAULT 0,
                known_spells INT DEFAULT 0,
                known_cantrips INT DEFAULT 0,
                FOREIGN KEY (class_id) REFERENCES classes(id) ON DELETE CASCADE
            )
            """,
            
            # Characters table
            """
            CREATE TABLE characters (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id BIGINT NOT NULL,
                name VARCHAR(100) NOT NULL,
                race_id INT,
                class_id INT,
                origin_id INT,
                level INT DEFAULT 1,
                experience INT DEFAULT 0,
                max_hp INT,
                current_hp INT,
                armor_class INT DEFAULT 10,
                strength INT DEFAULT 8,
                dexterity INT DEFAULT 8,
                constitution INT DEFAULT 8,
                intelligence INT DEFAULT 8,
                wisdom INT DEFAULT 8,
                charisma INT DEFAULT 8,
                equipment TEXT,  -- JSON format
                money INT DEFAULT 0,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (race_id) REFERENCES races(id),
                FOREIGN KEY (class_id) REFERENCES classes(id),
                FOREIGN KEY (origin_id) REFERENCES origins(id)
            )
            """,
            
            # Character spell slots table
            """
            CREATE TABLE character_spell_slots (
                id INT AUTO_INCREMENT PRIMARY KEY,
                character_id INT NOT NULL,
                slot_level INT NOT NULL,
                max_slots INT NOT NULL,
                used_slots INT DEFAULT 0,
                FOREIGN KEY (character_id) REFERENCES characters(id) ON DELETE CASCADE,
                UNIQUE KEY unique_char_slot_level (character_id, slot_level)
            )
            """,
            
            # Character spells table
            """
            CREATE TABLE character_spells (
                id INT AUTO_INCREMENT PRIMARY KEY,
                character_id INT,
                spell_id INT,
                FOREIGN KEY (character_id) REFERENCES characters(id) ON DELETE CASCADE,
                FOREIGN KEY (spell_id) REFERENCES spells(id) ON DELETE CASCADE,
                UNIQUE KEY unique_char_spell (character_id, spell_id)
            )
            """,
            
            # Character skills table
            """
            CREATE TABLE character_skills (
                id INT AUTO_INCREMENT PRIMARY KEY,
                character_id INT,
                skill_name VARCHAR(100),
                FOREIGN KEY (character_id) REFERENCES characters(id) ON DELETE CASCADE
            )
            """,
            
            # Character equipment table
            """
            CREATE TABLE character_equipment (
                id INT AUTO_INCREMENT PRIMARY KEY,
                character_id INT,
                item_type VARCHAR(50),  -- 'weapon', 'armor'
                item_id INT,
                is_equipped BOOLEAN DEFAULT FALSE,
                quantity INT DEFAULT 1,
                FOREIGN KEY (character_id) REFERENCES characters(id) ON DELETE CASCADE
            )
            """,
            
            # Adventures table
            """
            CREATE TABLE adventures (
                id INT AUTO_INCREMENT PRIMARY KEY,
                chat_id BIGINT NOT NULL,
                status VARCHAR(20) DEFAULT 'active',  -- active, completed, paused
                description TEXT,
                current_scene TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,
            
            # Adventure participants table
            """
            CREATE TABLE adventure_participants (
                id INT AUTO_INCREMENT PRIMARY KEY,
                adventure_id INT,
                character_id INT,
                FOREIGN KEY (adventure_id) REFERENCES adventures(id) ON DELETE CASCADE,
                FOREIGN KEY (character_id) REFERENCES characters(id) ON DELETE CASCADE
            )
            """,
            
            # Enemies table
            """
            CREATE TABLE enemies (
                id INT AUTO_INCREMENT PRIMARY KEY,
                adventure_id INT,
                name VARCHAR(100),
                hit_points INT,
                max_hit_points INT,
                armor_class INT,
                strength INT DEFAULT 10,
                dexterity INT DEFAULT 10,
                constitution INT DEFAULT 10,
                intelligence INT DEFAULT 10,
                wisdom INT DEFAULT 10,
                charisma INT DEFAULT 10,
                xp INT DEFAULT 0,
                FOREIGN KEY (adventure_id) REFERENCES adventures(id) ON DELETE CASCADE
            )
            """,
            
            # Enemy attacks table
            """
            CREATE TABLE enemy_attacks (
                id INT AUTO_INCREMENT PRIMARY KEY,
                enemy_id INT,
                name VARCHAR(100),
                damage VARCHAR(50),
                damage_type VARCHAR(50),
                attack_bonus INT DEFAULT 0,
                description TEXT,
                FOREIGN KEY (enemy_id) REFERENCES enemies(id) ON DELETE CASCADE
            )
            """,
            
            # Combat participants table
            """
            CREATE TABLE combat_participants (
                id INT AUTO_INCREMENT PRIMARY KEY,
                adventure_id INT,
                participant_type VARCHAR(20),  -- 'character' or 'enemy'
                participant_id INT,  -- character_id or enemy_id
                initiative INT,
                turn_order INT,
                FOREIGN KEY (adventure_id) REFERENCES adventures(id) ON DELETE CASCADE
            )
            """,
            
            # Adventure messages table (for Grok API history)
            """
            CREATE TABLE adventure_messages (
                id INT AUTO_INCREMENT PRIMARY KEY,
                adventure_id INT,
                role VARCHAR(20),  -- 'system', 'user', 'assistant'
                content TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (adventure_id) REFERENCES adventures(id) ON DELETE CASCADE
            )
            """,
            
            # Chat history table
            """
            CREATE TABLE chat_history (
                id INT AUTO_INCREMENT PRIMARY KEY,
                adventure_id INT,
                role VARCHAR(20),  -- 'system', 'user', 'assistant'
                content TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (adventure_id) REFERENCES adventures(id) ON DELETE CASCADE
            )
            """
        ]
        
        # Execute table creation
        for create_query in create_tables:
            result = self.execute_query(create_query)
            if result is None:
                logger.error(f"Failed to create table with query: {create_query[:50]}...")
                return False
        
        logger.info("Database schema initialized successfully")
        return True

    def populate_initial_data(self):
        """Populate database with initial game data"""
        
        logger.info("Populating database with initial data...")
        
        # Clear existing data in correct order
        tables_to_clear = [
            "class_spell_slots",
            "character_equipment", 
            "character_spells",
            "weapons",
            "armor",
            "origins", 
            "classes",
            "races",
            "levels"
        ]
        
        for table in tables_to_clear:
            result = self.execute_query(f"DELETE FROM {table}")
            logger.info(f"Cleared table {table}: {result} rows deleted")
        
        # Insert levels data
        levels_data = [
            (1, 0, 2), (2, 300, 2), (3, 900, 2), (4, 2700, 2), (5, 6500, 3),
            (6, 14000, 3), (7, 23000, 3), (8, 34000, 3), (9, 48000, 4),
            (10, 64000, 4), (11, 85000, 4), (12, 100000, 4), (13, 120000, 5),
            (14, 140000, 5), (15, 165000, 5), (16, 195000, 5), (17, 225000, 6),
            (18, 265000, 6), (19, 305000, 6), (20, 355000, 6)
        ]
        
        self.execute_many(
            "INSERT INTO levels (level, experience_required, proficiency_bonus) VALUES (%s, %s, %s)",
            levels_data
        )
        logger.info(f"Added {len(levels_data)} levels")
        
        # Insert races data
        races_data = [
            ("Человек",), ("Эльф",), ("Дварф",), ("Полурослик",), ("Драконорожденный",),
            ("Гном",), ("Полуэльф",), ("Полуорк",), ("Тифлинг",), ("Орк",),
            ("Аасимар",), ("Гоблин",), ("Голиаф",), ("Фирболг",), ("Табакси",)
        ]
        
        for race_data in races_data:
            self.execute_query("INSERT INTO races (name) VALUES (%s)", race_data)
        logger.info(f"Added {len(races_data)} races")
        
        # Insert origins data
        origins_data = [
            ("Артист", '{"str": 0, "dex": 0, "cha": 0}', '["Акробатика", "Выступление"]', 5000),
            ("Благородный", '{"str": 0, "int": 0, "cha": 0}', '["История", "Убеждение"]', 5000),
            ("Моряк", '{"str": 0, "dex": 0, "wis": 0}', '["Акробатика", "Внимательность"]', 5000),
            ("Мудрец", '{"con": 0, "int": 0, "wis": 0}', '["Аркана", "История"]', 5000),
            ("Отшельник", '{"con": 0, "wis": 0, "cha": 0}', '["Медицина", "Религия"]', 5000),
            ("Преступник", '{"dex": 0, "int": 0, "cha": 0}', '["Обман", "Скрытность"]', 5000),
            ("Народный герой", '{"str": 0, "con": 0, "wis": 0}', '["Выживание", "Обращение с животными"]', 5000),
            ("Солдат", '{"str": 0, "con": 0, "cha": 0}', '["Атлетика", "Запугивание"]', 5000),
            ("Аколит", '{"int": 0, "wis": 0, "cha": 0}', '["Проницательность", "Религия"]', 5000),
            ("Алхимик", '{"con": 0, "int": 0, "wis": 0}', '["Аркана", "Медицина"]', 5000),
        ]
        
        for origin_data in origins_data:
            self.execute_query(
                "INSERT INTO origins (name, stat_bonuses, skills, starting_money) VALUES (%s, %s, %s, %s)",
                origin_data
            )
        logger.info(f"Added {len(origins_data)} origins")
        
        # Insert classes data with spellcasting abilities
        classes_data = [
            # name, primary_stat, hit_die, weapon_prof, armor_prof, skills, skill_count, money, is_spellcaster, spellcasting_ability
            ("Варвар", "Сила", 12, '["простое", "воинское"]', '["легкие", "средние", "щиты"]', '["Уход за животными", "Атлетика", "Природа", "Запугивание", "Внимательность", "Выживание"]', 2, 7500, False, None),
            ("Бард", "Харизма", 8, '["простое"]', '["легкие"]', '["Атлетика", "Акробатика", "Анализ", "Аркана", "Внимание", "Выживание", "Выступление", "Запугивание", "История", "Ловкость Рук", "Обман", "Медицина", "Природа", "Проницательность", "Религия", "Скрытность", "Убеждение", "Уход за животными"]', 3, 7500, True, "Харизма"),
            ("Жрец", "Мудрость", 8, '["простое"]', '["легкие", "средние", "щиты"]', '["История", "Проницательность", "Медицина", "Убеждение", "Религия"]', 2, 11000, True, "Мудрость"),
            ("Друид", "Мудрость", 8, '["простое"]', '["легкие", "щиты"]', '["Аркана", "Уход за животными", "Проницательность", "Медицина", "Природа", "Внимательность", "Религия", "Выживание"]', 2, 5000, True, "Мудрость"),
            ("Воин", "Сила", 10, '["простое", "воинское"]', '["все", "щиты"]', '["Акробатика", "Атлетика", "Внимательность", "Выживание", "Запугивание", "История", "Проницательность", "Убеждение", "Уход за животными"]', 2, 15500, False, None),
            ("Монах", "Ловкость", 8, '["простое", "короткие мечи"]', '[]', '["Акробатика", "Атлетика", "История", "Проницательность", "Религия", "Скрытность"]', 2, 5000, False, None),
            ("Паладин", "Сила", 10, '["простое", "воинское"]', '["все", "щиты"]', '["Атлетика", "Проницательность", "Запугивание", "Медицина", "Убеждение", "Религия"]', 2, 15000, True, "Харизма"),
            ("Следопыт", "Ловкость", 10, '["простое", "воинское"]', '["легкие", "средние", "щиты"]', '["Уход за животными", "Атлетика", "Проницательность", "Анализ", "Природа", "Внимательность", "Скрытность", "Выживание"]', 3, 15000, True, "Мудрость"),
            ("Плут", "Ловкость", 8, '["простое", "воинское со свойством фехтовальное или легкое"]', '["легкие"]', '["Акробатика", "Атлетика", "Обман", "Проницательность", "Запугивание", "Анализ", "Внимательность", "Убеждение", "Ловкость рук", "Скрытность"]', 4, 10000, False, None),
            ("Чародей", "Харизма", 6, '["простое"]', '["легкие"]', '["Аркана", "Обман", "Проницательность", "Запугивание", "Убеждение", "Религия"]', 2, 5000, True, "Харизма"),
            ("Колдун", "Харизма", 8, '["простое"]', '["легкие"]', '["Аркана", "Обман", "История", "Запугивание", "Анализ", "Природа", "Религия"]', 2, 10000, True, "Харизма"),
            ("Волшебник", "Интеллект", 6, '["простое"]', '[]', '["Аркана", "История", "Проницательность", "Анализ", "Медицина", "Религия"]', 2, 5500, True, "Интеллект")
        ]
        
        for class_data in classes_data:
            self.execute_query(
                "INSERT INTO classes (name, primary_stat, hit_die, weapon_proficiency, armor_proficiency, skills_available, skills_count, starting_money, is_spellcaster, spellcasting_ability) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                class_data
            )
        logger.info(f"Added {len(classes_data)} classes")
        
        # Insert weapons data
        weapons_data = [
            # Простое рукопашное оружие
            ("Простое", "Дубинка", "1d4", "дробящий", '["Лёгкое"]', "одноручное", 2.0, 10, "Нет"),
            ("Простое", "Кинжал", "1d4", "колющий", '["Фехтовальное", "Лёгкое", "Метательное"]', "одноручное", 1.0, 200, "Бросок"),
            ("Простое", "Палица", "1d8", "дробящий", '["Двуручное"]', "двуручное", 10.0, 20, "Удар"),
            ("Простое", "Ручной топор", "1d6", "рубящий", '["Лёгкое", "Метательное"]', "одноручное", 2.0, 500, "Размах"),
            ("Простое", "Метательное копьё", "1d6", "колющий", '["Метательное"]', "одноручное", 2.0, 50, "Метнуть"),
            ("Простое", "Лёгкий молот", "1d4", "дробящий", '["Лёгкое", "Метательное"]', "одноручное", 2.0, 200, "Бросок"),
            ("Простое", "Булава", "1d6", "дробящий", '[]', "одноручное", 4.0, 500, "Удар"),
            ("Простое", "Боевой посох", "1d6", "дробящий", '["Универсальное (1d8)"]', "одноручное", 4.0, 20, "Удар"),
            ("Простое", "Серп", "1d4", "рубящий", '["Лёгкое"]', "одноручное", 2.0, 100, "Кривой удар"),
            ("Простое", "Копьё", "1d6", "колющий", '["Метательное", "Универсальное (1d8)"]', "одноручное", 3.0, 100, "Тычок"),
            
            # Простое дальнобойное оружие
            ("Простое", "Дротик", "1d4", "колющий", '["Фехтовальное", "Метательное"]', "одноручное", 0.25, 5, "Бросок"),
            ("Простое", "Лёгкий арбалет", "1d8", "колющий", '["Боеприпасы", "Перезарядка", "Двуручное"]', "двуручное", 5.0, 2500, "Выстрел"),
            ("Простое", "Короткий лук", "1d6", "колющий", '["Боеприпасы", "Двуручное"]', "двуручное", 2.0, 2500, "Выстрел"),
            ("Простое", "Праща", "1d4", "дробящий", '["Боеприпасы"]', "одноручное", 0.0, 10, "Бросок"),
            
            # Воинское рукопашное оружие
            ("Воинское", "Боевой топор", "1d8", "рубящий", '["Универсальное (1d10)"]', "одноручное", 4.0, 1000, "Размах"),
            ("Воинское", "Цеп", "1d8", "дробящий", '[]', "одноручное", 2.0, 1000, "Размах"),
            ("Воинское", "Глефа", "1d10", "рубящий", '["Тяжёлое", "Досягаемость", "Двуручное"]', "двуручное", 6.0, 2000, "Размах"),
            ("Воинское", "Секира", "1d12", "рубящий", '["Тяжёлое", "Двуручное"]', "двуручное", 7.0, 3000, "Размах"),
            ("Воинское", "Двуручный меч", "2d6", "рубящий", '["Тяжёлое", "Двуручное"]', "двуручное", 6.0, 5000, "Размах"),
            ("Воинское", "Алебарда", "1d10", "рубящий", '["Тяжёлое", "Досягаемость", "Двуручное"]', "двуручное", 6.0, 2000, "Размах"),
            ("Воинское", "Длинное копьё", "1d10", "колющий", '["Тяжёлое", "Досягаемость", "Двуручное"]', "двуручное", 6.0, 1000, "Тычок"),
            ("Воинское", "Длинный меч", "1d8", "рубящий", '["Универсальное (1d10)"]', "одноручное", 3.0, 1500, "Размах"),
            ("Воинское", "Молот", "1d8", "дробящий", '["Универсальное (1d10)"]', "одноручное", 2.0, 1500, "Удар"),
            ("Воинское", "Моргенштерн", "1d8", "колющий", '[]', "одноручное", 4.0, 1500, "Тычок"),
            ("Воинское", "Пика", "1d10", "колющий", '["Тяжёлое", "Досягаемость", "Двуручное"]', "двуручное", 18.0, 500, "Тычок"),
            ("Воинское", "Рапира", "1d8", "колющий", '["Фехтовальное"]', "одноручное", 2.0, 2500, "Тычок"),
            ("Воинское", "Скимитар", "1d6", "рубящий", '["Фехтовальное", "Лёгкое"]', "одноручное", 3.0, 2500, "Размах"),
            ("Воинское", "Короткий меч", "1d6", "колющий", '["Фехтовальное", "Лёгкое"]', "одноручное", 2.0, 1000, "Тычок"),
            ("Воинское", "Трезубец", "1d8", "колющий", '["Метательное", "Универсальное (1d10)"]', "одноручное", 4.0, 500, "Тычок"),
            ("Воинское", "Боевая кирка", "1d8", "колющий", '["Универсальное (1d10)"]', "одноручное", 2.0, 500, "Тычок"),
            ("Воинское", "Кнут", "1d4", "рубящий", '["Фехтовальное", "Досягаемость"]', "одноручное", 3.0, 200, "Хлестнуть"),
            
            # Воинское дальнобойное оружие
            ("Воинское", "Духовая трубка", "1", "колющий", '["Боеприпасы", "Лёгкое"]', "одноручное", 1.0, 1000, "Выстрел"),
            ("Воинское", "Ручной арбалет", "1d6", "колющий", '["Боеприпасы", "Лёгкое", "Лёгкое"]', "одноручное", 3.0, 7500, "Выстрел"),
            ("Воинское", "Тяжёлый арбалет", "1d10", "колющий", '["Боеприпасы", "Тяжёлое", "Перезарядка", "Двуручное"]', "двуручное", 18.0, 5000, "Выстрел"),
            ("Воинское", "Длинный лук", "1d8", "колющий", '["Боеприпасы", "Тяжёлое", "Двуручное"]', "двуручное", 2.0, 5000, "Выстрел"),
            ("Воинское", "Сеть", "0", "нет", '["Специальное", "Метательное"]', "одноручное", 3.0, 200, "Накинуть")
        ]
        
        for weapon in weapons_data:
            self.execute_query(
                "INSERT INTO weapons (weapon_type, name, damage, damage_type, properties, grip_type, weight, price, technique) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                weapon
            )
        logger.info(f"Added {len(weapons_data)} weapons")
        
        # Insert armor data
        armor_data = [
            # Легкие доспехи
            ("Стёганый доспех", "11 + Лов", 0, 8.0, 500, "легкий"),
            ("Кожаный доспех", "11 + Лов", 0, 10.0, 1000, "легкий"),
            ("Проклёпанная кожа", "12 + Лов", 0, 13.0, 4500, "легкий"),
            
            # Средние доспехи
            ("Шкурный доспех", "12 + Лов (макс 2)", 0, 12.0, 1000, "средний"),
            ("Кольчужная рубаха", "13 + Лов (макс 2)", 0, 20.0, 5000, "средний"),
            ("Чешуйчатый доспех", "14 + Лов (макс 2)", 0, 45.0, 5000, "средний"),
            ("Кираса", "14 + Лов (макс 2)", 0, 20.0, 40000, "средний"),
            ("Полулаты", "15 + Лов (макс 2)", 0, 40.0, 75000, "средний"),
            
            # Тяжелые доспехи
            ("Кольчатый доспех", "14", 0, 40.0, 3000, "тяжелый"),
            ("Кольчуга", "16", 13, 55.0, 7500, "тяжелый"),
            ("Наборный доспех", "17", 15, 60.0, 20000, "тяжелый"),
            ("Латы", "18", 15, 65.0, 150000, "тяжелый"),
            
            # Щит
            ("Щит", "+2", 0, 6.0, 1000, "щит")
        ]
        
        for armor in armor_data:
            self.execute_query(
                "INSERT INTO armor (name, armor_class, strength_requirement, weight, price, armor_type) VALUES (%s, %s, %s, %s, %s, %s)",
                armor
            )
        logger.info(f"Added {len(armor_data)} armor pieces")
        
        # Note: Spells are now imported using import_cantrips_from_json.py and import_spells_from_json.py
        # So we don't populate them here
        
        logger.info("Initial data population completed successfully")

    def setup_spell_slots_system(self):
        """Setup spell slots system for spellcasting classes"""
        
        logger.info("Setting up spell slots system...")
        
        # Get spellcaster classes
        classes = self.execute_query("SELECT id, name FROM classes WHERE is_spellcaster = TRUE")
        
        spell_slots_data = {
            "Бард": [
                (1, 2, 0, 0, 0, 0, 0, 0, 0, 0, 4, 2),
                (2, 3, 0, 0, 0, 0, 0, 0, 0, 0, 5, 2),
                (3, 4, 2, 0, 0, 0, 0, 0, 0, 0, 6, 2),
                (4, 4, 3, 0, 0, 0, 0, 0, 0, 0, 7, 3),
                (5, 4, 3, 2, 0, 0, 0, 0, 0, 0, 9, 3),
                (6, 4, 3, 3, 0, 0, 0, 0, 0, 0, 10, 3),
                (7, 4, 3, 3, 1, 0, 0, 0, 0, 0, 11, 3),
                (8, 4, 3, 3, 2, 0, 0, 0, 0, 0, 12, 3),
                (9, 4, 3, 3, 3, 1, 0, 0, 0, 0, 14, 3),
                (10, 4, 3, 3, 3, 2, 0, 0, 0, 0, 15, 4),
                (11, 4, 3, 3, 3, 2, 1, 0, 0, 0, 16, 4),
                (12, 4, 3, 3, 3, 2, 1, 0, 0, 0, 16, 4),
                (13, 4, 3, 3, 3, 2, 1, 1, 0, 0, 17, 4),
                (14, 4, 3, 3, 3, 2, 1, 1, 0, 0, 17, 4),
                (15, 4, 3, 3, 3, 2, 1, 1, 1, 0, 18, 4),
                (16, 4, 3, 3, 3, 2, 1, 1, 1, 0, 18, 4),
                (17, 4, 3, 3, 3, 2, 1, 1, 1, 1, 19, 4),
                (18, 4, 3, 3, 3, 3, 1, 1, 1, 1, 20, 4),
                (19, 4, 3, 3, 3, 3, 2, 1, 1, 1, 21, 4),
                (20, 4, 3, 3, 3, 3, 2, 2, 1, 1, 22, 4)
            ],
            "Жрец": [
                (1, 2, 0, 0, 0, 0, 0, 0, 0, 0, 4, 3),
                (2, 3, 0, 0, 0, 0, 0, 0, 0, 0, 5, 3),
                (3, 4, 2, 0, 0, 0, 0, 0, 0, 0, 6, 3),
                (4, 4, 3, 0, 0, 0, 0, 0, 0, 0, 7, 4),
                (5, 4, 3, 2, 0, 0, 0, 0, 0, 0, 9, 4),
                (6, 4, 3, 3, 0, 0, 0, 0, 0, 0, 10, 4),
                (7, 4, 3, 3, 1, 0, 0, 0, 0, 0, 11, 4),
                (8, 4, 3, 3, 2, 0, 0, 0, 0, 0, 12, 4),
                (9, 4, 3, 3, 3, 1, 0, 0, 0, 0, 14, 4),
                (10, 4, 3, 3, 3, 2, 0, 0, 0, 0, 15, 5),
                (11, 4, 3, 3, 3, 2, 1, 0, 0, 0, 16, 5),
                (12, 4, 3, 3, 3, 2, 1, 0, 0, 0, 16, 5),
                (13, 4, 3, 3, 3, 2, 1, 1, 0, 0, 17, 5),
                (14, 4, 3, 3, 3, 2, 1, 1, 0, 0, 17, 5),
                (15, 4, 3, 3, 3, 2, 1, 1, 1, 0, 18, 5),
                (16, 4, 3, 3, 3, 2, 1, 1, 1, 0, 18, 5),
                (17, 4, 3, 3, 3, 2, 1, 1, 1, 1, 19, 5),
                (18, 4, 3, 3, 3, 3, 1, 1, 1, 1, 20, 5),
                (19, 4, 3, 3, 3, 3, 2, 1, 1, 1, 21, 5),
                (20, 4, 3, 3, 3, 3, 2, 2, 1, 1, 22, 5)
            ],
            "Друид": [
                (1, 2, 0, 0, 0, 0, 0, 0, 0, 0, 4, 2),
                (2, 3, 0, 0, 0, 0, 0, 0, 0, 0, 5, 2),
                (3, 4, 2, 0, 0, 0, 0, 0, 0, 0, 6, 2),
                (4, 4, 3, 0, 0, 0, 0, 0, 0, 0, 7, 3),
                (5, 4, 3, 2, 0, 0, 0, 0, 0, 0, 9, 3),
                (6, 4, 3, 3, 0, 0, 0, 0, 0, 0, 10, 3),
                (7, 4, 3, 3, 1, 0, 0, 0, 0, 0, 11, 3),
                (8, 4, 3, 3, 2, 0, 0, 0, 0, 0, 12, 3),
                (9, 4, 3, 3, 3, 1, 0, 0, 0, 0, 14, 3),
                (10, 4, 3, 3, 3, 2, 0, 0, 0, 0, 15, 4),
                (11, 4, 3, 3, 3, 2, 1, 0, 0, 0, 16, 4),
                (12, 4, 3, 3, 3, 2, 1, 0, 0, 0, 16, 4),
                (13, 4, 3, 3, 3, 2, 1, 1, 0, 0, 17, 4),
                (14, 4, 3, 3, 3, 2, 1, 1, 0, 0, 17, 4),
                (15, 4, 3, 3, 3, 2, 1, 1, 1, 0, 18, 4),
                (16, 4, 3, 3, 3, 2, 1, 1, 1, 0, 18, 4),
                (17, 4, 3, 3, 3, 2, 1, 1, 1, 1, 19, 4),
                (18, 4, 3, 3, 3, 3, 1, 1, 1, 1, 20, 4),
                (19, 4, 3, 3, 3, 3, 2, 1, 1, 1, 21, 4),
                (20, 4, 3, 3, 3, 3, 2, 2, 1, 1, 22, 4)
            ],
            "Паладин": [
                (1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 2, 0),
                (2, 2, 0, 0, 0, 0, 0, 0, 0, 0, 3, 0),
                (3, 3, 0, 0, 0, 0, 0, 0, 0, 0, 4, 0),
                (4, 3, 0, 0, 0, 0, 0, 0, 0, 0, 5, 0),
                (5, 4, 2, 0, 0, 0, 0, 0, 0, 0, 6, 0),
                (6, 4, 2, 0, 0, 0, 0, 0, 0, 0, 6, 0),
                (7, 4, 3, 0, 0, 0, 0, 0, 0, 0, 7, 0),
                (8, 4, 3, 0, 0, 0, 0, 0, 0, 0, 7, 0),
                (9, 4, 3, 2, 0, 0, 0, 0, 0, 0, 9, 0),
                (10, 4, 3, 2, 0, 0, 0, 0, 0, 0, 9, 0),
                (11, 4, 3, 3, 0, 0, 0, 0, 0, 0, 10, 0),
                (12, 4, 3, 3, 0, 0, 0, 0, 0, 0, 10, 0),
                (13, 4, 3, 3, 1, 0, 0, 0, 0, 0, 11, 0),
                (14, 4, 3, 3, 1, 0, 0, 0, 0, 0, 11, 0),
                (15, 4, 3, 3, 2, 0, 0, 0, 0, 0, 12, 0),
                (16, 4, 3, 3, 2, 0, 0, 0, 0, 0, 12, 0),
                (17, 4, 3, 3, 3, 1, 0, 0, 0, 0, 14, 0),
                (18, 4, 3, 3, 3, 1, 0, 0, 0, 0, 14, 0),
                (19, 4, 3, 3, 3, 2, 0, 0, 0, 0, 15, 0),
                (20, 4, 3, 3, 3, 2, 0, 0, 0, 0, 15, 0)
            ],
            "Следопыт": [
                (1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 2, 0),
                (2, 2, 0, 0, 0, 0, 0, 0, 0, 0, 3, 0),
                (3, 3, 0, 0, 0, 0, 0, 0, 0, 0, 4, 0),
                (4, 3, 0, 0, 0, 0, 0, 0, 0, 0, 5, 0),
                (5, 4, 2, 0, 0, 0, 0, 0, 0, 0, 6, 0),
                (6, 4, 2, 0, 0, 0, 0, 0, 0, 0, 6, 0),
                (7, 4, 3, 0, 0, 0, 0, 0, 0, 0, 7, 0),
                (8, 4, 3, 0, 0, 0, 0, 0, 0, 0, 7, 0),
                (9, 4, 3, 2, 0, 0, 0, 0, 0, 0, 9, 0),
                (10, 4, 3, 2, 0, 0, 0, 0, 0, 0, 9, 0),
                (11, 4, 3, 3, 0, 0, 0, 0, 0, 0, 10, 0),
                (12, 4, 3, 3, 0, 0, 0, 0, 0, 0, 10, 0),
                (13, 4, 3, 3, 1, 0, 0, 0, 0, 0, 11, 0),
                (14, 4, 3, 3, 1, 0, 0, 0, 0, 0, 11, 0),
                (15, 4, 3, 3, 2, 0, 0, 0, 0, 0, 12, 0),
                (16, 4, 3, 3, 2, 0, 0, 0, 0, 0, 12, 0),
                (17, 4, 3, 3, 3, 1, 0, 0, 0, 0, 14, 0),
                (18, 4, 3, 3, 3, 1, 0, 0, 0, 0, 14, 0),
                (19, 4, 3, 3, 3, 2, 0, 0, 0, 0, 15, 0),
                (20, 4, 3, 3, 3, 2, 0, 0, 0, 0, 15, 0)
            ],
            "Чародей": [
                (1, 2, 0, 0, 0, 0, 0, 0, 0, 0, 2, 4),
                (2, 3, 0, 0, 0, 0, 0, 0, 0, 0, 4, 4),
                (3, 4, 2, 0, 0, 0, 0, 0, 0, 0, 6, 4),
                (4, 4, 3, 0, 0, 0, 0, 0, 0, 0, 7, 5),
                (5, 4, 3, 2, 0, 0, 0, 0, 0, 0, 9, 5),
                (6, 4, 3, 3, 0, 0, 0, 0, 0, 0, 10, 5),
                (7, 4, 3, 3, 1, 0, 0, 0, 0, 0, 11, 5),
                (8, 4, 3, 3, 2, 0, 0, 0, 0, 0, 12, 5),
                (9, 4, 3, 3, 3, 1, 0, 0, 0, 0, 14, 5),
                (10, 4, 3, 3, 3, 2, 0, 0, 0, 0, 15, 6),
                (11, 4, 3, 3, 3, 2, 1, 0, 0, 0, 16, 6),
                (12, 4, 3, 3, 3, 2, 1, 0, 0, 0, 16, 6),
                (13, 4, 3, 3, 3, 2, 1, 1, 0, 0, 17, 6),
                (14, 4, 3, 3, 3, 2, 1, 1, 0, 0, 17, 6),
                (15, 4, 3, 3, 3, 2, 1, 1, 1, 0, 18, 6),
                (16, 4, 3, 3, 3, 2, 1, 1, 1, 0, 18, 6),
                (17, 4, 3, 3, 3, 2, 1, 1, 1, 1, 19, 6),
                (18, 4, 3, 3, 3, 3, 1, 1, 1, 1, 20, 6),
                (19, 4, 3, 3, 3, 3, 2, 1, 1, 1, 21, 6),
                (20, 4, 3, 3, 3, 3, 2, 2, 1, 1, 22, 6)
            ],
            "Колдун": [
                (1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 2, 2),
                (2, 2, 0, 0, 0, 0, 0, 0, 0, 0, 3, 2),
                (3, 0, 2, 0, 0, 0, 0, 0, 0, 0, 4, 2),
                (4, 0, 2, 0, 0, 0, 0, 0, 0, 0, 5, 3),
                (5, 0, 0, 2, 0, 0, 0, 0, 0, 0, 6, 3),
                (6, 0, 0, 2, 0, 0, 0, 0, 0, 0, 7, 3),
                (7, 0, 0, 0, 2, 0, 0, 0, 0, 0, 8, 3),
                (8, 0, 0, 0, 2, 0, 0, 0, 0, 0, 9, 3),
                (9, 0, 0, 0, 0, 2, 0, 0, 0, 0, 10, 3),
                (10, 0, 0, 0, 0, 2, 0, 0, 0, 0, 10, 4),
                (11, 0, 0, 0, 0, 3, 0, 0, 0, 0, 11, 4),
                (12, 0, 0, 0, 0, 3, 0, 0, 0, 0, 11, 4),
                (13, 0, 0, 0, 0, 3, 0, 0, 0, 0, 12, 4),
                (14, 0, 0, 0, 0, 3, 0, 0, 0, 0, 12, 4),
                (15, 0, 0, 0, 0, 3, 0, 0, 0, 0, 13, 4),
                (16, 0, 0, 0, 0, 3, 0, 0, 0, 0, 13, 4),
                (17, 0, 0, 0, 0, 4, 0, 0, 0, 0, 14, 4),
                (18, 0, 0, 0, 0, 4, 0, 0, 0, 0, 14, 4),
                (19, 0, 0, 0, 0, 4, 0, 0, 0, 0, 15, 4),
                (20, 0, 0, 0, 0, 4, 0, 0, 0, 0, 15, 4)
            ],
            "Волшебник": [
                (1, 2, 0, 0, 0, 0, 0, 0, 0, 0, 6, 3),
                (2, 3, 0, 0, 0, 0, 0, 0, 0, 0, 8, 3),
                (3, 4, 2, 0, 0, 0, 0, 0, 0, 0, 10, 3),
                (4, 4, 3, 0, 0, 0, 0, 0, 0, 0, 12, 4),
                (5, 4, 3, 2, 0, 0, 0, 0, 0, 0, 14, 4),
                (6, 4, 3, 3, 0, 0, 0, 0, 0, 0, 16, 4),
                (7, 4, 3, 3, 1, 0, 0, 0, 0, 0, 18, 4),
                (8, 4, 3, 3, 2, 0, 0, 0, 0, 0, 20, 4),
                (9, 4, 3, 3, 3, 1, 0, 0, 0, 0, 22, 4),
                (10, 4, 3, 3, 3, 2, 0, 0, 0, 0, 24, 5),
                (11, 4, 3, 3, 3, 2, 1, 0, 0, 0, 26, 5),
                (12, 4, 3, 3, 3, 2, 1, 0, 0, 0, 28, 5),
                (13, 4, 3, 3, 3, 2, 1, 1, 0, 0, 30, 5),
                (14, 4, 3, 3, 3, 2, 1, 1, 0, 0, 32, 5),
                (15, 4, 3, 3, 3, 2, 1, 1, 1, 0, 34, 5),
                (16, 4, 3, 3, 3, 2, 1, 1, 1, 0, 36, 5),
                (17, 4, 3, 3, 3, 2, 1, 1, 1, 1, 38, 5),
                (18, 4, 3, 3, 3, 3, 1, 1, 1, 1, 40, 5),
                (19, 4, 3, 3, 3, 3, 2, 1, 1, 1, 42, 5),
                (20, 4, 3, 3, 3, 3, 2, 2, 1, 1, 44, 5)
            ]
        }
        
        spell_slots_count = 0
        for class_data in classes:
            class_id = class_data['id']
            class_name = class_data['name']
            
            if class_name in spell_slots_data:
                for level_data in spell_slots_data[class_name]:
                    level, slot1, slot2, slot3, slot4, slot5, slot6, slot7, slot8, slot9, known, cantrips = level_data
                    
                    self.execute_query(
                        """INSERT INTO class_spell_slots 
                        (class_id, level, slot_level_1, slot_level_2, slot_level_3, slot_level_4, slot_level_5, 
                         slot_level_6, slot_level_7, slot_level_8, slot_level_9, known_spells, known_cantrips) 
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                        (class_id, level, slot1, slot2, slot3, slot4, slot5, slot6, slot7, slot8, slot9, known, cantrips)
                    )
                    spell_slots_count += 1
        
        logger.info(f"Added {spell_slots_count} spell slot records")

    def full_database_setup(self):
        """Perform complete database setup"""
        
        logger.info("Starting complete database setup...")
        
        # Step 1: Create database if not exists
        if not self.create_database_if_not_exists():
            logger.error("Failed to create database")
            return False
        
        # Step 2: Connect to database
        if not self.connect():
            logger.error("Failed to connect to database")
            return False
        
        try:
            # Step 3: Initialize schema
            if not self.init_database_schema():
                logger.error("Failed to initialize database schema")
                return False
            
            # Step 4: Populate initial data
            self.populate_initial_data()
            
            # Step 5: Setup spell slots system
            self.setup_spell_slots_system()
            
            # Step 6: Initialize spell slots for existing spellcaster characters
            self.initialize_character_spell_slots()
            
            logger.info("Complete database setup finished successfully!")
            return True
            
        except Exception as e:
            logger.error(f"Error during database setup: {e}")
            return False
        
        finally:
            self.disconnect()

    def initialize_character_spell_slots(self):
        """Initialize spell slots for existing spellcaster characters"""
        
        logger.info("Initializing spell slots for existing characters...")
        
        characters = self.execute_query("""
            SELECT c.id, c.class_id, c.level
            FROM characters c
            JOIN classes cl ON c.class_id = cl.id
            WHERE cl.is_spellcaster = TRUE AND c.is_active = TRUE
        """)
        
        for char in characters:
            # Get slot information for this class and level
            slots_info = self.execute_query("""
                SELECT slot_level_1, slot_level_2, slot_level_3, slot_level_4, 
                       slot_level_5, slot_level_6, slot_level_7, slot_level_8, slot_level_9
                FROM class_spell_slots
                WHERE class_id = %s AND level = %s
            """, (char['class_id'], char['level']))
            
            if slots_info:
                slots_info = slots_info[0]
                # Add records for each slot level
                for slot_level in range(1, 10):
                    slot_column = f'slot_level_{slot_level}'
                    max_slots = slots_info.get(slot_column, 0)
                    
                    if max_slots > 0:
                        self.execute_query("""
                            INSERT INTO character_spell_slots (character_id, slot_level, max_slots, used_slots)
                            VALUES (%s, %s, %s, 0)
                            ON DUPLICATE KEY UPDATE max_slots = %s
                        """, (char['id'], slot_level, max_slots, max_slots))
        
        logger.info("Character spell slots initialized")

    def verify_database_setup(self):
        """Verify that all data was inserted correctly"""
        
        logger.info("Verifying database setup...")
        
        if not self.connect():
            logger.error("Failed to connect to database for verification")
            return False
        
        verification_queries = [
            ("levels", "SELECT COUNT(*) as count FROM levels"),
            ("races", "SELECT COUNT(*) as count FROM races"),
            ("origins", "SELECT COUNT(*) as count FROM origins"),
            ("classes", "SELECT COUNT(*) as count FROM classes"),
            ("weapons", "SELECT COUNT(*) as count FROM weapons"),
            ("armor", "SELECT COUNT(*) as count FROM armor"),
            ("class_spell_slots", "SELECT COUNT(*) as count FROM class_spell_slots"),
        ]
        
        all_good = True
        
        for table_name, query in verification_queries:
            try:
                result = self.execute_query(query)
                if result:
                    count = result[0]['count']
                    logger.info(f"Table {table_name}: {count} records")
                else:
                    logger.error(f"Failed to verify table {table_name}")
                    all_good = False
            except Exception as e:
                logger.error(f"Error verifying table {table_name}: {e}")
                all_good = False
        
        # Check some specific data
        try:
            spellcaster_classes = self.execute_query("SELECT name FROM classes WHERE is_spellcaster = TRUE")
            logger.info(f"Spellcaster classes: {[c['name'] for c in spellcaster_classes]}")
            
            # Note: Spells verification should be done after running import scripts
            # combat_spells and cantrips are now imported separately
            
        except Exception as e:
            logger.error(f"Error during detailed verification: {e}")
            all_good = False
        
        self.disconnect()
        
        if all_good:
            logger.info("Database verification completed successfully!")
        else:
            logger.error("Database verification found issues!")
        
        return all_good

def main():
    """Main function to run complete database setup"""
    
    manager = DatabaseSetupManager()
    
    print("=== DnD Bot Database Setup Manager ===")
    print("1. Starting complete database setup...")
    
    if manager.full_database_setup():
        print("\n2. Verifying database setup...")
        if manager.verify_database_setup():
            print("\n✅ Database setup and verification completed successfully!")
            print("\nYour DnD bot database is ready to use!")
        else:
            print("\n❌ Database setup completed but verification found issues!")
    else:
        print("\n❌ Database setup failed!")

if __name__ == "__main__":
    main()
