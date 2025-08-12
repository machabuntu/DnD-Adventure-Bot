#!/usr/bin/env python3
"""
Модуль для управления заклинаниями в боевой системе.
Обрабатывает использование заклинаний в бою, проверку слотов, выбор целей и нанесение урона.
"""

import json
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import get_db
from dice_utils import roll_dice, roll_dice_detailed, is_critical_hit, is_critical_miss
from spell_slot_manager import spell_slot_manager
from achievement_manager import achievement_manager
from combat_achievements import record_damage_dealt, record_kill

logger = logging.getLogger(__name__)

class SpellCombatManager:
    def __init__(self):
        self.db = get_db()
    
    async def display_combat_spells(self, update: Update, character_id: int, adventure_id: int, turn_index: int):
        """Показывает список боевых заклинаний персонажа для выбора."""
        if not self.db.connection or not self.db.connection.is_connected():
            self.db.connect()
        
        # Получаем боевые заклинания персонажа и доступные слоты
        available_slots = spell_slot_manager.get_available_slots(character_id)
        
        # Получаем боевые заклинания персонажа, доступные с учетом слотов
        combat_spells_query = """
            SELECT s.id, s.name, s.level, s.damage, s.damage_type, s.description, s.is_area_of_effect
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
        
        # Фильтруем заклинания - показываем только те, для которых есть слоты
        available_spells = []
        for spell in combat_spells:
            if spell_slot_manager.has_available_slot(character_id, spell['level']):
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
        
        # Сначала заговоры (0 уровень)
        if 0 in spells_by_level:
            for spell in spells_by_level[0]:
                spell_name = spell['name']
                damage_info = f" ({spell['damage']})" if spell['damage'] else ""
                aoe_mark = " [AoE]" if spell['is_area_of_effect'] else ""
                
                button_text = f"🔮 {spell_name}{damage_info}{aoe_mark}"
                callback_data = f"cast_{character_id}_{adventure_id}_{turn_index}_{spell['id']}"
                keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
        
        # Затем заклинания более высоких уровней
        for level in range(1, 10):
            if level in spells_by_level:
                for spell in spells_by_level[level]:
                    spell_name = spell['name']
                    damage_info = f" ({spell['damage']})" if spell['damage'] else ""
                    aoe_mark = " [AoE]" if spell['is_area_of_effect'] else ""
                    
                    button_text = f"✨{level} {spell_name}{damage_info}{aoe_mark}"
                    callback_data = f"cast_{character_id}_{adventure_id}_{turn_index}_{spell['id']}"
                    keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
        
        # Кнопка отмены
        keyboard.append([InlineKeyboardButton("❌ Отмена", 
                                             callback_data=f"cancel_spell_{character_id}_{adventure_id}_{turn_index}")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if not keyboard or len(keyboard) == 1:  # Только кнопка отмены
            slot_info = spell_slot_manager.get_spell_slots_info(character_id)
            await update.callback_query.edit_message_text(
                f"❌ У вас нет доступных слотов для боевых заклинаний!\n\n{slot_info}"
            )
        else:
            # Получаем информацию о слотах для отображения
            slot_info = spell_slot_manager.get_spell_slots_info(character_id)
            spell_text = f"🪄 Выберите заклинание для использования:\n\n{slot_info}"
            
            await update.callback_query.edit_message_text(spell_text, reply_markup=reply_markup)
    
    async def handle_spell_cast(self, update: Update, context: ContextTypes.DEFAULT_TYPE, 
                               character_id: int, adventure_id: int, turn_index: int, spell_id: int):
        """Обрабатывает использование заклинания персонажем."""
        if not self.db.connection or not self.db.connection.is_connected():
            self.db.connect()
        
        # Получаем информацию о заклинании
        spell_query = """
            SELECT s.name, s.level, s.damage, s.damage_type, s.description, s.is_area_of_effect
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
        
        # Проверяем и используем слот заклинания
        if not spell_slot_manager.has_available_slot(character_id, spell_level):
            slot_info = spell_slot_manager.get_spell_slots_info(character_id)
            await update.callback_query.edit_message_text(
                f"❌ Нет доступных слотов для заклинания '{spell_name}' (уровень {spell_level})!\n\n{slot_info}"
            )
            return
        
        # Используем слот
        used_slot_level = spell_slot_manager.use_spell_slot(character_id, spell_level)
        if used_slot_level is None:
            await update.callback_query.edit_message_text(
                f"❌ Не удалось использовать слот для заклинания '{spell_name}'!"
            )
            return
        
        # Получаем имя персонажа
        char_query = "SELECT name FROM characters WHERE id = %s"
        char_result = self.db.execute_query(char_query, (character_id,))
        char_name = char_result[0]['name'] if char_result else "Неизвестный"
        
        # Если заклинание наносит урон, показываем цели для выбора
        if spell['damage']:
            if spell['is_area_of_effect']:
                # AoE заклинание - атакует всех врагов
                await self.cast_aoe_spell(update, character_id, adventure_id, spell, char_name, context, turn_index)
            else:
                # Одиночное заклинание - выбираем цель
                await self.display_spell_targets(update, character_id, adventure_id, turn_index, spell, char_name)
        else:
            # Вспомогательное заклинание - применяем без выбора цели
            await self.cast_utility_spell(update, character_id, adventure_id, spell, char_name, context, turn_index)
    
    async def display_spell_targets(self, update: Update, character_id: int, adventure_id: int, 
                                   turn_index: int, spell: dict, char_name: str):
        """Показывает доступные цели для заклинания."""
        if not self.db.connection or not self.db.connection.is_connected():
            self.db.connect()
        
        # Получаем всех живых врагов
        enemies_query = """
            SELECT e.id, e.name, e.hit_points, e.max_hit_points
            FROM combat_participants cp
            JOIN enemies e ON cp.participant_id = e.id
            WHERE cp.adventure_id = %s AND cp.participant_type = 'enemy' AND e.hit_points > 0
        """
        
        alive_enemies = self.db.execute_query(enemies_query, (adventure_id,))
        
        if not alive_enemies:
            await update.callback_query.edit_message_text("❌ Нет доступных целей для заклинания!")
            return
        
        # Получаем ID заклинания из базы данных, если это необходимо
        spell_id_query = "SELECT id FROM spells WHERE name = %s AND level = %s"
        spell_id_result = self.db.execute_query(spell_id_query, (spell['name'], spell['level']))
        spell_id = spell_id_result[0]['id'] if spell_id_result else 0
        
        # Создаем кнопки для каждого врага
        keyboard = []
        for enemy in alive_enemies:
            enemy_name = enemy['name']
            callback_data = f"spell_target_{character_id}_{adventure_id}_{turn_index}_{spell_id}_{enemy['id']}"
            keyboard.append([InlineKeyboardButton(enemy_name, callback_data=callback_data)])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        spell_name = spell['name']
        damage_info = f" ({spell['damage']} {spell['damage_type']})" if spell['damage_type'] else f" ({spell['damage']})"
        
        await update.callback_query.edit_message_text(
            f"🎯 {char_name} использует '{spell_name}'{damage_info}\n\nВыберите цель:",
            reply_markup=reply_markup
        )
    
    async def cast_single_target_spell(self, update: Update, character_id: int, adventure_id: int,
                                      spell_id: int, target_id: int):
        """Применяет одиночное боевое заклинание к цели."""
        if not self.db.connection or not self.db.connection.is_connected():
            self.db.connect()
        
        # Получаем информацию о заклинании
        spell_query = """
            SELECT name, level, damage, damage_type, description
            FROM spells WHERE id = %s
        """
        
        spell_info = self.db.execute_query(spell_query, (spell_id,))
        if not spell_info:
            await update.callback_query.edit_message_text("❌ Заклинание не найдено!")
            return
        
        spell = spell_info[0]
        
        # Получаем информацию о персонаже
        char_query = "SELECT name FROM characters WHERE id = %s"
        char_result = self.db.execute_query(char_query, (character_id,))
        char_name = char_result[0]['name'] if char_result else "Неизвестный"
        
        # Получаем информацию о цели
        target_query = "SELECT name, hit_points, armor_class FROM enemies WHERE id = %s"
        target_result = self.db.execute_query(target_query, (target_id,))
        
        if not target_result:
            await update.callback_query.edit_message_text("❌ Цель не найдена!")
            return
        
        target = target_result[0]
        target_name = target['name']
        target_ac = target['armor_class'] or 12
        
        spell_name = spell['name']
        result_text = f"✨ {char_name} использует заклинание '{spell_name}' на {target_name}!\n"
        
        # Проверяем достижение за первое заклинание
        user_query = "SELECT user_id FROM characters WHERE id = %s"
        user_result = self.db.execute_query(user_query, (character_id,))
        user_id = user_result[0]['user_id'] if user_result else None
        if user_id:
            ach = achievement_manager.grant_achievement(user_id, 'first_spell', char_name)
        
        # Проверяем, требует ли заклинание броска атаки или спасброска
        spell_check_query = "SELECT saving_throw FROM spells WHERE id = %s"
        spell_check = self.db.execute_query(spell_check_query, (spell_id,))
        has_saving_throw = spell_check and spell_check[0]['saving_throw'] is not None
        
        # Если нет спасброска и заклинание наносит урон - требуется бросок атаки
        if spell['damage'] and not has_saving_throw:
            # Заклинания, требующие броска атаки
            from dice_utils import calculate_modifier
            
            # Получаем характеристику заклинателя из таблицы классов
            char_stats_query = """
                SELECT c.intelligence, c.wisdom, c.charisma, cl.spellcasting_ability
                FROM characters c
                JOIN classes cl ON c.class_id = cl.id
                WHERE c.id = %s
            """
            
            char_stats = self.db.execute_query(char_stats_query, (character_id,))
            if not char_stats:
                spell_modifier = 0
            else:
                stats = char_stats[0]
                spellcasting_ability = stats['spellcasting_ability']
                
                # Определяем модификатор на основе заклинательной характеристики класса
                if spellcasting_ability == "Интеллект":
                    spell_modifier = calculate_modifier(stats['intelligence'])
                elif spellcasting_ability == "Мудрость":
                    spell_modifier = calculate_modifier(stats['wisdom'])
                elif spellcasting_ability == "Харизма":
                    spell_modifier = calculate_modifier(stats['charisma'])
                else:
                    # Если класс не заклинатель, используем основную характеристику
                    spell_modifier = 0
            
            proficiency_bonus = 2  # Упрощенно для 1-5 уровня
            spell_attack_bonus = spell_modifier + proficiency_bonus
            
            from dice_utils import roll_d20
            attack_roll_result, attack_breakdown = roll_d20(spell_attack_bonus)
            raw_roll = attack_roll_result - spell_attack_bonus
            
            result_text += f"🎲 Бросок атаки заклинанием: {attack_breakdown} против AC {target_ac}"
            
            if is_critical_hit(raw_roll):
                result_text += f"\n🎯 КРИТИЧЕСКОЕ ПОПАДАНИЕ! (натуральная 20)"
                damage_result = self._roll_spell_damage(spell['damage'], critical=True)
                result_text += f"\n💥 Урон: {damage_result['text']} {spell['damage_type']} урона"
                
                # Применяем урон
                new_hp = max(0, target['hit_points'] - damage_result['total'])
                self.db.execute_query("UPDATE enemies SET hit_points = %s WHERE id = %s",
                                     (new_hp, target_id))
                
                # Метрики нанесенного урона
                try:
                    dealt = target['hit_points'] - new_hp
                    if dealt > 0:
                        record_damage_dealt(adventure_id, character_id, dealt)
                except Exception as e:
                    logger.warning(f"COMBAT METRICS WARNING: record_damage_dealt failed: {e}")
                
                # Проверяем достижения за урон
                if user_id:
                    ach_damage = achievement_manager.check_damage_achievement(user_id, damage_result['total'], char_name)
                
                if new_hp <= 0:
                    result_text += f"\n💀 {target_name} повержен заклинанием!"
                    try:
                        record_kill(adventure_id, character_id, 1)
                    except Exception as e:
                        logger.warning(f"COMBAT METRICS WARNING: record_kill failed: {e}")
                
            elif is_critical_miss(raw_roll):
                result_text += f"\n💨 КРИТИЧЕСКИЙ ПРОМАХ! (натуральная 1)"
                
            elif attack_roll_result >= target_ac:
                result_text += f"\n✅ ПОПАДАНИЕ!"
                damage_result = self._roll_spell_damage(spell['damage'])
                result_text += f"\n💥 Урон: {damage_result['text']} {spell['damage_type']} урона"
                
                # Применяем урон
                new_hp = max(0, target['hit_points'] - damage_result['total'])
                self.db.execute_query("UPDATE enemies SET hit_points = %s WHERE id = %s",
                                     (new_hp, target_id))
                
                # Проверяем достижения за урон
                if user_id:
                    ach_damage = achievement_manager.check_damage_achievement(user_id, damage_result['total'], char_name)
                
                if new_hp <= 0:
                    result_text += f"\n💀 {target_name} повержен заклинанием!"
            else:
                result_text += f"\n❌ ПРОМАХ!"
        else:
            # Заклинания, автоматически попадающие (например, Магическая стрела)
            result_text += f"\n✨ Заклинание автоматически попадает!"
            
            if spell['damage']:
                damage_result = self._roll_spell_damage(spell['damage'])
                result_text += f"\n💥 Урон: {damage_result['text']} {spell['damage_type']} урона"
                
                # Применяем урон
                new_hp = max(0, target['hit_points'] - damage_result['total'])
                self.db.execute_query("UPDATE enemies SET hit_points = %s WHERE id = %s",
                                     (new_hp, target_id))
                
                if new_hp <= 0:
                    result_text += f"\n💀 {target_name} повержен заклинанием!"
        
        await update.callback_query.edit_message_text(result_text)
        
        # Проверяем, остались ли живые враги
        alive_enemies_query = "SELECT COUNT(*) as count FROM enemies WHERE adventure_id = %s AND hit_points > 0"
        alive_enemies = self.db.execute_query(alive_enemies_query, (adventure_id,))
        
        if alive_enemies and alive_enemies[0]['count'] == 0:
            from combat_manager import combat_manager
            await combat_manager.end_combat(update.callback_query, adventure_id, victory='players')
    
    async def cast_aoe_spell(self, update: Update, character_id: int, adventure_id: int, 
                            spell: dict, char_name: str, context: ContextTypes.DEFAULT_TYPE = None, turn_index: int = None):
        """Применяет заклинание по области (AoE) ко всем врагам."""
        if not self.db.connection or not self.db.connection.is_connected():
            self.db.connect()
        
        # Получаем всех живых врагов
        enemies_query = """
            SELECT e.id, e.name, e.hit_points, e.max_hit_points, e.armor_class
            FROM combat_participants cp
            JOIN enemies e ON cp.participant_id = e.id
            WHERE cp.adventure_id = %s AND cp.participant_type = 'enemy' AND e.hit_points > 0
        """
        
        alive_enemies = self.db.execute_query(enemies_query, (adventure_id,))
        
        if not alive_enemies:
            await update.callback_query.edit_message_text("❌ Нет целей для заклинания!")
            return
        
        spell_name = spell['name']
        
        # Получаем информацию о спасброске из базы данных
        spell_save_query = "SELECT saving_throw FROM spells WHERE name = %s AND level = %s"
        spell_save_result = self.db.execute_query(spell_save_query, (spell_name, spell['level']))
        saving_throw_type = spell_save_result[0]['saving_throw'] if spell_save_result and spell_save_result[0]['saving_throw'] else None
        
        result_text = f"🔥 {char_name} использует '{spell_name}' по области!\n"
        
        # Для AoE заклинаний делаем ОДИН бросок урона для всех целей
        base_damage_result = self._roll_spell_damage(spell['damage'])
        result_text += f"\n💥 Базовый урон: {base_damage_result['text']} {spell['damage_type']}\n"
        
        # Если есть спасбросок, вычисляем DC
        save_dc = None
        if saving_throw_type:
            from saving_throws import saving_throw_manager
            save_dc = saving_throw_manager.calculate_spell_save_dc(character_id)
            result_text += f"📊 DC спасброска ({saving_throw_type}): {save_dc}\n\n"
        else:
            result_text += "\n"
        
        enemies_defeated = []
        total_dealt = 0
        
        for enemy in alive_enemies:
            enemy_name = enemy['name']
            actual_damage = base_damage_result['total']
            
            # Если есть спасбросок, враг может получить половину урона при успехе
            if saving_throw_type:
                from saving_throws import saving_throw_manager
                save_success, save_text = saving_throw_manager.make_saving_throw(
                    enemy['id'], 'enemy', saving_throw_type, save_dc
                )
                
                if save_success:
                    actual_damage = actual_damage // 2  # Половина урона при успешном спасброске
                    result_text += f"{enemy_name}: {save_text.split(' - ')[1]} - получает {actual_damage} урона (половина)\n"
                else:
                    result_text += f"{enemy_name}: {save_text.split(' - ')[1]} - получает {actual_damage} урона (полный)\n"
            else:
                result_text += f"{enemy_name}: получает {actual_damage} урона\n"
            
            # Применяем урон
            new_hp = max(0, enemy['hit_points'] - actual_damage)
            self.db.execute_query("UPDATE enemies SET hit_points = %s WHERE id = %s",
                                 (new_hp, enemy['id']))
            
            # Суммарный нанесенный урон
            dealt = enemy['hit_points'] - new_hp
            if dealt > 0:
                total_dealt += dealt
            
            if new_hp <= 0:
                enemies_defeated.append(enemy_name)
        
        # Записываем нанесенный урон по боевым метрикам
        try:
            if total_dealt > 0:
                record_damage_dealt(adventure_id, character_id, total_dealt)
        except Exception as e:
            logger.warning(f"COMBAT METRICS WARNING: record_damage_dealt (AoE) failed: {e}")
        
        if enemies_defeated:
            result_text += f"\n💀 Повержены: {', '.join(enemies_defeated)}"
            # Мультикилл: выдаем достижения 3/5
            try:
                user_row = self.db.execute_query("SELECT user_id FROM characters WHERE id = %s", (character_id,))
                user_id = user_row[0]['user_id'] if user_row else None
                if user_id:
                    count = len(enemies_defeated)
                    if count >= 5:
                        achievement_manager.grant_achievement(user_id, 'multikill_5', char_name,
                                                              f"Убиты: {', '.join(enemies_defeated)}")
                    elif count >= 3:
                        achievement_manager.grant_achievement(user_id, 'multikill_3', char_name,
                                                              f"Убиты: {', '.join(enemies_defeated)}")
            except Exception as e:
                logger.warning(f"ACHIEVEMENTS WARNING: multikill award failed: {e}")
        
        await update.callback_query.edit_message_text(result_text)
        
        # Проверяем, остались ли живые враги
        alive_enemies_query = "SELECT COUNT(*) as count FROM enemies WHERE adventure_id = %s AND hit_points > 0"
        alive_enemies_check = self.db.execute_query(alive_enemies_query, (adventure_id,))
        
        if alive_enemies_check and alive_enemies_check[0]['count'] == 0:
            from combat_manager import combat_manager
            await combat_manager.end_combat(update.callback_query, adventure_id, victory='players')
        else:
            # Переходим к следующему ходу после использования AoE заклинания
            if turn_index is not None and context:
                from combat_manager import combat_manager
                await combat_manager.next_turn(update, context, adventure_id, turn_index)
    
    async def cast_utility_spell(self, update: Update, character_id: int, adventure_id: int,
                                spell: dict, char_name: str, context: ContextTypes.DEFAULT_TYPE = None, turn_index: int = None):
        """Применяет вспомогательное заклинание (не наносящее урон)."""
        spell_name = spell['name']
        
        # Базовый результат для неурновых заклинаний
        result_text = f"✨ {char_name} использует заклинание '{spell_name}'!\n"
        
        # Добавляем описание эффекта заклинания
        if spell['description']:
            result_text += f"\n📜 {spell['description']}"
        
        # Для некоторых заклинаний можно добавить специальную логику
        if spell_name == "Щит":
            result_text += "\n🛡️ +5 к КД до следующего хода!"
        elif spell_name == "Размытие":
            result_text += "\n👻 Атаки по персонажу совершаются с помехой!"
        elif spell_name == "Невидимость":
            result_text += "\n🫥 Персонаж становится невидимым!"
        
        await update.callback_query.edit_message_text(result_text)
        
        # Переходим к следующему ходу после использования вспомогательного заклинания
        if turn_index is not None and context:
            from combat_manager import combat_manager
            await combat_manager.next_turn(update, context, adventure_id, turn_index)
    
    def _roll_spell_damage(self, damage_dice: str, critical: bool = False) -> dict:
        """Бросает кубики урона заклинания и возвращает результат."""
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
spell_combat_manager = SpellCombatManager()
