import PyPDF2
import json
import re
import logging
from database import get_db

logger = logging.getLogger(__name__)

class PDFParser:
    def __init__(self):
        self.db = get_db()
    
    def extract_text_from_pdf(self, file_path):
        """Extract text from PDF file"""
        try:
            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                text = ""
                for page in pdf_reader.pages:
                    text += page.extract_text() + "\n"
                return text
        except Exception as e:
            logger.error(f"Error reading PDF {file_path}: {e}")
            return None
    
    def parse_origins(self):
        """Parse origins from PDF and insert into database"""
        text = self.extract_text_from_pdf("Docs/Происхождения.pdf")
        if not text:
            return False
        
        # Origins data based on PDF parsing
        origins_data = [
            ("Артист", '{"str": 1, "dex": 1, "cha": 1}', '["Акробатика", "Выступление"]', 5000),  # 50 зм = 5000 монет
            ("Благородный", '{"str": 1, "int": 1, "cha": 1}', '["История", "Убеждение"]', 5000),  # 50 зм = 5000 монет
            ("Моряк", '{"str": 1, "dex": 1, "wis": 1}', '["Акробатика", "Внимательность"]', 5000),  # 50 зм = 5000 монет
            ("Мудрец", '{"con": 1, "int": 1, "wis": 1}', '["Аркана", "История"]', 5000),  # 50 зм = 5000 монет
            ("Отшельник", '{"con": 1, "wis": 1, "cha": 1}', '["Медицина", "Религия"]', 5000),  # 50 зм = 5000 монет
            ("Преступник", '{"dex": 1, "int": 1, "cha": 1}', '["Обман", "Скрытность"]', 5000),  # 50 зм = 5000 монет
            ("Народный герой", '{"str": 1, "con": 1, "wis": 1}', '["Выживание", "Обращение с животными"]', 5000),  # 50 зм = 5000 монет
            ("Солдат", '{"str": 1, "con": 1, "cha": 1}', '["Атлетика", "Запугивание"]', 5000),  # 50 зм = 5000 монет
            ("Аколит", '{"int": 1, "wis": 1, "cha": 1}', '["Проницательность", "Религия"]', 5000),  # 50 зм = 5000 монет
            ("Алхимик", '{"con": 1, "int": 1, "wis": 1}', '["Аркана", "Медицина"]', 5000),  # 50 зм = 5000 монет
        ]
        
        for origin_data in origins_data:
            self.db.execute_query(
                "INSERT IGNORE INTO origins (name, stat_bonuses, skills, starting_money) VALUES (%s, %s, %s, %s)",
                origin_data
            )
        
        logger.info("Origins data inserted successfully")
        return True
    
    def parse_races(self):
        """Parse races from PDF and insert into database"""
        text = self.extract_text_from_pdf("Docs/Расы.pdf")
        if not text:
            return False
        
        # Sample races data
        races_data = [
            ("Человек",), ("Эльф",), ("Дварф",), ("Полурослик",), ("Драконорожденный",),
            ("Гном",), ("Полуэльф",), ("Полуорк",), ("Тифлинг",), ("Орк",),
            ("Аасимар",), ("Гоблин",), ("Голиаф",), ("Фирболг",), ("Табакси",)
        ]
        
        for race_data in races_data:
            self.db.execute_query(
                "INSERT IGNORE INTO races (name) VALUES (%s)",
                race_data
            )
        
        logger.info("Races data inserted successfully")
        return True
    
    def parse_armor(self):
        """Parse armor from PDF and insert into database"""
        text = self.extract_text_from_pdf("Docs/Доспехи.pdf")
        if not text:
            return False
        
        # Sample armor data (converted from copper/silver/gold to coins)
        armor_data = [
            ("Кожаная", "11 + Лов", 0, 10.0, 1000),      # 10gp = 1000 coins
            ("Кожаная клепаная", "12 + Лов", 0, 13.0, 4500),  # 45gp = 4500 coins
            ("Кольчуга", "13 + Лов (макс 2)", 0, 20.0, 5000),
            ("Чешуйчатая", "14 + Лов (макс 2)", 0, 45.0, 5000),
            ("Нагрудник", "14 + Лов (макс 2)", 0, 20.0, 40000),
            ("Кольчатая рубаха", "15 + Лов (макс 2)", 0, 40.0, 7500),
            ("Кольчужные доспехи", "16", 13, 55.0, 15000),
            ("Чешуйчатые доспехи", "16 + Лов (макс 2)", 0, 45.0, 5000),
            ("Пластинчатые доспехи", "17", 13, 60.0, 20000),
            ("Латы", "18", 15, 65.0, 150000),
            ("Щит", "+2", 0, 6.0, 1000)
        ]
        
        for armor in armor_data:
            self.db.execute_query(
                "INSERT IGNORE INTO armor (name, armor_class, strength_requirement, weight, price) VALUES (%s, %s, %s, %s, %s)",
                armor
            )
        
        logger.info("Armor data inserted successfully")
        return True
    
    def parse_weapons(self):
        """Parse weapons from PDF and insert into database"""
        text = self.extract_text_from_pdf("Docs/Оружие.pdf")
        if not text:
            return False
        
# Sample weapons data
        weapons_data = [
            ("Простое", "Дубинка", "1d4", "дробящий", '["Лёгкое"]', "одноручное", 2.0, 10),
            ("Простое", "Кинжал", "1d4", "колющий", '["Фехтовальное", "Лёгкое", "Метательное"]', "одноручное", 1.0, 200),
            ("Простое", "Палица", "1d8", "дробящий", '["Двуручное"]', "двуручное", 10.0, 20),
            ("Простое", "Ручной топор", "1d6", "рубящий", '["Лёгкое", "Метательное"]', "одноручное", 2.0, 500),
            ("Простое", "Метательное копьё", "1d6", "колющий", '["Метательное"]', "одноручное", 2.0, 50),
            ("Простое", "Лёгкий молот", "1d4", "дробящий", '["Лёгкое", "Метательное"]', "одноручное", 2.0, 200),
            ("Простое", "Булава", "1d6", "дробящий", '[]', "одноручное", 4.0, 500),
            ("Простое", "Боевой посох", "1d6", "дробящий", '["Универсальное (1d8)"]', "одноручное", 4.0, 20),
            ("Простое", "Серп", "1d4", "рубящий", '["Лёгкое"]', "одноручное", 2.0, 100),
            ("Простое", "Копьё", "1d6", "колющий", '["Метательное", "Универсальное (1d8)"]', "одноручное", 3.0, 100),
            ("Воинское", "Боевой топор", "1d8", "рубящий", '["Универсальное (1d10)"]', "одноручное", 4.0, 1000),
            ("Воинское", "Цеп", "1d8", "дробящий", '[]', "одноручное", 2.0, 1000),
            ("Воинское", "Глефа", "1d10", "рубящий", '["Тяжёлое", "Досягаемость", "Двуручное"]', "двуручное", 6.0, 2000),
            ("Воинское", "Секира", "1d12", "рубящий", '["Тяжёлое", "Двуручное"]', "двуручное", 7.0, 3000),
            ("Воинское", "Двуручный меч", "2d6", "рубящий", '["Тяжёлое", "Двуручное"]', "двуручное", 6.0, 5000),
            ("Воинское", "Алебарда", "1d10", "рубящий", '["Тяжёлое", "Досягаемость", "Двуручное"]', "двуручное", 6.0, 2000),
            ("Воинское", "Длинное копьё", "1d10", "колющий", '["Тяжёлое", "Досягаемость", "Двуручное"]', "двуручное", 6.0, 1000),
            ("Воинское", "Длинный меч", "1d8", "рубящий", '["Универсальное (1d10)"]', "одноручное", 3.0, 1500)
        ]
        
        for weapon in weapons_data:
            self.db.execute_query(
                "INSERT IGNORE INTO weapons (weapon_type, name, damage, damage_type, properties, grip_type, weight, price) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                weapon
            )
        
        logger.info("Weapons data inserted successfully")
        return True
    
    def parse_classes(self):
        """Parse classes from PDF files and insert into database"""
        
        # Classes data with correct starting money from PDF parsing (Б options)
        classes_data = [
            ("Варвар", "Сила", 12, '["простое", "воинское"]', '["легкие", "средние", "щиты"]', '["Уход за животными", "Атлетика", "Природа", "Запугивание", "Внимательность", "Выживание"]', 2, 7500, False),  # 75 зм = 7500 монет
            ("Бард", "Харизма", 8, '["простое"]', '["легкие"]', '["любые три"]', 3, 7500, True),  # 75 зм = 7500 монет
            ("Жрец", "Мудрость", 8, '["простое"]', '["легкие", "средние", "щиты"]', '["История", "Проницательность", "Медицина", "Убеждение", "Религия"]', 2, 11000, True),  # 110 зм = 11000 монет
            ("Друид", "Мудрость", 8, '["простое"]', '["легкие", "щиты"]', '["Аркана", "Уход за животными", "Проницательность", "Медицина", "Природа", "Внимательность", "Религия", "Выживание"]', 2, 5000, True),  # 50 зм = 5000 монет
            ("Воин", "Сила", 10, '["простое", "воинское"]', '["все", "щиты"]', '["Акробатика", "Атлетика", "Внимательность", "Выживание", "Запугивание", "История", "Проницательность", "Убеждение", "Уход за животными"]', 2, 15500, False),  # 155 зм = 15500 монет
            ("Монах", "Ловкость", 8, '["простое", "короткие мечи"]', '[]', '["Акробатика", "Атлетика", "История", "Проницательность", "Религия", "Скрытность"]', 2, 5000, False),  # 50 зм = 5000 монет
            ("Паладин", "Сила", 10, '["простое", "воинское"]', '["все", "щиты"]', '["Атлетика", "Проницательность", "Запугивание", "Медицина", "Убеждение", "Религия"]', 2, 15000, True),  # 150 зм = 15000 монет
            ("Следопыт", "Ловкость", 10, '["простое", "воинское"]', '["легкие", "средние", "щиты"]', '["Уход за животными", "Атлетика", "Проницательность", "Анализ", "Природа", "Внимательность", "Скрытность", "Выживание"]', 3, 15000, True),  # 150 зм = 15000 монет
            ("Плут", "Ловкость", 8, '["простое", "воинское со свойством фехтовальное или легкое"]', '["легкие"]', '["Акробатика", "Атлетика", "Обман", "Проницательность", "Запугивание", "Анализ", "Внимательность", "Убеждение", "Ловкость рук", "Скрытность"]', 4, 10000, False),  # 100 зм = 10000 монет
            ("Чародей", "Харизма", 6, '["простое"]', '[]', '["Аркана", "Обман", "Проницательность", "Запугивание", "Убеждение", "Религия"]', 2, 5000, True),  # 50 зм = 5000 монет
            ("Колдун", "Харизма", 8, '["простое"]', '["легкие"]', '["Аркана", "Обман", "История", "Запугивание", "Анализ", "Природа", "Религия"]', 2, 10000, True),  # 100 зм = 10000 монет
            ("Волшебник", "Интеллект", 6, '["простое"]', '[]', '["Аркана", "История", "Проницательность", "Анализ", "Медицина", "Религия"]', 2, 5500, True)  # 55 зм = 5500 монет
        ]
        
        for class_data in classes_data:
            result = self.db.execute_query(
                "INSERT IGNORE INTO classes (name, primary_stat, hit_die, weapon_proficiency, armor_proficiency, skills_available, skills_count, starting_money, is_spellcaster) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                class_data
            )
        
        # Insert spell slot data for spellcasting classes
        self.insert_spell_slots_data()
        
        logger.info("Classes data inserted successfully")
        return True
    
    def insert_spell_slots_data(self):
        """Insert spell slots data for spellcasting classes"""
        
        # Get class IDs for spellcasters
        classes = self.db.execute_query("SELECT id, name FROM classes WHERE is_spellcaster = TRUE")
        
        if not classes:
            return
        
        # Sample spell slots data for level 1-5 (can be extended)
        spell_slots_data = {
            "Бард": [
                (1, 2, 0, 0, 0, 0, 0, 0, 0, 0, 4),
                (2, 3, 0, 0, 0, 0, 0, 0, 0, 0, 5),
                (3, 4, 2, 0, 0, 0, 0, 0, 0, 0, 6),
                (4, 4, 3, 0, 0, 0, 0, 0, 0, 0, 7),
                (5, 4, 3, 2, 0, 0, 0, 0, 0, 0, 8)
            ],
            "Жрец": [
                (1, 2, 0, 0, 0, 0, 0, 0, 0, 0, 2),
                (2, 3, 0, 0, 0, 0, 0, 0, 0, 0, 3),
                (3, 4, 2, 0, 0, 0, 0, 0, 0, 0, 4),
                (4, 4, 3, 0, 0, 0, 0, 0, 0, 0, 5),
                (5, 4, 3, 2, 0, 0, 0, 0, 0, 0, 6)
            ],
            "Друид": [
                (1, 2, 0, 0, 0, 0, 0, 0, 0, 0, 2),
                (2, 3, 0, 0, 0, 0, 0, 0, 0, 0, 3),
                (3, 4, 2, 0, 0, 0, 0, 0, 0, 0, 4),
                (4, 4, 3, 0, 0, 0, 0, 0, 0, 0, 5),
                (5, 4, 3, 2, 0, 0, 0, 0, 0, 0, 6)
            ],
            "Паладин": [
                (1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
                (2, 2, 0, 0, 0, 0, 0, 0, 0, 0, 2),
                (3, 3, 0, 0, 0, 0, 0, 0, 0, 0, 3),
                (4, 3, 0, 0, 0, 0, 0, 0, 0, 0, 4),
                (5, 4, 2, 0, 0, 0, 0, 0, 0, 0, 5)
            ],
            "Следопыт": [
                (1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
                (2, 2, 0, 0, 0, 0, 0, 0, 0, 0, 2),
                (3, 3, 0, 0, 0, 0, 0, 0, 0, 0, 3),
                (4, 3, 0, 0, 0, 0, 0, 0, 0, 0, 4),
                (5, 4, 2, 0, 0, 0, 0, 0, 0, 0, 5)
            ],
            "Чародей": [
                (1, 2, 0, 0, 0, 0, 0, 0, 0, 0, 2),
                (2, 3, 0, 0, 0, 0, 0, 0, 0, 0, 3),
                (3, 4, 2, 0, 0, 0, 0, 0, 0, 0, 4),
                (4, 4, 3, 0, 0, 0, 0, 0, 0, 0, 5),
                (5, 4, 3, 2, 0, 0, 0, 0, 0, 0, 6)
            ],
            "Колдун": [
                (1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 2),
                (2, 2, 0, 0, 0, 0, 0, 0, 0, 0, 3),
                (3, 0, 2, 0, 0, 0, 0, 0, 0, 0, 4),
                (4, 0, 2, 0, 0, 0, 0, 0, 0, 0, 5),
                (5, 0, 0, 2, 0, 0, 0, 0, 0, 0, 6)
            ],
            "Волшебник": [
                (1, 2, 0, 0, 0, 0, 0, 0, 0, 0, 6),
                (2, 3, 0, 0, 0, 0, 0, 0, 0, 0, 8),
                (3, 4, 2, 0, 0, 0, 0, 0, 0, 0, 10),
                (4, 4, 3, 0, 0, 0, 0, 0, 0, 0, 12),
                (5, 4, 3, 2, 0, 0, 0, 0, 0, 0, 14)
            ]
        }
        
        for class_data in classes:
            class_id = class_data['id']
            class_name = class_data['name']
            
            if class_name in spell_slots_data:
                for level_data in spell_slots_data[class_name]:
                    level, slot1, slot2, slot3, slot4, slot5, slot6, slot7, slot8, slot9, known = level_data
                    
                    self.db.execute_query(
                        """INSERT IGNORE INTO class_spell_slots 
                        (class_id, level, slot_level_1, slot_level_2, slot_level_3, slot_level_4, slot_level_5, 
                         slot_level_6, slot_level_7, slot_level_8, slot_level_9, known_spells) 
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                        (class_id, level, slot1, slot2, slot3, slot4, slot5, slot6, slot7, slot8, slot9, known)
                    )
    
    def parse_all_data(self):
        """Parse all PDF data and populate database"""
        logger.info("Starting to parse all PDF data...")
        
        self.parse_origins()
        self.parse_races()
        self.parse_armor()
        self.parse_weapons()
        self.parse_classes()
        
        logger.info("All PDF data parsed successfully")

if __name__ == "__main__":
    parser = PDFParser()
    if parser.db.connect():
        parser.parse_all_data()
        parser.db.disconnect()
