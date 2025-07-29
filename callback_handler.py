import logging
from telegram import Update
from telegram.ext import ContextTypes
from character_generation import character_gen
from adventure_manager import adventure_manager
from action_handler import action_handler

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
    elif query.data == 'join_group':
        await action_handler.handle_join_group_callback(update, context)
    
    # Adventure management callbacks
    elif query.data.startswith('start_adventure_'):
        await adventure_manager.handle_start_adventure(update, context)
    
    # Combat action callbacks
    elif query.data.startswith('action_'):
        await handle_combat_action(update, context)
    
    else:
        await query.answer("Неизвестная команда")

async def handle_combat_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle combat action callbacks"""
    query = update.callback_query
    action_parts = query.data.split('_')
    
    if len(action_parts) < 3:
        await query.answer("Неверный формат действия")
        return
    
    action_type = action_parts[1]  # attack, spell, pass
    character_id = int(action_parts[2])
    
    # Here you would implement specific combat actions
    if action_type == 'attack':
        await query.edit_message_text(f"⚔️ Персонаж атакует!")
    elif action_type == 'spell':
        await query.edit_message_text(f"✨ Персонаж использует заклинание!")
    elif action_type == 'pass':
        await query.edit_message_text(f"⏭️ Персонаж пропускает ход")
    
    await query.answer()
