#!/usr/bin/env python3
"""
Дополнительные обработчики callback для улучшенной системы заклинаний.
Подключается к основному callback_handler для обработки новых типов callback.
"""

import logging
from telegram import Update
from telegram.ext import ContextTypes
from spell_combat_enhanced import enhanced_spell_combat_manager
from saving_throws import saving_throw_manager

logger = logging.getLogger(__name__)

async def handle_slot_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка выбора слота для заклинания."""
    query = update.callback_query
    action_parts = query.data.split('_')
    
    # use_slot_character_id_adventure_id_turn_index_spell_id_slot_level
    if len(action_parts) < 6:
        await query.answer("Неверный формат выбора слота")
        logger.error(f"Invalid slot selection format: {query.data}")
        return
    
    character_id = int(action_parts[2])
    adventure_id = int(action_parts[3])
    turn_index = int(action_parts[4])
    spell_id = int(action_parts[5])
    slot_level = int(action_parts[6])
    
    logger.info(f"SPELL DEBUG: Character {character_id} selected slot {slot_level} for spell {spell_id}")
    
    await enhanced_spell_combat_manager.handle_slot_selection(
        update, context, character_id, adventure_id, turn_index, spell_id, slot_level
    )
    
    await query.answer()

async def handle_enhanced_spell_target(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка выбора цели для заклинания с учетом усиления."""
    query = update.callback_query
    action_parts = query.data.split('_')
    
    # spell_target_enh_character_id_adventure_id_turn_index_spell_id_target_id_slot_level
    if len(action_parts) < 8:
        await query.answer("Неверный формат цели заклинания")
        logger.error(f"Invalid enhanced spell target format: {query.data}")
        return
    
    character_id = int(action_parts[3])
    adventure_id = int(action_parts[4])
    turn_index = int(action_parts[5])
    spell_id = int(action_parts[6])
    target_id = int(action_parts[7])
    slot_level = int(action_parts[8]) if action_parts[8] != '0' else None
    
    logger.info(f"SPELL DEBUG: Character {character_id} targeting {target_id} with spell {spell_id} (slot {slot_level})")
    
    # Здесь должна быть логика применения заклинания к цели с учетом усиления
    from spell_combat_enhanced import enhanced_spell_combat_manager
    from database import get_db
    
    db = get_db()
    if not db.connection or not db.connection.is_connected():
        db.connect()
    
    # Получаем информацию о заклинании
    spell_query = """
        SELECT name, level, damage, damage_type, description
        FROM spells WHERE id = %s
    """
    spell_info = db.execute_query(spell_query, (spell_id,))
    
    if not spell_info:
        await query.edit_message_text("❌ Заклинание не найдено!")
        return
    
    spell = spell_info[0]
    
    # Получаем информацию о персонаже
    char_query = "SELECT name, level FROM characters WHERE id = %s"
    char_result = db.execute_query(char_query, (character_id,))
    char_name = char_result[0]['name'] if char_result else "Неизвестный"
    character_level = char_result[0]['level'] if char_result else 1
    
    # Применяем заклинание с учетом усиления
    from spell_scaling import apply_spell_scaling_in_combat
    
    scaling = apply_spell_scaling_in_combat(
        spell_id,
        spell['damage'],
        slot_level=slot_level,
        character_level=character_level if spell['level'] == 0 else None
    )
    
    # Получаем информацию о цели
    target_query = "SELECT name, current_hp, armor_class FROM enemies WHERE id = %s"
    target_result = db.execute_query(target_query, (target_id,))
    
    if not target_result:
        await query.edit_message_text("❌ Цель не найдена!")
        return
    
    target = target_result[0]
    target_name = target['name']
    target_ac = target['armor_class'] or 12
    
    spell_name = spell['name']
    if slot_level and slot_level > spell['level']:
        spell_name += f" (слот {slot_level} ур.)"
    
    result_text = f"✨ {char_name} использует заклинание '{spell_name}' на {target_name}!\n"
    
    # Проверяем наличие спасброска
    spell_query_full = """
        SELECT saving_throw FROM spells WHERE id = %s
    """
    spell_full = db.execute_query(spell_query_full, (spell_id,))
    
    if spell_full and spell_full[0].get('saving_throw'):
        # Заклинание требует спасброска вместо броска атаки
        save_success, save_text = saving_throw_manager.process_spell_saving_throw(
            spell_id, character_id, target_id, 'enemy'
        )
        
        result_text += f"\n{save_text}\n"
        
        if spell['damage']:
            damage_result = enhanced_spell_combat_manager._roll_spell_damage(scaling['damage'])
            
            if save_success:
                # Успешный спасбросок - половина урона
                damage_taken = damage_result['total'] // 2
                result_text += f"\n💥 Урон (половина): {damage_taken} {spell['damage_type']} урона"
            else:
                # Проваленный спасбросок - полный урон
                damage_taken = damage_result['total']
                result_text += f"\n💥 Урон: {damage_result['text']} {spell['damage_type']} урона"
            
            # Применяем урон
            new_hp = max(0, target['current_hp'] - damage_taken)
            db.execute_query("UPDATE enemies SET current_hp = %s WHERE id = %s",
                            (new_hp, target_id))
            
            if new_hp <= 0:
                result_text += f"\n💀 {target_name} повержен заклинанием!"
    # Проверяем, требует ли заклинание броска атаки
    elif spell_name in ["Огненный снаряд", "Ледяной луч", "Сглаз", "Ведьмин снаряд"]:
        # Заклинания, требующие броска атаки
        from dice_utils import calculate_modifier, roll_d20, is_critical_hit, is_critical_miss
        
        # Получаем характеристику заклинателя
        char_stats_query = """
            SELECT c.intelligence, c.wisdom, c.charisma, cl.name as class_name
            FROM characters c
            JOIN classes cl ON c.class_id = cl.id
            WHERE c.id = %s
        """
        
        char_stats = db.execute_query(char_stats_query, (character_id,))
        if not char_stats:
            spell_modifier = 0
        else:
            stats = char_stats[0]
            class_name = stats['class_name']
            
            # Определяем основную характеристику заклинателя
            if class_name in ["Волшебник"]:
                spell_modifier = calculate_modifier(stats['intelligence'])
            elif class_name in ["Жрец", "Друид", "Следопыт"]:
                spell_modifier = calculate_modifier(stats['wisdom'])
            else:  # Бард, Чародей, Колдун, Паладин
                spell_modifier = calculate_modifier(stats['charisma'])
        
        proficiency_bonus = 2 + (character_level - 1) // 4  # Более точный расчет
        spell_attack_bonus = spell_modifier + proficiency_bonus
        
        attack_roll_result, attack_breakdown = roll_d20(spell_attack_bonus)
        raw_roll = attack_roll_result - spell_attack_bonus
        
        result_text += f"🎲 Бросок атаки заклинанием: {attack_breakdown} против AC {target_ac}"
        
        if is_critical_hit(raw_roll):
            result_text += f"\n🎯 КРИТИЧЕСКОЕ ПОПАДАНИЕ! (натуральная 20)"
            damage_result = enhanced_spell_combat_manager._roll_spell_damage(scaling['damage'], critical=True)
            result_text += f"\n💥 Урон: {damage_result['text']} {spell['damage_type']} урона"
            
            # Применяем урон
            new_hp = max(0, target['current_hp'] - damage_result['total'])
            db.execute_query("UPDATE enemies SET current_hp = %s WHERE id = %s",
                            (new_hp, target_id))
            
            if new_hp <= 0:
                result_text += f"\n💀 {target_name} повержен заклинанием!"
            
        elif is_critical_miss(raw_roll):
            result_text += f"\n💨 КРИТИЧЕСКИЙ ПРОМАХ! (натуральная 1)"
            
        elif attack_roll_result >= target_ac:
            result_text += f"\n✅ ПОПАДАНИЕ!"
            damage_result = enhanced_spell_combat_manager._roll_spell_damage(scaling['damage'])
            result_text += f"\n💥 Урон: {damage_result['text']} {spell['damage_type']} урона"
            
            # Применяем урон
            new_hp = max(0, target['current_hp'] - damage_result['total'])
            db.execute_query("UPDATE enemies SET current_hp = %s WHERE id = %s",
                            (new_hp, target_id))
            
            if new_hp <= 0:
                result_text += f"\n💀 {target_name} повержен заклинанием!"
        else:
            result_text += f"\n❌ ПРОМАХ!"
    else:
        # Заклинания, автоматически попадающие или требующие спасброска
        if spell['damage']:
            damage_result = enhanced_spell_combat_manager._roll_spell_damage(scaling['damage'])
            
            if spell.get('saving_throw'):
                result_text += f"\n⚡ Цель должна совершить спасбросок {spell['saving_throw']}!"
            else:
                result_text += f"\n✨ Заклинание автоматически попадает!"
            
            result_text += f"\n💥 Урон: {damage_result['text']} {spell['damage_type']} урона"
            
            # Применяем урон
            new_hp = max(0, target['current_hp'] - damage_result['total'])
            db.execute_query("UPDATE enemies SET current_hp = %s WHERE id = %s",
                            (new_hp, target_id))
            
            if new_hp <= 0:
                result_text += f"\n💀 {target_name} повержен заклинанием!"
    
    await query.edit_message_text(result_text)
    
    # Проверяем, остались ли живые враги
    alive_enemies_query = "SELECT COUNT(*) as count FROM enemies WHERE adventure_id = %s AND current_hp > 0"
    alive_enemies = db.execute_query(alive_enemies_query, (adventure_id,))
    
    if alive_enemies and alive_enemies[0]['count'] == 0:
        from combat_manager import combat_manager
        await combat_manager.end_combat(query, adventure_id, victory='players')
    else:
        # Переходим к следующему ходу
        from combat_manager import combat_manager
        await combat_manager.next_turn(update, context, adventure_id, turn_index)
    
    await query.answer()

async def handle_beam_target_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка выбора цели для луча заговора."""
    query = update.callback_query
    action_parts = query.data.split('_')
    
    # beam_target_character_id_adventure_id_turn_index_spell_id_target_id_beam_number
    if len(action_parts) < 7:
        await query.answer("Неверный формат цели луча")
        logger.error(f"Invalid beam target format: {query.data}")
        return
    
    character_id = int(action_parts[2])
    adventure_id = int(action_parts[3])
    turn_index = int(action_parts[4])
    spell_id = int(action_parts[5])
    target_id = int(action_parts[6])
    beam_number = int(action_parts[7])
    
    logger.info(f"SPELL DEBUG: Character {character_id} beam {beam_number} targeting {target_id}")
    
    # Сохраняем выбранную цель для этого луча
    context_key = f"beam_targets_{character_id}_{spell_id}"
    
    if context_key not in context.chat_data:
        context.chat_data[context_key] = {
            'targets': [],
            'num_beams': 1,
            'current_beam': 1
        }
    
    beam_data = context.chat_data[context_key]
    
    # Добавляем цель для текущего луча
    from database import get_db
    db = get_db()
    if not db.connection or not db.connection.is_connected():
        db.connect()
    
    target_query = "SELECT name FROM enemies WHERE id = %s"
    target_result = db.execute_query(target_query, (target_id,))
    
    if target_result:
        beam_data['targets'].append({
            'id': target_id,
            'name': target_result[0]['name'],
            'beam': beam_number
        })
    
    # Проверяем, все ли лучи назначены
    if beam_number < beam_data['num_beams']:
        # Еще есть лучи для назначения
        beam_data['current_beam'] = beam_number + 1
        await enhanced_spell_combat_manager._select_beam_targets(
            update, character_id, adventure_id, turn_index, spell_id,
            None, None, None, None  # Эти параметры должны быть получены заново
        )
    else:
        # Все лучи назначены, выполняем атаки
        await execute_beam_attacks(update, context, character_id, adventure_id, 
                                  turn_index, spell_id, beam_data['targets'])
        
        # Очищаем данные о лучах
        del context.chat_data[context_key]
    
    await query.answer()

async def execute_beam_attacks(update: Update, context: ContextTypes.DEFAULT_TYPE,
                              character_id: int, adventure_id: int, turn_index: int,
                              spell_id: int, targets: list):
    """Выполняет атаки всеми лучами заговора."""
    from database import get_db
    from dice_utils import calculate_modifier, roll_d20, is_critical_hit, is_critical_miss
    
    db = get_db()
    if not db.connection or not db.connection.is_connected():
        db.connect()
    
    # Получаем информацию о персонаже и заклинании
    char_query = "SELECT name, level FROM characters WHERE id = %s"
    char_result = db.execute_query(char_query, (character_id,))
    char_name = char_result[0]['name'] if char_result else "Неизвестный"
    character_level = char_result[0]['level'] if char_result else 1
    
    spell_query = "SELECT name, damage, damage_type FROM spells WHERE id = %s"
    spell_result = db.execute_query(spell_query, (spell_id,))
    
    if not spell_result:
        await update.callback_query.edit_message_text("❌ Заклинание не найдено!")
        return
    
    spell = spell_result[0]
    spell_name = spell['name']
    
    # Получаем скалирование
    from spell_scaling import get_cantrip_scaling
    scaling = get_cantrip_scaling(spell_id, character_level)
    damage_dice = scaling.get('damage_dice', spell['damage'])
    
    # Получаем модификатор атаки заклинанием
    char_stats_query = """
        SELECT c.intelligence, c.wisdom, c.charisma, cl.name as class_name
        FROM characters c
        JOIN classes cl ON c.class_id = cl.id
        WHERE c.id = %s
    """
    
    char_stats = db.execute_query(char_stats_query, (character_id,))
    if not char_stats:
        spell_modifier = 0
    else:
        stats = char_stats[0]
        class_name = stats['class_name']
        
        if class_name in ["Волшебник"]:
            spell_modifier = calculate_modifier(stats['intelligence'])
        elif class_name in ["Жрец", "Друид", "Следопыт"]:
            spell_modifier = calculate_modifier(stats['wisdom'])
        else:
            spell_modifier = calculate_modifier(stats['charisma'])
    
    proficiency_bonus = 2 + (character_level - 1) // 4
    spell_attack_bonus = spell_modifier + proficiency_bonus
    
    result_text = f"✨ {char_name} использует '{spell_name}'!\n"
    result_text += f"Выпускает {len(targets)} лучей:\n\n"
    
    enemies_defeated = []
    
    for i, target_info in enumerate(targets, 1):
        target_id = target_info['id']
        target_name = target_info['name']
        
        # Получаем текущие HP и AC цели
        enemy_query = "SELECT current_hp, armor_class FROM enemies WHERE id = %s"
        enemy_result = db.execute_query(enemy_query, (target_id,))
        
        if not enemy_result or enemy_result[0]['current_hp'] <= 0:
            result_text += f"Луч {i}: {target_name} - цель уже повержена\n"
            continue
        
        enemy = enemy_result[0]
        target_ac = enemy['armor_class'] or 12
        
        # Бросок атаки для каждого луча
        attack_roll_result, attack_breakdown = roll_d20(spell_attack_bonus)
        raw_roll = attack_roll_result - spell_attack_bonus
        
        result_text += f"Луч {i} → {target_name}: {attack_breakdown} vs AC {target_ac}"
        
        if is_critical_hit(raw_roll):
            result_text += " - КРИТ! "
            damage_result = enhanced_spell_combat_manager._roll_spell_damage(damage_dice, critical=True)
            result_text += f"{damage_result['text']} урона\n"
            damage_total = damage_result['total']
        elif is_critical_miss(raw_roll):
            result_text += " - крит. промах!\n"
            damage_total = 0
        elif attack_roll_result >= target_ac:
            result_text += " - попадание! "
            damage_result = enhanced_spell_combat_manager._roll_spell_damage(damage_dice)
            result_text += f"{damage_result['text']} урона\n"
            damage_total = damage_result['total']
        else:
            result_text += " - промах!\n"
            damage_total = 0
        
        if damage_total > 0:
            new_hp = max(0, enemy['current_hp'] - damage_total)
            db.execute_query("UPDATE enemies SET current_hp = %s WHERE id = %s",
                           (new_hp, target_id))
            
            if new_hp <= 0:
                enemies_defeated.append(target_name)
    
    if enemies_defeated:
        result_text += f"\n💀 Повержены: {', '.join(enemies_defeated)}"
    
    await update.callback_query.edit_message_text(result_text)
    
    # Проверяем окончание боя
    alive_enemies_query = "SELECT COUNT(*) as count FROM enemies WHERE adventure_id = %s AND current_hp > 0"
    alive_enemies = db.execute_query(alive_enemies_query, (adventure_id,))
    
    if alive_enemies and alive_enemies[0]['count'] == 0:
        from combat_manager import combat_manager
        await combat_manager.end_combat(update.callback_query, adventure_id, victory='players')
    else:
        # Переходим к следующему ходу
        from combat_manager import combat_manager
        await combat_manager.next_turn(update, context, adventure_id, turn_index)

# Функция для регистрации обработчиков
def register_enhanced_callbacks(application):
    """Регистрирует дополнительные обработчики callback для улучшенной системы заклинаний."""
    from telegram.ext import CallbackQueryHandler
    
    # Обработчики для выбора слота
    application.add_handler(CallbackQueryHandler(
        handle_slot_selection,
        pattern=r'^use_slot_\d+_\d+_\d+_\d+_\d+$'
    ))
    
    # Обработчики для улучшенных целей заклинаний
    application.add_handler(CallbackQueryHandler(
        handle_enhanced_spell_target,
        pattern=r'^spell_target_enh_\d+_\d+_\d+_\d+_\d+_\d+$'
    ))
    
    # Обработчики для лучей заговоров
    application.add_handler(CallbackQueryHandler(
        handle_beam_target_selection,
        pattern=r'^beam_target_\d+_\d+_\d+_\d+_\d+_\d+$'
    ))
    
    logger.info("Enhanced spell callbacks registered")
