import mysql.connector
from mysql.connector import Error
import logging
from config import DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DatabaseManager:
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

    def init_database(self):
        """Initialize database schema"""
        
        # Drop and recreate tables if they exist
        drop_tables = [
            "DROP TABLE IF EXISTS adventure_participants",
            "DROP TABLE IF EXISTS character_spells",
            "DROP TABLE IF EXISTS character_equipment",
            "DROP TABLE IF EXISTS combat_participants",
            "DROP TABLE IF EXISTS enemies",
            "DROP TABLE IF EXISTS chat_history",
            "DROP TABLE IF EXISTS characters",
            "DROP TABLE IF EXISTS adventures",
            "DROP TABLE IF EXISTS class_spell_slots",
            "DROP TABLE IF EXISTS spells",
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
                is_spellcaster BOOLEAN DEFAULT FALSE
            )
            """,
            
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
                FOREIGN KEY (class_id) REFERENCES classes(id) ON DELETE CASCADE
            )
            """,
            
            # Spells table
            """
            CREATE TABLE spells (
                id INT AUTO_INCREMENT PRIMARY KEY,
                level INT,
                name VARCHAR(100) NOT NULL,
                damage VARCHAR(20),
                damage_type VARCHAR(20),
                description TEXT
            )
            """,
            
            # Adventures table
            """
            CREATE TABLE adventures (
                id INT AUTO_INCREMENT PRIMARY KEY,
                chat_id BIGINT NOT NULL,
                status VARCHAR(20) DEFAULT 'preparing',  -- preparing, active, combat, finished
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            )
            """,
            
            # Characters table
            """
            CREATE TABLE characters (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id BIGINT NOT NULL,
                adventure_id INT,
                name VARCHAR(100) NOT NULL,
                race_id INT,
                origin_id INT,
                class_id INT,
                level INT DEFAULT 1,
                experience INT DEFAULT 0,
                strength INT,
                dexterity INT,
                constitution INT,
                intelligence INT,
                wisdom INT,
                charisma INT,
                hit_points INT,
                max_hit_points INT,
                money INT DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active BOOLEAN DEFAULT TRUE,
                FOREIGN KEY (race_id) REFERENCES races(id),
                FOREIGN KEY (origin_id) REFERENCES origins(id),
                FOREIGN KEY (class_id) REFERENCES classes(id),
                FOREIGN KEY (adventure_id) REFERENCES adventures(id)
            )
            """,
            
            # Adventure participants table
            """
            CREATE TABLE adventure_participants (
                id INT AUTO_INCREMENT PRIMARY KEY,
                adventure_id INT,
                character_id INT,
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (adventure_id) REFERENCES adventures(id) ON DELETE CASCADE,
                FOREIGN KEY (character_id) REFERENCES characters(id) ON DELETE CASCADE,
                UNIQUE KEY unique_participation (adventure_id, character_id)
            )
            """,
            
            # Character equipment table
            """
            CREATE TABLE character_equipment (
                id INT AUTO_INCREMENT PRIMARY KEY,
                character_id INT,
                item_type VARCHAR(20),  -- 'weapon' or 'armor'
                item_id INT,
                is_equipped BOOLEAN DEFAULT FALSE,
                FOREIGN KEY (character_id) REFERENCES characters(id) ON DELETE CASCADE
            )
            """,
            
            # Character spells table
            """
            CREATE TABLE character_spells (
                id INT AUTO_INCREMENT PRIMARY KEY,
                character_id INT,
                spell_id INT,
                FOREIGN KEY (character_id) REFERENCES characters(id) ON DELETE CASCADE,
                FOREIGN KEY (spell_id) REFERENCES spells(id) ON DELETE CASCADE
            )
            """,
            
            # Chat history table for Grok context
            """
            CREATE TABLE chat_history (
                id INT AUTO_INCREMENT PRIMARY KEY,
                adventure_id INT,
                role VARCHAR(20),  -- 'user', 'assistant', 'system'
                content TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (adventure_id) REFERENCES adventures(id) ON DELETE CASCADE
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
                strength INT,
                dexterity INT,
                constitution INT,
                intelligence INT,
                wisdom INT,
                charisma INT,
                attack_name VARCHAR(100),
                attack_damage VARCHAR(20),
                attack_bonus INT DEFAULT 0,
                experience_reward INT DEFAULT 0,
                is_alive BOOLEAN DEFAULT TRUE,
                FOREIGN KEY (adventure_id) REFERENCES adventures(id) ON DELETE CASCADE
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
            """
        ]
        
        # Execute table creation
        for create_query in create_tables:
            result = self.execute_query(create_query)
            if result is None:
                logger.error(f"Failed to create table with query: {create_query[:50]}...")
                return False
        
        # Insert initial data
        self.insert_initial_data()
        
        logger.info("Database schema initialized successfully")
        return True
    
    def insert_initial_data(self):
        """Insert initial game data"""
        
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
        
        # Insert placeholder spells
        spells_data = [
            (0, "Волшебная рука", None, None, "Заклинание заговора для перемещения объектов"),
            (0, "Свет", None, None, "Создает яркий свет в радиусе 20 футов"),
            (0, "Малое исцеление", "1d4", "исцеление", "Восстанавливает небольшое количество хитов"),
            (1, "Магическая стрела", "1d4+1", "силовое", "Автоматически попадающая стрела из силы"),
            (1, "Исцеление ран", "1d8+мод", "исцеление", "Восстанавливает хиты прикосновением"),
            (1, "Щит", None, None, "Дает +5 к КД до следующего хода"),
            (2, "Огненный шар", "8d6", "огонь", "Взрывается в радиусе 20 футов"),
            (2, "Размытие", None, None, "Атаки по вам совершаются с помехой"),
            (3, "Молния", "8d6", "электричество", "Линия молнии длиной 100 футов"),
            (3, "Полет", None, None, "Дает скорость полета 60 футов")
        ]
        
        self.execute_many(
            "INSERT INTO spells (level, name, damage, damage_type, description) VALUES (%s, %s, %s, %s, %s)",
            spells_data
        )
        
        logger.info("Initial data inserted successfully")

# Global database instance
db = DatabaseManager()

def get_db():
    """Get database instance"""
    return db
