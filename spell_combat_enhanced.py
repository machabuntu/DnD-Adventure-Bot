#!/usr/bin/env python3
"""
Улучшенный модуль для управления заклинаниями в боевой системе.
Полная поддержка скалирования заклинаний по уровню персонажа и слотам.
"""

import json
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import get_db
from dice_utils import roll_dice, roll_dice_detailed, is_critical_hit, is_critical_miss, calculate_modifier, roll_d20
from spell_slot_manager import spell_slot_manager
from spell_scaling import (
    get_cantrip_scaling, 
    get_spell_slot_scaling, 
    apply_spell_scaling_in_combat,
    calculate_scaled_damage,
    get_spell_scaling_rules
)
from saving_throws import saving_throw_manager

logger = logging.getLogger(__name__)

class EnhancedSpellCombatManager:
    def __init__(self):
        self.db = get_db()
    
    async def display_combat_spells(self, update: Update, character_id: int, adventure_id: int, turn_index: int):
        """Показывает список боевых заклинаний персонажа для выбора."""
        if not self.db.connection or not self.db.connection.is_connected():
            self.db.connect()
        
        # Получаем уровень персонажа
        char_query = "SELECT level FROM characters WHERE id = %s"
        char_result = self.db.execute_query(char_query, (character_id,))
        character_level = char_result[0]['level'] if char_result else 1
        
        # Получаем доступные слоты
        available_slots = spell_slot_manager.get_available_slots(character_id)
        
        # Получаем боевые заклинания персонажа
        combat_spells_query = """
            SELECT s.id, s.name, s.level, s.damage, s.damage_type, s.description, 
                   s.is_area_of_effect, s.scaling_type
            FROM character_spells cs
            JOIN spells s ON cs.spell_id = s.id
            WHERE cs.character_id = %s AND s.is_combat = TRUE
            ORDER BY s.level, s.name
        """
        
        combat_spells = self.db.execute_query(combat_spells_query, (character_id,))
        
        if not combat_spells:
            await update.callback_query.edit_message_text(
                "❌ У вас нет доступных боевых заклинаний!"
            )
            return
        
        # Фильтруем заклинания
        available_spells = []
        for spell in combat_spells:
            # Заговоры всегда доступны
            if spell['level'] == 0:
                available_spells.append(spell)
            # Для обычных заклинаний проверяем слоты
            elif spell_slot_manager.has_available_slot(character_id, spell['level']):
                available_spells.append(spell)
        
        if not available_spells:
            slot_info = spell_slot_manager.get_spell_slots_info(character_id)
            await update.callback_query.edit_message_text(
                f"❌ У вас нет доступных слотов для боевых заклинаний!\n\n{slot_info}"
            )
            return
        
        # Группируем доступные заклинания по уровням
        spells_by_level = {}
        for spell in available_spells:
            level = spell['level']
            if level not in spells_by_level:
                spells_by_level[level] = []
            spells_by_level[level].append(spell)
        
        # Создаем кнопки для заклинаний
        keyboard = []
        
        # Заговоры (0 уровень) с индикацией скалирования
        if 0 in spells_by_level:
            for spell in spells_by_level[0]:
                spell_name = spell['name']
                
                # Проверяем скалирование заговора
                if spell['scaling_type'] == 'cantrip_damage':
                    scaling = get_cantrip_scaling(spell['id'], character_level)
                    if scaling and 'damage_dice' in scaling:
                        damage_info = f" ({scaling['damage_dice']})"
                    else:
                        damage_info = f" ({spell['damage']})" if spell['damage'] else ""
                elif spell['scaling_type'] == 'cantrip_beams':
                    scaling = get_cantrip_scaling(spell['id'], character_level)
                    if scaling and 'num_beams' in scaling:
                        damage_info = f" ({spell['damage']} x{scaling['num_beams']})"
                    else:
                        damage_info = f" ({spell['damage']})" if spell['damage'] else ""
                else:
                    damage_info = f" ({spell['damage']})" if spell['damage'] else ""
                
                aoe_mark = " [AoE]" if spell['is_area_of_effect'] else ""
                
                button_text = f"🔮 {spell_name}{damage_info}{aoe_mark}"
                callback_data = f"cast_{character_id}_{adventure_id}_{turn_index}_{spell['id']}"
                keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
        
        # Заклинания более высоких уровней
        for level in range(1, 10):
            if level in spells_by_level:
                for spell in spells_by_level[level]:
                    spell_name = spell['name']
                    damage_info = f" ({spell['damage']})" if spell['damage'] else ""
                    aoe_mark = " [AoE]" if spell['is_area_of_effect'] else ""
                    
                    # Проверяем, есть ли скалирование
                    has_scaling = spell['scaling_type'] is not None
                    scaling_mark = " ⬆️" if has_scaling else ""
                    
                    button_text = f"✨{level} {spell_name}{damage_info}{aoe_mark}{scaling_mark}"
                    callback_data = f"cast_{character_id}_{adventure_id}_{turn_index}_{spell['id']}"
                    keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
        
        # Кнопка отмены
        keyboard.append([InlineKeyboardButton("❌ Отмена", 
                                             callback_data=f"cancel_spell_{character_id}_{adventure_id}_{turn_index}")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Получаем информацию о слотах для отображения
        slot_info = spell_slot_manager.get_spell_slots_info(character_id)
        spell_text = f"🪄 Выберите заклинание для использования:\n\n{slot_info}"
        spell_text += "\n\n⬆️ - заклинание можно усилить слотом высокого уровня"
        
        await update.callback_query.edit_message_text(spell_text, reply_markup=reply_markup)
    
    async def handle_spell_cast(self, update: Update, context: ContextTypes.DEFAULT_TYPE, 
                               character_id: int, adventure_id: int, turn_index: int, spell_id: int):
        """Обрабатывает использование заклинания персонажем."""
        if not self.db.connection or not self.db.connection.is_connected():
            self.db.connect()
        
        # Получаем информацию о персонаже
        char_query = "SELECT name, level FROM characters WHERE id = %s"
        char_result = self.db.execute_query(char_query, (character_id,))
        if not char_result:
            await update.callback_query.edit_message_text("❌ Персонаж не найден!")
            return
        
        char_name = char_result[0]['name']
        character_level = char_result[0]['level']
        
        # Получаем информацию о заклинании
        spell_query = """
            SELECT s.name, s.level, s.damage, s.damage_type, s.description, 
                   s.is_area_of_effect, s.scaling_type, s.base_scaling_info
            FROM spells s
            WHERE s.id = %s
        """
        
        spell_info = self.db.execute_query(spell_query, (spell_id,))
        if not spell_info:
            await update.callback_query.edit_message_text("❌ Заклинание не найдено!")
            return
        
        spell = spell_info[0]
        spell_name = spell['name']
        spell_level = spell['level']
        
        # Проверяем, есть ли у персонажа это заклинание
        char_spell_query = "SELECT id FROM character_spells WHERE character_id = %s AND spell_id = %s"
        has_spell = self.db.execute_query(char_spell_query, (character_id, spell_id))
        
        if not has_spell:
            await update.callback_query.edit_message_text(
                f"❌ У вас нет заклинания '{spell_name}'!"
            )
            return
        
        # Для заговоров не нужно выбирать слот
        if spell_level == 0:
            await self._cast_cantrip(update, character_id, adventure_id, turn_index, 
                                    spell_id, spell, char_name, character_level)
        else:
            # Для обычных заклинаний проверяем наличие скалирования
            if spell['scaling_type'] and spell['scaling_type'].startswith('slot_'):
                # Заклинание можно усилить - предлагаем выбор слота
                await self._select_spell_slot(update, character_id, adventure_id, turn_index, 
                                             spell_id, spell)
            else:
                # Заклинание без скалирования - используем минимальный доступный слот
                slot_level = spell_slot_manager.use_spell_slot(character_id, spell_level)
                if slot_level is None:
                    slot_info = spell_slot_manager.get_spell_slots_info(character_id)
                    await update.callback_query.edit_message_text(
                        f"❌ Нет доступных слотов для заклинания '{spell_name}' (уровень {spell_level})!\n\n{slot_info}"
                    )
                    return
                
                await self._execute_spell(update, character_id, adventure_id, turn_index, 
                                         spell_id, spell, char_name, character_level, slot_level)
    
    async def _select_spell_slot(self, update: Update, character_id: int, adventure_id: int, 
                                turn_index: int, spell_id: int, spell: dict):
        """Предлагает выбор слота для заклинания с возможностью усиления."""
        # Получаем доступные слоты
        available_slots = spell_slot_manager.get_available_slots(character_id)
        
        # Фильтруем слоты, которые можно использовать для этого заклинания
        usable_slots = []
        for slot_level, (used, max_slots) in available_slots.items():
            if slot_level >= spell['level'] and used < max_slots:
                usable_slots.append(slot_level)
        
        if not usable_slots:
            slot_info = spell_slot_manager.get_spell_slots_info(character_id)
            await update.callback_query.edit_message_text(
                f"❌ Нет доступных слотов для заклинания '{spell['name']}'!\n\n{slot_info}"
            )
            return
        
        # Создаем кнопки для выбора слота
        keyboard = []
        
        for slot_level in sorted(usable_slots):
            button_text = f"📊 Слот {slot_level} уровня"
            
            # Добавляем информацию об усилении
            if slot_level > spell['level']:
                scaling = get_spell_slot_scaling(spell_id, slot_level)
                if scaling:
                    if 'damage_bonus' in scaling:
                        button_text += f" (+урон)"
                    if 'target_bonus' in scaling:
                        button_text += f" (+цели: {scaling['target_bonus']})"
                    if 'other_effects' in scaling:
                        effects = scaling['other_effects']
                        if 'projectiles' in effects:
                            button_text += f" ({effects['projectiles']})"
                        elif 'healing' in effects:
                            button_text += f" ({effects['healing']})"
            
            callback_data = f"use_slot_{character_id}_{adventure_id}_{turn_index}_{spell_id}_{slot_level}"
            keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
        
        # Кнопка отмены
        keyboard.append([InlineKeyboardButton("❌ Отмена", 
                                             callback_data=f"cancel_spell_{character_id}_{adventure_id}_{turn_index}")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        message_text = f"🎯 Выберите слот для заклинания '{spell['name']}' (минимум {spell['level']} уровня):"
        
        # Добавляем описание усиления
        if spell['base_scaling_info']:
            scaling_info = json.loads(spell['base_scaling_info'])
            if 'description' in scaling_info:
                message_text += f"\n\n📈 Усиление: {scaling_info['description']}"
        
        await update.callback_query.edit_message_text(message_text, reply_markup=reply_markup)
    
    async def handle_slot_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE,
                                   character_id: int, adventure_id: int, turn_index: int, 
                                   spell_id: int, slot_level: int):
        """Обрабатывает выбор слота для заклинания."""
        if not self.db.connection or not self.db.connection.is_connected():
            self.db.connect()
        
        # Получаем информацию о персонаже и заклинании
        char_query = "SELECT name, level FROM characters WHERE id = %s"
        char_result = self.db.execute_query(char_query, (character_id,))
        char_name = char_result[0]['name'] if char_result else "Неизвестный"
        character_level = char_result[0]['level'] if char_result else 1
        
        spell_query = """
            SELECT name, level, damage, damage_type, description, is_area_of_effect, scaling_type
            FROM spells WHERE id = %s
        """
        spell_info = self.db.execute_query(spell_query, (spell_id,))
        if not spell_info:
            await update.callback_query.edit_message_text("❌ Заклинание не найдено!")
            return
        
        spell = spell_info[0]
        
        # Используем выбранный слот
        used_slot = spell_slot_manager.use_spell_slot(character_id, spell['level'])
        if used_slot != slot_level:
            # Если автоматически был использован другой слот, возвращаем его и используем выбранный
            if used_slot is not None:
                spell_slot_manager.restore_spell_slot(character_id, used_slot)
            
            # Используем конкретный слот
            success = self.db.execute_query("""
                UPDATE character_spell_slots
                SET used_slots = used_slots + 1
                WHERE character_id = %s AND slot_level = %s AND used_slots < max_slots
            """, (character_id, slot_level))
            
            if not success:
                await update.callback_query.edit_message_text(
                    f"❌ Не удалось использовать слот {slot_level} уровня!"
                )
                return
        
        await self._execute_spell(update, character_id, adventure_id, turn_index, 
                                 spell_id, spell, char_name, character_level, slot_level)
    
    async def _cast_cantrip(self, update: Update, character_id: int, adventure_id: int, 
                          turn_index: int, spell_id: int, spell: dict, char_name: str, character_level: int):
        """Использует заговор с учетом уровня персонажа."""
        # Получаем скалирование заговора
        scaling = apply_spell_scaling_in_combat(spell_id, spell['damage'], character_level=character_level)
        
        # Если заговор имеет несколько лучей/атак
        if scaling['num_attacks'] > 1 and spell['damage']:
            # Показываем выбор целей для каждого луча
            await self._select_beam_targets(update, character_id, adventure_id, turn_index, 
                                          spell_id, spell, char_name, character_level, scaling)
        else:
            # Обычное использование заговора
            await self._execute_spell(update, character_id, adventure_id, turn_index, 
                                     spell_id, spell, char_name, character_level, None)
    
    async def _select_beam_targets(self, update: Update, character_id: int, adventure_id: int,
                                  turn_index: int, spell_id: int, spell: dict, char_name: str,
                                  character_level: int, scaling: dict):
        """Выбор целей для заговора с несколькими лучами."""
        if not self.db.connection or not self.db.connection.is_connected():
            self.db.connect()
        
        # Получаем всех живых врагов
        enemies_query = """
            SELECT e.id, e.name, e.current_hp, e.max_hp
            FROM combat_participants cp
            JOIN enemies e ON cp.participant_id = e.id
            WHERE cp.adventure_id = %s AND cp.participant_type = 'enemy' AND e.current_hp > 0
        """
        
        alive_enemies = self.db.execute_query(enemies_query, (adventure_id,))
        
        if not alive_enemies:
            await update.callback_query.edit_message_text("❌ Нет доступных целей для заклинания!")
            return
        
        num_beams = scaling['num_attacks']
        spell_name = spell['name']
        
        # Сохраняем информацию о лучах в контексте
        context_key = f"beam_targets_{character_id}_{spell_id}"
        if context_key not in update.callback_query.message.chat.data:
            update.callback_query.message.chat.data[context_key] = {
                'targets': [],
                'num_beams': num_beams,
                'current_beam': 1
            }
        
        beam_data = update.callback_query.message.chat.data[context_key]
        current_beam = beam_data['current_beam']
        
        # Создаем кнопки для каждого врага
        keyboard = []
        for enemy in alive_enemies:
            enemy_name = enemy['name']
            hp_info = f" ({enemy['current_hp']}/{enemy['max_hp']} HP)"
            button_text = f"{enemy_name}{hp_info}"
            callback_data = f"beam_target_{character_id}_{adventure_id}_{turn_index}_{spell_id}_{enemy['id']}_{current_beam}"
            keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
        
        # Кнопка отмены
        keyboard.append([InlineKeyboardButton("❌ Отмена", 
                                             callback_data=f"cancel_spell_{character_id}_{adventure_id}_{turn_index}")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        message_text = f"🎯 {char_name} использует '{spell_name}'\n"
        message_text += f"Луч {current_beam} из {num_beams}. Выберите цель:"
        
        if beam_data['targets']:
            message_text += f"\n\nВыбранные цели: {', '.join([t['name'] for t in beam_data['targets']])}"
        
        await update.callback_query.edit_message_text(message_text, reply_markup=reply_markup)
    
    async def _execute_spell(self, update: Update, character_id: int, adventure_id: int,
                            turn_index: int, spell_id: int, spell: dict, char_name: str,
                            character_level: int, slot_level: int = None):
        """Выполняет заклинание с учетом всех параметров скалирования."""
        # Получаем параметры скалирования
        scaling = apply_spell_scaling_in_combat(
            spell_id, 
            spell['damage'], 
            slot_level=slot_level,
            character_level=character_level if spell['level'] == 0 else None
        )
        
        # Если заклинание наносит урон
        if spell['damage']:
            if spell['is_area_of_effect']:
                # AoE заклинание
                await self._cast_aoe_spell(update, character_id, adventure_id, spell_id, spell, 
                                          char_name, scaling, slot_level)
            elif scaling['num_targets'] > 1:
                # Заклинание с несколькими целями
                await self._select_multiple_targets(update, character_id, adventure_id, 
                                                   turn_index, spell_id, spell, char_name, 
                                                   scaling, slot_level)
            else:
                # Одиночная цель
                await self._display_spell_targets(update, character_id, adventure_id, 
                                                 turn_index, spell, char_name, scaling, slot_level)
        else:
            # Вспомогательное заклинание
            await self._cast_utility_spell(update, character_id, adventure_id, spell, 
                                          char_name, slot_level)
    
    async def _display_spell_targets(self, update: Update, character_id: int, adventure_id: int,
                                    turn_index: int, spell: dict, char_name: str, 
                                    scaling: dict, slot_level: int = None):
        """Показывает доступные цели для заклинания."""
        if not self.db.connection or not self.db.connection.is_connected():
            self.db.connect()
        
        # Получаем всех живых врагов
        enemies_query = """
            SELECT e.id, e.name, e.current_hp, e.max_hp
            FROM combat_participants cp
            JOIN enemies e ON cp.participant_id = e.id
            WHERE cp.adventure_id = %s AND cp.participant_type = 'enemy' AND e.current_hp > 0
        """
        
        alive_enemies = self.db.execute_query(enemies_query, (adventure_id,))
        
        if not alive_enemies:
            await update.callback_query.edit_message_text("❌ Нет доступных целей для заклинания!")
            return
        
        # Создаем кнопки для каждого врага
        keyboard = []
        for enemy in alive_enemies:
            enemy_name = enemy['name']
            hp_info = f" ({enemy['current_hp']}/{enemy['max_hp']} HP)"
            callback_data = f"spell_target_enh_{character_id}_{adventure_id}_{turn_index}_{spell['id']}_{enemy['id']}_{slot_level or 0}"
            keyboard.append([InlineKeyboardButton(enemy_name + hp_info, callback_data=callback_data)])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        spell_name = spell['name']
        if slot_level and slot_level > spell['level']:
            spell_name += f" (слот {slot_level} ур.)"
        
        damage_info = f" ({scaling['damage']} {spell['damage_type']})" if spell['damage_type'] else f" ({scaling['damage']})"
        
        await update.callback_query.edit_message_text(
            f"🎯 {char_name} использует '{spell_name}'{damage_info}\n\nВыберите цель:",
            reply_markup=reply_markup
        )
    
    async def _select_multiple_targets(self, update: Update, character_id: int, adventure_id: int,
                                      turn_index: int, spell_id: int, spell: dict, char_name: str,
                                      scaling: dict, slot_level: int = None):
        """Выбор нескольких целей для заклинания."""
        # TODO: Реализовать выбор нескольких целей
        # Пока используем упрощенную версию - атакуем первые N целей
        await self._cast_multi_target_spell(update, character_id, adventure_id, spell, 
                                           char_name, scaling, slot_level)
    
    async def _cast_aoe_spell(self, update: Update, character_id: int, adventure_id: int, spell_id: int,
                             spell: dict, char_name: str, scaling: dict, slot_level: int = None):
        """Применяет заклинание по области."""
        if not self.db.connection or not self.db.connection.is_connected():
            self.db.connect()
        
        # Получаем всех живых врагов
        enemies_query = """
            SELECT e.id, e.name, e.current_hp, e.max_hp, e.armor_class
            FROM combat_participants cp
            JOIN enemies e ON cp.participant_id = e.id
            WHERE cp.adventure_id = %s AND cp.participant_type = 'enemy' AND e.current_hp > 0
        """
        
        alive_enemies = self.db.execute_query(enemies_query, (adventure_id,))
        
        if not alive_enemies:
            await update.callback_query.edit_message_text("❌ Нет целей для заклинания!")
            return
        
        spell_name = spell['name']
        if slot_level and slot_level > spell['level']:
            spell_name += f" (слот {slot_level} ур.)"
        
        result_text = f"🔥 {char_name} использует '{spell_name}' по области!\n\n"
        
        enemies_defeated = []
        
        # Вычисляем урон один раз для всех
        damage_result = self._roll_spell_damage(scaling['damage'])
        
        # Обрабатываем спасброски для всех целей
        saving_throw_results = saving_throw_manager.process_aoe_saving_throws(
            spell_id, character_id, 
            [{'id': e['id'], 'type': 'enemy'} for e in alive_enemies]
        )
        
        for enemy in alive_enemies:
            enemy_id = enemy['id']
            enemy_name = enemy['name']
            
            # Проверяем результат спасброска
            save_success, save_text = saving_throw_results.get(enemy_id, (False, ""))
            
            result_text += f"\n**{enemy_name}**:\n{save_text}\n"
            
            # Определяем урон
            damage_taken = damage_result['total']
            if save_success:
                # Успешный спасбросок - урон в два раза меньше
                damage_taken //= 2
                result_text += f"💥 Урон (половина): {damage_taken} {spell['damage_type']}\n"
            else:
                # Проваленный спасбросок - полный урон
                result_text += f"💥 Урон: {damage_taken} {spell['damage_type']}\n"
            
            # Применяем урон
            new_hp = max(0, enemy['current_hp'] - damage_taken)
            self.db.execute_query("UPDATE enemies SET current_hp = %s WHERE id = %s",
                                 (new_hp, enemy_id))
            
            if new_hp <= 0:
                enemies_defeated.append(enemy_name)
        
        if enemies_defeated:
            result_text += f"\n💀 Повержены: {', '.join(enemies_defeated)}"
        
        await update.callback_query.edit_message_text(result_text)
        
        # Проверяем окончание боя
        alive_enemies_query = "SELECT COUNT(*) as count FROM enemies WHERE adventure_id = %s AND current_hp > 0"
        alive_enemies_check = self.db.execute_query(alive_enemies_query, (adventure_id,))
        
        if alive_enemies_check and alive_enemies_check[0]['count'] == 0:
            from combat_manager import combat_manager
            await combat_manager.end_combat(update.callback_query, adventure_id, victory='players')
    
    async def _cast_multi_target_spell(self, update: Update, character_id: int, adventure_id: int,
                                      spell: dict, char_name: str, scaling: dict, slot_level: int = None):
        """Применяет заклинание к нескольким целям."""
        if not self.db.connection or not self.db.connection.is_connected():
            self.db.connect()
        
        # Получаем живых врагов
        enemies_query = """
            SELECT e.id, e.name, e.current_hp, e.max_hp
            FROM combat_participants cp
            JOIN enemies e ON cp.participant_id = e.id
            WHERE cp.adventure_id = %s AND cp.participant_type = 'enemy' AND e.current_hp > 0
            LIMIT %s
        """
        
        num_targets = scaling['num_targets']
        targets = self.db.execute_query(enemies_query, (adventure_id, num_targets))
        
        if not targets:
            await update.callback_query.edit_message_text("❌ Нет целей для заклинания!")
            return
        
        spell_name = spell['name']
        if slot_level and slot_level > spell['level']:
            spell_name += f" (слот {slot_level} ур.)"
        
        result_text = f"✨ {char_name} использует '{spell_name}'!\n"
        result_text += f"Поражает {len(targets)} целей:\n\n"
        
        for target in targets:
            damage_result = self._roll_spell_damage(scaling['damage'])
            result_text += f"💥 {target['name']}: {damage_result['text']} {spell['damage_type']} урона\n"
            
            new_hp = max(0, target['current_hp'] - damage_result['total'])
            self.db.execute_query("UPDATE enemies SET current_hp = %s WHERE id = %s",
                                 (new_hp, target['id']))
            
            if new_hp <= 0:
                result_text += f"   💀 {target['name']} повержен!\n"
        
        await update.callback_query.edit_message_text(result_text)
    
    async def _cast_utility_spell(self, update: Update, character_id: int, adventure_id: int,
                                 spell: dict, char_name: str, slot_level: int = None):
        """Применяет вспомогательное заклинание."""
        spell_name = spell['name']
        if slot_level and slot_level > spell['level']:
            spell_name += f" (слот {slot_level} ур.)"
        
        result_text = f"✨ {char_name} использует заклинание '{spell_name}'!\n"
        
        # Добавляем описание эффекта
        if spell['description']:
            result_text += f"\n📜 {spell['description']}"
        
        # Добавляем информацию об усилении
        if slot_level and slot_level > spell['level']:
            scaling = get_spell_slot_scaling(spell['id'], slot_level)
            if scaling:
                result_text += f"\n\n📈 Усиление (слот {slot_level} уровня):"
                if 'duration_bonus' in scaling:
                    result_text += f"\n  • Длительность: {scaling['duration_bonus']}"
                if 'other_effects' in scaling:
                    effects = scaling['other_effects']
                    for key, value in effects.items():
                        result_text += f"\n  • {value}"
        
        await update.callback_query.edit_message_text(result_text)
    
    def _roll_spell_damage(self, damage_dice: str, critical: bool = False) -> dict:
        """Бросает кубики урона заклинания."""
        if critical:
            # Для критического попадания удваиваем кубики
            total1, rolls1, modifier1, _ = roll_dice_detailed(damage_dice)
            total2, rolls2, modifier2, _ = roll_dice_detailed(damage_dice)
            
            all_rolls = rolls1 + rolls2
            total_damage = sum(all_rolls) + modifier1  # Модификатор не удваивается
            
            if len(all_rolls) == 1:
                if modifier1 != 0:
                    damage_text = f"{all_rolls[0]} + {modifier1} = {total_damage}"
                else:
                    damage_text = f"{all_rolls[0]} = {total_damage}"
            else:
                rolls_str = " + ".join(map(str, all_rolls))
                if modifier1 != 0:
                    damage_text = f"{rolls_str} + {modifier1} = {total_damage}"
                else:
                    damage_text = f"{rolls_str} = {total_damage}"
        else:
            # Обычный урон
            total_damage, damage_text = roll_dice(damage_dice)
        
        return {
            'total': total_damage,
            'text': damage_text
        }

# Global instance
enhanced_spell_combat_manager = EnhancedSpellCombatManager()
