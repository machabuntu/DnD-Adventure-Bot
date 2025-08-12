import logging
import random
from telegram import Update
from telegram.ext import ContextTypes
from character_generation import character_gen
from adventure_manager import adventure_manager
from action_handler import action_handler
from database import get_db
from dice_utils import roll_d20, is_critical_hit, is_critical_miss, roll_dice, roll_dice_detailed, calculate_modifier
from achievement_manager import achievement_manager
from combat_achievements import record_damage_dealt, record_kill
from rest_handler import rest_handler

logger = logging.getLogger(__name__)

async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle all callback queries from inline keyboards"""
    query = update.callback_query
    
    if not query.data:
        logger.warning("Received callback query with no data")
        await query.answer("Неизвестная команда")
        return
    
    logger.info(f"Handling callback query: {query.data}")
    
    # Character generation callbacks
    if query.data.startswith('race_'):
        await character_gen.handle_race_selection(update, context)
    elif query.data.startswith('origin_'):
        await character_gen.handle_origin_selection(update, context)
    elif query.data.startswith('bonus_'):
        await character_gen.handle_stat_bonus_selection(update, context)
    elif query.data.startswith('select_bonus_'):
        await character_gen.handle_bonus_stat_selection(update, context)
    elif query.data.startswith('class_'):
        await character_gen.handle_class_selection(update, context)
    elif query.data.startswith('skill_'):
        await character_gen.handle_skill_selection(update, context)
    elif query.data.startswith('armor_'):
        await character_gen.handle_armor_selection(update, context)
    elif query.data.startswith('weapon_'):
        await character_gen.handle_weapon_selection(update, context)
    elif query.data.startswith('cantrip_'):
        await character_gen.handle_cantrip_selection(update, context)
    elif query.data.startswith('spell1_'):
        await character_gen.handle_spell_selection(update, context)
    elif query.data == 'join_group':
        await action_handler.handle_join_group_callback(update, context)
    
    # Adventure management callbacks
    elif query.data.startswith('start_adventure_'):
        await adventure_manager.handle_start_adventure(update, context)
    
    # Combat action callbacks
    elif query.data.startswith('action_'):
        await handle_combat_action(update, context)
    elif query.data.startswith('target_'):
        await handle_target_selection(update, context)
    elif query.data.startswith('cast_'):
        await handle_spell_cast(update, context)
    elif query.data.startswith('spell_target_'):
        await handle_spell_target_selection(update, context)
    elif query.data.startswith('cancel_spell_'):
        await handle_spell_cancel(update, context)
    
    # Rest callbacks
    elif query.data.startswith('rest_vote_'):
        await rest_handler.handle_rest_vote(update, context)
    
    else:
        await query.answer("Неизвестная команда")

async def handle_combat_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle combat action callbacks"""
    query = update.callback_query
    action_parts = query.data.split('_')
    
    if len(action_parts) < 5:
        await query.answer("Неверный формат действия")
        logger.error(f"Invalid combat action format: {query.data}")
        return
    
    action_type = action_parts[1]  # attack, spell, pass
    character_id = int(action_parts[2])
    adventure_id = int(action_parts[3])
    turn_index = int(action_parts[4])
    
    logger.info(f"COMBAT DEBUG: Processing action {action_type} for character {character_id} in adventure {adventure_id}, turn {turn_index}")
    
    db = get_db()
    if not db.connection or not db.connection.is_connected():
        db.connect()
    
    # Handle the specific combat action
    if action_type == 'attack':
        # Show target selection instead of immediate attack
        from combat_manager import combat_manager
        await combat_manager.display_attack_targets(update, character_id, adventure_id, turn_index)
        await query.answer()
        return  # Don't advance turn yet, wait for target selection
    elif action_type == 'spell':
        # Show combat spells selection
        from spell_combat import spell_combat_manager
        await spell_combat_manager.display_combat_spells(update, character_id, adventure_id, turn_index)
        await query.answer()
        return  # Don't advance turn yet, wait for spell selection
    elif action_type == 'pass':
        await query.edit_message_text(f"⏭️ Персонаж пропускает ход")
    
    await query.answer()
    
    # Import combat_manager here to avoid circular imports
    from combat_manager import combat_manager
    
    # Move to the next turn (except for attack, which handles it after target selection)
    if action_type != 'attack':
        await combat_manager.next_turn(update, context, adventure_id, turn_index)

async def handle_target_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle target selection and perform the character's attack."""
    query = update.callback_query
    action_parts = query.data.split('_')
    
    if len(action_parts) < 5:
        await query.answer("Неверный формат цели")
        logger.error(f"Invalid target selection format: {query.data}")
        return
    
    character_id = int(action_parts[1])
    adventure_id = int(action_parts[2])
    turn_index = int(action_parts[3])
    target_id = int(action_parts[4])
    
    logger.info(f"COMBAT DEBUG: Character {character_id} selected target {target_id} in adventure {adventure_id}")
    
    db = get_db()
    if not db.connection or not db.connection.is_connected():
        db.connect()
    
    # Perform the attack with the selected target
    await perform_character_attack(query, character_id, adventure_id, target_id, db)
    
    # Advance the turn
    from combat_manager import combat_manager
    await combat_manager.next_turn(update, context, adventure_id, turn_index)

async def perform_character_attack(query, character_id: int, adventure_id: int, target_id: int, db):
    """Perform a character attack against a specific target."""
    # Get character data
    char_query = "SELECT * FROM characters WHERE id = %s"
    char_data = db.execute_query(char_query, (character_id,))
    
    if not char_data:
        await query.edit_message_text("❌ Ошибка: персонаж не найден")
        return
    
    character = char_data[0]
    char_name = character['name']
    
    # Get target enemy data
    enemy_query = "SELECT * FROM enemies WHERE id = %s AND hit_points > 0"
    enemy_data = db.execute_query(enemy_query, (target_id,))
    
    if not enemy_data:
        await query.edit_message_text("❌ Ошибка: цель не найдена или уже повержена")
        return
    
    target = enemy_data[0]
    
    # Get character's weapon/attack info - for simplicity, use strength modifier for melee attacks
    strength_mod = calculate_modifier(character.get('strength', 10))
    proficiency_bonus = 2  # Simplified proficiency bonus
    attack_bonus = strength_mod + proficiency_bonus
    
    # Use enemy's stored AC (calculated when enemy was created)
    target_ac = target['armor_class'] or 12  # Default AC if not set
    
    # Perform attack roll
    attack_roll_result, attack_breakdown = roll_d20(attack_bonus)
    raw_roll = attack_roll_result - attack_bonus  # Get the raw d20 roll
    
    result_text = f"⚔️ {char_name} атакует {target['name']}!\n"
    result_text += f"🎲 Бросок атаки: {attack_breakdown} против AC {target_ac}"
    
    # Check for critical hit/miss
    if is_critical_hit(raw_roll):
        result_text += f"\n🎯 КРИТИЧЕСКОЕ ПОПАДАНИЕ! (натуральная 20)"
        # Double damage dice on crit - roll twice and combine
        total1, rolls1, modifier1, _ = roll_dice_detailed('1d8')
        total2, rolls2, modifier2, _ = roll_dice_detailed('1d8')
        
        # Combine all rolls and add strength modifier
        all_rolls = rolls1 + rolls2
        total_damage = sum(all_rolls) + strength_mod
        
        # Create detailed breakdown
        rolls_str = " + ".join(map(str, all_rolls))
        damage_text = f"{rolls_str} + {strength_mod} = {total_damage}"
        result_text += f"\n💥 Урон: {damage_text} урона"
        
        # Apply damage
        new_hp = max(0, target['hit_points'] - total_damage)
        db.execute_query("UPDATE enemies SET hit_points = %s WHERE id = %s", 
                         (new_hp, target['id']))
        # DO NOT show enemy HP for player attacks
        
        # Метрики боя: нанесенный урон
        try:
            dealt = target['hit_points'] - new_hp
            if dealt > 0:
                record_damage_dealt(adventure_id, character_id, dealt)
        except Exception as e:
            logger.warning(f"COMBAT METRICS WARNING: record_damage_dealt failed: {e}")
        
        # Проверяем достижения
        # За критический удар
        user_id = character.get('user_id')
        if user_id:
            ach = achievement_manager.grant_achievement(user_id, 'critical_hit', char_name)
            # За высокий урон
            ach_damage = achievement_manager.check_damage_achievement(user_id, total_damage, char_name)
        
        # Check if enemy is defeated
        if new_hp <= 0:
            result_text += f"\n💀 {target['name']} повержен!"
            # Достижение за первое убийство
            if user_id:
                ach = achievement_manager.grant_achievement(user_id, 'first_kill', char_name)
            # Метрики: убийство
            try:
                record_kill(adventure_id, character_id, 1)
            except Exception as e:
                logger.warning(f"COMBAT METRICS WARNING: record_kill failed: {e}")
        
    elif is_critical_miss(raw_roll):
        result_text += f"\n💨 КРИТИЧЕСКИЙ ПРОМАХ! (натуральная 1)"
        # Достижение за критический промах
        user_id = character.get('user_id')
        if user_id:
            ach = achievement_manager.grant_achievement(user_id, 'critical_miss', char_name)
        
    elif attack_roll_result >= target_ac:
        result_text += f"\n✅ ПОПАДАНИЕ!"
        # Calculate damage (1d8 + strength modifier for simplicity)
        damage_result, damage_breakdown = roll_dice('1d8')
        total_damage = damage_result + strength_mod
        result_text += f"\n💥 Урон: {damage_breakdown} + {strength_mod} = {total_damage} урона"
        
        # Apply damage
        new_hp = max(0, target['hit_points'] - total_damage)
        db.execute_query("UPDATE enemies SET hit_points = %s WHERE id = %s", 
                         (new_hp, target['id']))
        # DO NOT show enemy HP for player attacks
        
        # Метрики боя: нанесенный урон
        try:
            dealt = target['hit_points'] - new_hp
            if dealt > 0:
                record_damage_dealt(adventure_id, character_id, dealt)
        except Exception as e:
            logger.warning(f"COMBAT METRICS WARNING: record_damage_dealt failed: {e}")
        
        # Проверяем достижения за урон
        user_id = character.get('user_id')
        if user_id:
            ach_damage = achievement_manager.check_damage_achievement(user_id, total_damage, char_name)
        
        # Check if enemy is defeated
        if new_hp <= 0:
            result_text += f"\n💀 {target['name']} повержен!"
            # Достижение за первое убийство
            if user_id:
                ach = achievement_manager.grant_achievement(user_id, 'first_kill', char_name)
            # Метрики: убийство
            try:
                record_kill(adventure_id, character_id, 1)
            except Exception as e:
                logger.warning(f"COMBAT METRICS WARNING: record_kill failed: {e}")
            
    else:
        result_text += f"\n❌ ПРОМАХ!"
    
    await query.edit_message_text(result_text)
    
    # Check if all enemies are defeated
    alive_enemies_query = "SELECT COUNT(*) as count FROM enemies WHERE adventure_id = %s AND hit_points > 0"
    alive_enemies = db.execute_query(alive_enemies_query, (adventure_id,))
    
    if alive_enemies and alive_enemies[0]['count'] == 0:
        # Import combat_manager here to avoid circular imports
        from combat_manager import combat_manager
        await combat_manager.end_combat(query, adventure_id, victory='players')

async def handle_spell_cast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle spell casting callbacks"""
    query = update.callback_query
    action_parts = query.data.split('_')
    
    if len(action_parts) < 5:
        await query.answer("Неверный формат заклинания")
        logger.error(f"Invalid spell cast format: {query.data}")
        return
    
    # cast_character_id_adventure_id_turn_index_spell_id
    character_id = int(action_parts[1])
    adventure_id = int(action_parts[2])
    turn_index = int(action_parts[3])
    spell_id = int(action_parts[4])
    
    logger.info(f"SPELL DEBUG: Character {character_id} casting spell {spell_id} in adventure {adventure_id}")
    
    from spell_combat import spell_combat_manager
    await spell_combat_manager.handle_spell_cast(update, context, character_id, adventure_id, turn_index, spell_id)
    
    await query.answer()

async def handle_spell_target_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle spell target selection"""
    query = update.callback_query
    action_parts = query.data.split('_')
    
    if len(action_parts) < 6:
        await query.answer("Неверный формат цели заклинания")
        logger.error(f"Invalid spell target format: {query.data}")
        return
    
    # spell_target_character_id_adventure_id_turn_index_spell_id_target_id
    character_id = int(action_parts[2])
    adventure_id = int(action_parts[3])
    turn_index = int(action_parts[4])
    spell_id = int(action_parts[5])
    target_id = int(action_parts[6])
    
    logger.info(f"SPELL DEBUG: Character {character_id} targeting {target_id} with spell {spell_id}")
    
    from spell_combat import spell_combat_manager
    await spell_combat_manager.cast_single_target_spell(update, character_id, adventure_id, spell_id, target_id)
    
    # Advance the turn after casting spell
    from combat_manager import combat_manager
    await combat_manager.next_turn(update, context, adventure_id, turn_index)
    
    await query.answer()

async def handle_spell_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle spell casting cancellation"""
    query = update.callback_query
    action_parts = query.data.split('_')
    
    if len(action_parts) < 5:
        await query.answer("Неверный формат отмены")
        logger.error(f"Invalid spell cancel format: {query.data}")
        return
    
    # cancel_spell_character_id_adventure_id_turn_index
    character_id = int(action_parts[2])
    adventure_id = int(action_parts[3])
    turn_index = int(action_parts[4])
    
    logger.info(f"SPELL DEBUG: Character {character_id} cancelled spell casting")
    
    # Go back to action selection
    from combat_manager import combat_manager
    await combat_manager.display_actions(update, context, character_id, adventure_id, turn_index)
    
    await query.answer()
