#!/usr/bin/env python3
"""
Модуль для выбора заклинаний при создании персонажа.
Обрабатывает выбор заговоров и заклинаний в соответствии с классом персонажа.
"""

import json
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import get_db

logger = logging.getLogger(__name__)

class SpellSelectionManager:
    def __init__(self):
        self.db = get_db()
    
    def needs_spell_selection(self, class_id: int, level: int = 1) -> bool:
        """Проверяет, нужен ли выбор заклинаний для данного класса."""
        if not self.db.connection or not self.db.connection.is_connected():
            self.db.connect()
        
        # Проверяем, является ли класс магическим
        class_query = "SELECT is_spellcaster FROM classes WHERE id = %s"
        class_info = self.db.execute_query(class_query, (class_id,))
        
        if not class_info or not class_info[0]['is_spellcaster']:
            return False
        
        # Проверяем, есть ли заклинания для этого класса и уровня
        slots_query = "SELECT known_cantrips, known_spells FROM class_spell_slots WHERE class_id = %s AND level = %s"
        slots_info = self.db.execute_query(slots_query, (class_id, level))
        
        if not slots_info:
            return False
        
        cantrips = slots_info[0]['known_cantrips'] or 0
        spells = slots_info[0]['known_spells'] or 0
        
        return cantrips > 0 or spells > 0
    
    def get_available_cantrips(self, class_id: int) -> list:
        """Получает список доступных заговоров для класса."""
        if not self.db.connection or not self.db.connection.is_connected():
            self.db.connect()
        
        # Получаем имя класса
        class_query = "SELECT name FROM classes WHERE id = %s"
        class_info = self.db.execute_query(class_query, (class_id,))
        
        if not class_info:
            return []
        
        class_name = class_info[0]['name']
        
        # Получаем заговоры (уровень 0), доступные этому классу
        cantrips_query = """
            SELECT id, name, description, damage, damage_type, is_combat, is_area_of_effect
            FROM spells 
            WHERE level = 0 AND available_classes LIKE %s
            ORDER BY name
        """
        
        cantrips = self.db.execute_query(cantrips_query, (f'%"{class_name}"%',))
        return cantrips or []
    
    def get_available_spells(self, class_id: int, level: int = 1) -> list:
        """Получает список доступных заклинаний для класса и уровня."""
        if not self.db.connection or not self.db.connection.is_connected():
            self.db.connect()
        
        # Получаем имя класса
        class_query = "SELECT name FROM classes WHERE id = %s"
        class_info = self.db.execute_query(class_query, (class_id,))
        
        if not class_info:
            return []
        
        class_name = class_info[0]['name']
        
        # Получаем доступные слоты заклинаний для определения максимального уровня заклинаний
        slots_query = """
            SELECT slot_level_1, slot_level_2, slot_level_3, slot_level_4, slot_level_5,
                   slot_level_6, slot_level_7, slot_level_8, slot_level_9
            FROM class_spell_slots
            WHERE class_id = %s AND level = %s
        """
        
        slots_info = self.db.execute_query(slots_query, (class_id, level))
        
        if not slots_info:
            return []
        
        slots = slots_info[0]
        max_spell_level = 0
        
        # Определяем максимальный уровень заклинаний, для которого есть слоты
        slot_levels = [
            slots['slot_level_1'], slots['slot_level_2'], slots['slot_level_3'],
            slots['slot_level_4'], slots['slot_level_5'], slots['slot_level_6'],
            slots['slot_level_7'], slots['slot_level_8'], slots['slot_level_9']
        ]
        
        for i, slot_count in enumerate(slot_levels, 1):
            if slot_count and slot_count > 0:
                max_spell_level = i
        
        if max_spell_level == 0:
            return []
        
        # Получаем заклинания уровней 1-max_spell_level, доступные этому классу
        spells_query = """
            SELECT id, name, level, description, damage, damage_type, is_combat, is_area_of_effect
            FROM spells 
            WHERE level BETWEEN 1 AND %s AND available_classes LIKE %s
            ORDER BY level, name
        """
        
        spells = self.db.execute_query(spells_query, (max_spell_level, f'%"{class_name}"%'))
        return spells or []
    
    async def start_cantrip_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE, 
                                     char_data: dict):
        """Начинает процесс выбора заговоров."""
        class_id = char_data.get('class_id')
        
        if not self.db.connection or not self.db.connection.is_connected():
            self.db.connect()
        
        # Получаем количество заговоров, которые можно выбрать
        slots_query = "SELECT known_cantrips FROM class_spell_slots WHERE class_id = %s AND level = 1"
        slots_info = self.db.execute_query(slots_query, (class_id,))
        
        if not slots_info or not slots_info[0]['known_cantrips']:
            # Нет заговоров для этого класса, переходим к заклинаниям
            await self.start_spell_selection(update, context, char_data)
            return
        
        cantrips_to_select = slots_info[0]['known_cantrips']
        available_cantrips = self.get_available_cantrips(class_id)
        
        if not available_cantrips:
            await update.callback_query.edit_message_text(
                "❌ Нет доступных заговоров для вашего класса!"
            )
            return
        
        # Инициализируем выбранные заговоры
        char_data['selected_cantrips'] = []
        char_data['cantrips_to_select'] = cantrips_to_select
        char_data['available_cantrips'] = available_cantrips
        
        # Сохраняем в context для использования в callbacks
        context.user_data['char_data'] = char_data
        
        await self.display_cantrip_selection(update, context, char_data)
    
    async def display_cantrip_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE,
                                       char_data: dict):
        """Отображает список заговоров для выбора."""
        selected_count = len(char_data.get('selected_cantrips', []))
        total_count = char_data.get('cantrips_to_select', 0)
        available_cantrips = char_data.get('available_cantrips', [])
        selected_cantrips = char_data.get('selected_cantrips', [])
        
        # Фильтруем уже выбранные заговоры
        available_cantrips = [c for c in available_cantrips if c['id'] not in selected_cantrips]
        
        if selected_count >= total_count:
            # Все заговоры выбраны, переходим к заклинаниям
            await self.start_spell_selection(update, context, char_data)
            return
        
        # Создаем кнопки для каждого доступного заговора
        keyboard = []
        for cantrip in available_cantrips:
            cantrip_name = cantrip['name']
            damage_info = f" ({cantrip['damage']})" if cantrip['damage'] else ""
            combat_mark = " ⚔️" if cantrip['is_combat'] else ""
            aoe_mark = " [AoE]" if cantrip['is_area_of_effect'] else ""
            
            button_text = f"🔮 {cantrip_name}{damage_info}{combat_mark}{aoe_mark}"
            callback_data = f"select_cantrip_{cantrip['id']}"
            keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        header_text = f"🪄 Выбор заговоров ({selected_count}/{total_count})\n\n"
        header_text += f"Выберите заговор для изучения:\n\n"
        
        if selected_cantrips:
            selected_names = []
            for cantrip_id in selected_cantrips:
                cantrip = next((c for c in char_data.get('available_cantrips', []) if c['id'] == cantrip_id), None)
                if cantrip:
                    selected_names.append(cantrip['name'])
            header_text += f"✅ Выбрано: {', '.join(selected_names)}\n\n"
        
        await update.callback_query.edit_message_text(header_text, reply_markup=reply_markup)
    
    async def handle_cantrip_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обрабатывает выбор заговора."""
        query = update.callback_query
        cantrip_id = int(query.data.split('_')[2])
        
        char_data = context.user_data.get('char_data', {})
        
        if 'selected_cantrips' not in char_data:
            char_data['selected_cantrips'] = []
        
        # Добавляем заговор к выбранным
        if cantrip_id not in char_data['selected_cantrips']:
            char_data['selected_cantrips'].append(cantrip_id)
        
        # Обновляем данные в context
        context.user_data['char_data'] = char_data
        
        await self.display_cantrip_selection(update, context, char_data)
    
    async def start_spell_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE,
                                   char_data: dict):
        """Начинает процесс выбора заклинаний."""
        class_id = char_data.get('class_id')
        
        if not self.db.connection or not self.db.connection.is_connected():
            self.db.connect()
        
        # Получаем количество заклинаний, которые можно выбрать
        slots_query = "SELECT known_spells FROM class_spell_slots WHERE class_id = %s AND level = 1"
        slots_info = self.db.execute_query(slots_query, (class_id,))
        
        if not slots_info or not slots_info[0]['known_spells']:
            # Нет заклинаний для этого класса, завершаем выбор
            await self.finish_spell_selection(update, context, char_data)
            return
        
        spells_to_select = slots_info[0]['known_spells']
        available_spells = self.get_available_spells(class_id, 1)
        
        if not available_spells:
            await update.callback_query.edit_message_text(
                "❌ Нет доступных заклинаний для вашего класса!"
            )
            return
        
        # Инициализируем выбранные заклинания
        char_data['selected_spells'] = []
        char_data['spells_to_select'] = spells_to_select
        char_data['available_spells'] = available_spells
        
        # Сохраняем в context для использования в callbacks
        context.user_data['char_data'] = char_data
        
        await self.display_spell_selection(update, context, char_data)
    
    async def display_spell_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE,
                                     char_data: dict):
        """Отображает список заклинаний для выбора."""
        selected_count = len(char_data.get('selected_spells', []))
        total_count = char_data.get('spells_to_select', 0)
        available_spells = char_data.get('available_spells', [])
        selected_spells = char_data.get('selected_spells', [])
        
        # Фильтруем уже выбранные заклинания
        available_spells = [s for s in available_spells if s['id'] not in selected_spells]
        
        if selected_count >= total_count:
            # Все заклинания выбраны, завершаем выбор
            await self.finish_spell_selection(update, context, char_data)
            return
        
        # Группируем заклинания по уровням
        spells_by_level = {}
        for spell in available_spells:
            level = spell['level']
            if level not in spells_by_level:
                spells_by_level[level] = []
            spells_by_level[level].append(spell)
        
        # Создаем кнопки для каждого доступного заклинания
        keyboard = []
        for level in sorted(spells_by_level.keys()):
            for spell in spells_by_level[level]:
                spell_name = spell['name']
                damage_info = f" ({spell['damage']})" if spell['damage'] else ""
                combat_mark = " ⚔️" if spell['is_combat'] else ""
                aoe_mark = " [AoE]" if spell['is_area_of_effect'] else ""
                
                button_text = f"✨{level} {spell_name}{damage_info}{combat_mark}{aoe_mark}"
                callback_data = f"select_spell_{spell['id']}"
                keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        header_text = f"📚 Выбор заклинаний ({selected_count}/{total_count})\n\n"
        header_text += f"Выберите заклинание для изучения:\n\n"
        
        if selected_spells:
            selected_names = []
            for spell_id in selected_spells:
                spell = next((s for s in char_data.get('available_spells', []) if s['id'] == spell_id), None)
                if spell:
                    selected_names.append(f"{spell['name']} ({spell['level']}ур)")
            header_text += f"✅ Выбрано: {', '.join(selected_names)}\n\n"
        
        await update.callback_query.edit_message_text(header_text, reply_markup=reply_markup)
    
    async def handle_spell_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обрабатывает выбор заклинания."""
        query = update.callback_query
        spell_id = int(query.data.split('_')[2])
        
        char_data = context.user_data.get('char_data', {})
        
        if 'selected_spells' not in char_data:
            char_data['selected_spells'] = []
        
        # Добавляем заклинание к выбранным
        if spell_id not in char_data['selected_spells']:
            char_data['selected_spells'].append(spell_id)
        
        # Обновляем данные в context
        context.user_data['char_data'] = char_data
        
        await self.display_spell_selection(update, context, char_data)
    
    async def finish_spell_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE,
                                    char_data: dict):
        """Завершает выбор заклинаний и продолжает создание персонажа."""
        # Возвращаем управление обратно в character_generation
        from character_generation import character_gen
        
        # Обновляем данные персонажа
        context.user_data['char_data'] = char_data
        
        # Переходим к следующему шагу создания персонажа
        await character_gen.continue_after_spell_selection(update, context, char_data)
    
    def save_character_spells(self, character_id: int, selected_cantrips: list, selected_spells: list):
        """Сохраняет выбранные заклинания персонажа в базу данных."""
        if not self.db.connection or not self.db.connection.is_connected():
            self.db.connect()
        
        # Сохраняем заговоры
        for cantrip_id in selected_cantrips:
            self.db.execute_query(
                "INSERT INTO character_spells (character_id, spell_id) VALUES (%s, %s)",
                (character_id, cantrip_id)
            )
        
        # Сохраняем заклинания
        for spell_id in selected_spells:
            self.db.execute_query(
                "INSERT INTO character_spells (character_id, spell_id) VALUES (%s, %s)",
                (character_id, spell_id)
            )
        
        logger.info(f"Saved {len(selected_cantrips)} cantrips and {len(selected_spells)} spells for character {character_id}")

# Global instance
spell_selection_manager = SpellSelectionManager()
