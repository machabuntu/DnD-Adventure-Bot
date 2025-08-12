#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Модуль для управления слотами заклинаний персонажей
"""

import logging
from database import DatabaseManager
from typing import Optional, List, Dict, Tuple

logger = logging.getLogger(__name__)

class SpellSlotManager:
    def __init__(self):
        self.db = DatabaseManager()
        self.db.connect()
    
    def initialize_character_slots(self, character_id: int) -> bool:
        """
        Инициализация слотов заклинаний для персонажа при создании или повышении уровня
        """
        try:
            # Получаем информацию о персонаже
            character = self.db.execute_query("""
                SELECT c.id, c.level, c.class_id, cl.is_spellcaster
                FROM characters c
                JOIN classes cl ON c.class_id = cl.id
                WHERE c.id = %s
            """, (character_id,))
            
            if not character or not character[0]['is_spellcaster']:
                logger.info(f"Персонаж {character_id} не является заклинателем")
                return False
            
            char_info = character[0]
            
            # Получаем информацию о слотах для данного класса и уровня
            slots_info = self.db.execute_query("""
                SELECT slot_level_1, slot_level_2, slot_level_3, slot_level_4, 
                       slot_level_5, slot_level_6, slot_level_7, slot_level_8, slot_level_9
                FROM class_spell_slots
                WHERE class_id = %s AND level = %s
            """, (char_info['class_id'], char_info['level']))
            
            if not slots_info:
                logger.warning(f"Не найдена информация о слотах для класса {char_info['class_id']} уровня {char_info['level']}")
                return False
            
            slots = slots_info[0]
            
            # Обновляем или создаем записи для каждого уровня слотов
            for slot_level in range(1, 10):
                slot_column = f'slot_level_{slot_level}'
                max_slots = slots.get(slot_column, 0)
                
                if max_slots > 0:
                    self.db.execute_query("""
                        INSERT INTO character_spell_slots (character_id, slot_level, max_slots, used_slots)
                        VALUES (%s, %s, %s, 0)
                        ON DUPLICATE KEY UPDATE max_slots = %s, used_slots = LEAST(used_slots, %s)
                    """, (character_id, slot_level, max_slots, max_slots, max_slots))
            
            logger.info(f"Слоты заклинаний для персонажа {character_id} инициализированы")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка при инициализации слотов: {e}")
            return False
    
    def get_available_slots(self, character_id: int) -> Dict[int, Tuple[int, int]]:
        """
        Получение доступных слотов заклинаний для персонажа
        Возвращает словарь {уровень_слота: (использовано, максимум)}
        """
        try:
            slots = self.db.execute_query("""
                SELECT slot_level, used_slots, max_slots
                FROM character_spell_slots
                WHERE character_id = %s
                ORDER BY slot_level
            """, (character_id,))
            
            if not slots:
                return {}
            
            return {
                slot['slot_level']: (slot['used_slots'], slot['max_slots'])
                for slot in slots
            }
            
        except Exception as e:
            logger.error(f"Ошибка при получении слотов: {e}")
            return {}
    
    def has_available_slot(self, character_id: int, spell_level: int) -> bool:
        """
        Проверка наличия доступного слота для заклинания определенного уровня
        """
        if spell_level == 0:  # Заговоры не требуют слотов
            return True
        
        try:
            # Проверяем наличие слотов того же уровня или выше
            result = self.db.execute_query("""
                SELECT slot_level, (max_slots - used_slots) as available
                FROM character_spell_slots
                WHERE character_id = %s 
                AND slot_level >= %s
                AND used_slots < max_slots
                ORDER BY slot_level
                LIMIT 1
            """, (character_id, spell_level))
            
            return bool(result)
            
        except Exception as e:
            logger.error(f"Ошибка при проверке доступности слота: {e}")
            return False
    
    def use_spell_slot(self, character_id: int, spell_level: int) -> Optional[int]:
        """
        Использование слота заклинания
        Возвращает уровень использованного слота или None, если слот недоступен
        """
        if spell_level == 0:  # Заговоры не используют слоты
            return 0
        
        try:
            # Находим доступный слот минимального подходящего уровня
            available_slot = self.db.execute_query("""
                SELECT slot_level
                FROM character_spell_slots
                WHERE character_id = %s 
                AND slot_level >= %s
                AND used_slots < max_slots
                ORDER BY slot_level
                LIMIT 1
            """, (character_id, spell_level))
            
            if not available_slot:
                logger.warning(f"Нет доступных слотов уровня {spell_level} или выше для персонажа {character_id}")
                return None
            
            slot_level = available_slot[0]['slot_level']
            
            # Увеличиваем счетчик использованных слотов
            self.db.execute_query("""
                UPDATE character_spell_slots
                SET used_slots = used_slots + 1
                WHERE character_id = %s AND slot_level = %s
            """, (character_id, slot_level))
            
            logger.info(f"Персонаж {character_id} использовал слот уровня {slot_level} для заклинания уровня {spell_level}")
            return slot_level
            
        except Exception as e:
            logger.error(f"Ошибка при использовании слота: {e}")
            return None
    
    def restore_spell_slot(self, character_id: int, slot_level: int) -> bool:
        """
        Восстановление одного слота заклинания определенного уровня
        """
        try:
            result = self.db.execute_query("""
                UPDATE character_spell_slots
                SET used_slots = GREATEST(0, used_slots - 1)
                WHERE character_id = %s AND slot_level = %s AND used_slots > 0
            """, (character_id, slot_level))
            
            if result and result > 0:
                logger.info(f"Восстановлен слот уровня {slot_level} для персонажа {character_id}")
                return True
            return False
            
        except Exception as e:
            logger.error(f"Ошибка при восстановлении слота: {e}")
            return False
    
    def rest_short(self, character_id: int) -> bool:
        """
        Короткий отдых - восстановление некоторых способностей (зависит от класса)
        Для колдуна восстанавливаются все слоты
        """
        try:
            # Проверяем, является ли персонаж колдуном
            character = self.db.execute_query("""
                SELECT cl.name
                FROM characters c
                JOIN classes cl ON c.class_id = cl.id
                WHERE c.id = %s
            """, (character_id,))
            
            if character and character[0]['name'] == 'Колдун':
                # Колдуны восстанавливают все слоты при коротком отдыхе
                self.db.execute_query("""
                    UPDATE character_spell_slots
                    SET used_slots = 0
                    WHERE character_id = %s
                """, (character_id,))
                logger.info(f"Колдун {character_id} восстановил все слоты при коротком отдыхе")
            
            return True
            
        except Exception as e:
            logger.error(f"Ошибка при коротком отдыхе: {e}")
            return False
    
    def rest_long(self, character_id: int) -> bool:
        """
        Длинный отдых - полное восстановление всех слотов заклинаний
        """
        try:
            self.db.execute_query("""
                UPDATE character_spell_slots
                SET used_slots = 0
                WHERE character_id = %s
            """, (character_id,))
            
            logger.info(f"Персонаж {character_id} восстановил все слоты при длинном отдыхе")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка при длинном отдыхе: {e}")
            return False
    
    def get_available_spell_levels(self, character_id: int) -> List[int]:
        """
        Получение списка уровней заклинаний, для которых есть доступные слоты
        Всегда включает 0 (заговоры)
        """
        try:
            result = self.db.execute_query("""
                SELECT DISTINCT s.level
                FROM character_spells cs
                JOIN spells s ON cs.spell_id = s.id
                WHERE cs.character_id = %s
                AND (
                    s.level = 0  -- Заговоры всегда доступны
                    OR EXISTS (
                        SELECT 1
                        FROM character_spell_slots css
                        WHERE css.character_id = %s
                        AND css.slot_level >= s.level
                        AND css.used_slots < css.max_slots
                    )
                )
                ORDER BY s.level
            """, (character_id, character_id))
            
            return [row['level'] for row in result] if result else [0]
            
        except Exception as e:
            logger.error(f"Ошибка при получении доступных уровней заклинаний: {e}")
            return [0]
    
    def get_spell_slots_info(self, character_id: int) -> str:
        """
        Получение текстовой информации о слотах заклинаний для отображения
        """
        try:
            slots = self.get_available_slots(character_id)
            
            if not slots:
                return "У вас нет слотов заклинаний"
            
            info_parts = []
            for level, (used, max_slots) in sorted(slots.items()):
                available = max_slots - used
                if max_slots > 0:
                    emoji = "🔴" if available == 0 else "🟢" if available == max_slots else "🟡"
                    info_parts.append(f"{emoji} Ур.{level}: {available}/{max_slots}")
            
            return "📊 **Слоты заклинаний:**\n" + "\n".join(info_parts)
            
        except Exception as e:
            logger.error(f"Ошибка при получении информации о слотах: {e}")
            return "Ошибка при получении информации о слотах"
    
    def __del__(self):
        """Деструктор для закрытия соединения с БД"""
        if hasattr(self, 'db'):
            self.db.disconnect()


# Глобальный экземпляр менеджера слотов
spell_slot_manager = SpellSlotManager()
