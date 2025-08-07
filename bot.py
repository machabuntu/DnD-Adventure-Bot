import logging
import json
from telegram import Update, BotCommand
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from config import TELEGRAM_BOT_TOKEN, ALLOWED_CHAT_ID
from character_generation import character_gen
from adventure_manager import adventure_manager
from database import get_db
from action_handler import action_handler
from callback_handler import handle_callback_query

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configure httpx logging to only show errors (4xx, 5xx) and warnings
httpx_logger = logging.getLogger("httpx")
httpx_logger.setLevel(logging.WARNING)  # This will only show WARNING and above (including ERROR)

# Alternative approach: Set up a custom filter for httpx
class HTTPXFilter(logging.Filter):
    def filter(self, record):
        # Only show logs that contain error status codes (4xx, 5xx) or are not HTTP request logs
        if "HTTP Request:" in record.getMessage():
            # Check if the message contains error codes
            message = record.getMessage()
            if any(code in message for code in ["4", "5"]) and any(status in message for status in ["40", "41", "42", "43", "44", "45", "50", "51", "52", "53"]):
                return True  # Show 4xx and 5xx errors
            else:
                return False  # Hide successful 2xx requests
        return True  # Show all other logs

# Apply the filter to httpx logger
httpx_logger.addFilter(HTTPXFilter())

# Emoji для характеристик
STAT_EMOJIS = {
    'strength': '🐂',      # Бык - Сила
    'dexterity': '🐱',     # Кот - Ловкость  
    'constitution': '🐻',  # Медведь - Телосложение
    'intelligence': '🦊',  # Лиса - Интеллект
    'wisdom': '🦉',        # Сова - Мудрость
    'charisma': '🦅'       # Орёл - Харизма
}

# Названия характеристик на русском
STAT_NAMES = {
    'strength': 'Сила',
    'dexterity': 'Ловкость',
    'constitution': 'Телосложение', 
    'intelligence': 'Интеллект',
    'wisdom': 'Мудрость',
    'charisma': 'Харизма'
}

def get_modifier(stat: int) -> int:
    """Вычисляет модификатор характеристики"""
    return (stat - 10) // 2

def format_character_display(char: dict, db) -> str:
    """Форматирует информацию о персонаже для отображения"""
    # Форматируем характеристики вертикально (в том же стиле, что и окно создания)
    stats_text = "\n📊 <b>Характеристики:</b>\n"
    stat_names = ['strength', 'dexterity', 'constitution', 'intelligence', 'wisdom', 'charisma']
    
    for stat_name in stat_names:
        emoji = STAT_EMOJIS.get(stat_name, '❓')
        ru_name = STAT_NAMES.get(stat_name, stat_name)
        value = char.get(stat_name, 10)
        modifier = get_modifier(value)
        stats_text += f"{emoji} <b>{ru_name}:</b> {value} ({modifier:+d})\n"
    
    # Заголовок для команды /character
    info_text = "🎭 <b>Информация о персонаже</b>\n\n"
    
    # Основная информация (в том же порядке, что и в окне создания)
    info_text += f"👤 <b>Имя:</b> {char['name']}\n"
    info_text += f"🧝‍♂️ <b>Раса:</b> {char['race_name']}\n"
    info_text += f"🎭 <b>Происхождение:</b> {char['origin_name']}\n"
    info_text += f"⚔️ <b>Класс:</b> {char['class_name']}\n"
    
    # Добавляем уровень и опыт (новые поля)
    info_text += f"📊 <b>Уровень:</b> {char['level']}\n"
    info_text += f"⭐ <b>Опыт:</b> {char['experience']}\n"
    
    # Навыки (получаем из новой таблицы character_skills)
    try:
        skills_query = "SELECT skill_name FROM character_skills WHERE character_id = %s"
        skills_result = db.execute_query(skills_query, (char['id'],))
        
        if skills_result:
            skills_info = [skill['skill_name'] for skill in skills_result]
            skills_text = ", ".join(skills_info)
            info_text += f"🎯 <b>Навыки:</b> {skills_text}\n"
        else:
            # Fallback для старых персонажей без навыков в новой таблице
            info_text += f"🎯 <b>Навыки:</b> не определены (старый персонаж)\n"
            
    except Exception as e:
        logger.error(f"Error getting skills info: {e}")
    
    # Деньги
    info_text += f"💰 <b>Деньги:</b> {char.get('money', 0)} монет\n"
    
    # Проверяем наличие доспехов и оружия для экипировки
    if not db.connection or not db.connection.is_connected():
        db.connect()
    
    equipment_query = """
        SELECT ce.item_type, ce.item_id, ce.is_equipped,
               CASE 
                   WHEN ce.item_type = 'armor' THEN a.name
                   WHEN ce.item_type = 'weapon' THEN w.name
               END as item_name,
               CASE 
                   WHEN ce.item_type = 'weapon' THEN w.damage
                   ELSE NULL
               END as damage,
               CASE 
                   WHEN ce.item_type = 'weapon' THEN w.damage_type
                   ELSE NULL
               END as damage_type
        FROM character_equipment ce
        LEFT JOIN armor a ON ce.item_type = 'armor' AND ce.item_id = a.id
        LEFT JOIN weapons w ON ce.item_type = 'weapon' AND ce.item_id = w.id
        WHERE ce.character_id = %s
    """
    
    equipment = db.execute_query(equipment_query, (char['id'],))
    
    # Добавляем экипировку в том же стиле, что и в окне создания
    if equipment:
        for item in equipment:
            if item['item_type'] == 'armor':
                info_text += f"🛡️ <b>Доспехи:</b> {item['item_name']}\n"
            elif item['item_type'] == 'weapon':
                damage_text = f" ({item['damage']} {item['damage_type']})" if item['damage'] and item['damage_type'] else ""
                info_text += f"⚔️ <b>Оружие:</b> {item['item_name']}{damage_text}\n"
    
    # Бонус мастерства
    info_text += f"🎯 <b>Бонус мастерства:</b> +{char.get('proficiency_bonus', 2)}\n"
    
    # Класс доспехов (с учетом доспехов)
    armor_class = 10 + get_modifier(char.get('dexterity', 10))
    armor_description = f"{armor_class}"
    
    # Проверяем наличие доспехов для КД
    armor_query = """
        SELECT a.armor_class, a.name 
        FROM character_equipment ce
        INNER JOIN armor a ON ce.item_id = a.id
        WHERE ce.character_id = %s AND ce.item_type = 'armor' AND ce.is_equipped = TRUE
    """
    
    equipped_armor = db.execute_query(armor_query, (char['id'],))
    
    if equipped_armor:
        armor_base = equipped_armor[0]['armor_class']
        armor_name = equipped_armor[0]['name']
        
        # Обрабатываем различные типы КД доспехов
        if "+" in armor_base:
            if "макс" in armor_base:
                # Средние доспехи с ограничением
                base_ac = int(armor_base.split()[0])
                max_dex = int(armor_base.split("макс ")[1].split(")")[0])
                dex_mod = min(get_modifier(char.get('dexterity', 10)), max_dex)
                armor_class = base_ac + dex_mod
            else:
                # Легкие доспехи
                base_ac = int(armor_base.split()[0])
                armor_class = base_ac + get_modifier(char.get('dexterity', 10))
        elif armor_base.startswith("+"):
            # Щит
            armor_class += int(armor_base[1:])
        else:
            # Тяжелые доспехи
            try:
                armor_class = int(armor_base)
            except ValueError:
                pass
        
        armor_description = f"{armor_class} ({armor_name})"
    
    info_text += f"🛡️ <b>КД:</b> {armor_description}\n"
    
    # Информация об атаке (как в финальном окне создания)
    weapon_query = """
        SELECT w.name, w.damage, w.damage_type, w.properties
        FROM character_equipment ce
        INNER JOIN weapons w ON ce.item_id = w.id
        WHERE ce.character_id = %s AND ce.item_type = 'weapon' AND ce.is_equipped = TRUE
    """
    
    equipped_weapons = db.execute_query(weapon_query, (char['id'],))
    
    if equipped_weapons:
        for weapon in equipped_weapons:
            # Проверяем свойства оружия
            try:
                properties = json.loads(weapon['properties']) if weapon['properties'] else []
            except:
                properties = []
            
            # Определяем модификатор для атаки
            str_mod = get_modifier(char.get('strength', 10))
            dex_mod = get_modifier(char.get('dexterity', 10))
            
            # Если оружие фехтовальное, используем лучший модификатор
            if "Фехтовальное" in properties:
                attack_mod = max(str_mod, dex_mod)
                damage_mod = max(str_mod, dex_mod)
            else:
                # Для обычного оружия используем силу
                attack_mod = str_mod
                damage_mod = str_mod
            
            proficiency_bonus = char.get('proficiency_bonus', 2)
            attack_bonus = attack_mod + proficiency_bonus
            
            # Формируем строку атаки (точно как в окне создания)
            damage_str = str(weapon['damage'])
            damage_type_str = str(weapon['damage_type'])
            info_text += f"⚔️ <b>Атака ({weapon['name']}):</b> {attack_bonus:+d} к атаке, {damage_str}{damage_mod:+d} {damage_type_str}\n"
    
    # Заклинания для заклинателей (как в финальном окне создания)
    if char.get('is_spellcaster'):
        spells_query = """
            SELECT s.name, s.level 
            FROM character_spells cs
            JOIN spells s ON cs.spell_id = s.id
            WHERE cs.character_id = %s
            ORDER BY s.level, s.name
        """
        
        spells = db.execute_query(spells_query, (char['id'],))
        
        if spells:
            spells_by_level = {}
            for spell in spells:
                level = spell['level']
                if level not in spells_by_level:
                    spells_by_level[level] = []
                spells_by_level[level].append(spell['name'])
            
            info_text += "\n📜 <b>Заклинания:</b>\n"
            for level in sorted(spells_by_level.keys()):
                level_name = "Заговоры" if level == 0 else f"{level} уровень"
                spells_list = ", ".join(spells_by_level[level])
                info_text += f"• <b>{level_name}:</b> {spells_list}\n"
    
    # Добавляем характеристики в конце (как в окне создания)
    info_text += stats_text
    
    return info_text

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler for /start command"""
    logger.info(f"Start command called by user {update.effective_user.id} in chat {update.effective_chat.id}")
    
    if update.effective_chat.id != ALLOWED_CHAT_ID:
        logger.warning(f"Start command blocked - chat {update.effective_chat.id} not allowed (expected: {ALLOWED_CHAT_ID})")
        await context.bot.send_message(chat_id=update.effective_chat.id, text="This bot is not allowed in this chat.")
        return
        
    await context.bot.send_message(chat_id=update.effective_chat.id, text="Welcome to the D&D adventure bot!")
    logger.info("Start command completed successfully")

async def version_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show bot version and registered commands"""
    logger.info(f"Version command called by user {update.effective_user.id} in chat {update.effective_chat.id}")
    
    if update.effective_chat.id != ALLOWED_CHAT_ID:
        return
    
    import datetime
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    version_text = f"""🤖 <b>Информация о боте</b>

📅 <b>Время запроса:</b> {now}
🔄 <b>Версия:</b> 2.0 (с командами /character и /party)

✅ <b>Доступные команды:</b>
• /start - Запуск бота
• /generate - Создать персонажа
• /character - Показать персонажа ⭐ НОВАЯ
• /party - Показать группу ⭐ НОВАЯ
• /help - Помощь
• /version - Эта команда

🔧 <b>Статус:</b> Работает"""
    
    await context.bot.send_message(chat_id=update.effective_chat.id, text=version_text, parse_mode='HTML')
    
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler for /help command"""
    if update.effective_chat.id != ALLOWED_CHAT_ID:
        return
    
    help_text = """🎲 <b>Справка по командам D&D бота</b>

<b>📊 Персонажи:</b>
• /generate - Создать нового персонажа D&D
• /character - Показать информацию о вашем персонаже
• /deletecharacter - Удалить вашего персонажа

<b>🗺️ Приключения:</b>
• /startnewadventure - Начать новое приключение
• /terminateadventure - завершить текущее приключение
• /joinadventure - Присоединиться к активному приключению
• /leaveadventure - Покинуть текущее приключение

<b>👥 Группа:</b>
• /party - Показать состав текущей группы
• /action [действие] - Выполнить действие в приключении

<b>ℹ️ Информация:</b>
• /start - Запуск бота
• /help - Эта справка
• /version - Информация о версии бота

<b>💡 Подсказки:</b>
- Создайте персонажа командой /generate перед началом приключения
- Используйте /party чтобы узнать кто в группе
- В приключении используйте кнопки или команду /action для действий
- Бот поддерживает полноценную боевую систему D&D 5e

<i>Удачи в приключениях! 🌟</i>"""
    
    await context.bot.send_message(chat_id=update.effective_chat.id, text=help_text, parse_mode='HTML')

async def delete_character(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Delete user's character"""
    if update.effective_chat.id != ALLOWED_CHAT_ID:
        return
    
    user_id = update.effective_user.id
    db = get_db()
    
    if not db.connection or not db.connection.is_connected():
        db.connect()
    
    # Check if character is in active adventure
    in_adventure = db.execute_query(
        "SELECT ap.id FROM adventure_participants ap "
        "INNER JOIN characters c ON ap.character_id = c.id "
        "INNER JOIN adventures a ON ap.adventure_id = a.id "
        "WHERE c.user_id = %s AND a.status = 'active'",
        (user_id,)
    )
    
    if in_adventure:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Cannot delete character while in an active adventure.")
        return
    
    # Delete character
    result = db.execute_query(
        "UPDATE characters SET is_active = FALSE WHERE user_id = %s AND is_active = TRUE",
        (user_id,)
    )
    
    if result:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Your character has been deleted.")
    else:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="No active character found to delete.")

async def join_adventure(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Join an active adventure"""
    if update.effective_chat.id != ALLOWED_CHAT_ID:
        return
    
    user_id = update.effective_user.id
    db = get_db()
    
    if not db.connection or not db.connection.is_connected():
        db.connect()
    
    # Check if user has a character
    character = db.execute_query(
        "SELECT id FROM characters WHERE user_id = %s AND is_active = TRUE",
        (user_id,)
    )
    
    if not character:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="You need to generate a character first.")
        return
    
    # Check if there's an active adventure
    adventure = db.execute_query(
        "SELECT id FROM adventures WHERE chat_id = %s AND status = 'active'",
        (update.effective_chat.id,)
    )
    
    if not adventure:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="No active adventure to join.")
        return
    
    # Check if already in adventure
    already_in = db.execute_query(
        "SELECT id FROM adventure_participants WHERE adventure_id = %s AND character_id = %s",
        (adventure[0]['id'], character[0]['id'])
    )
    
    if already_in:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="You are already in this adventure.")
        return
    
    # Join adventure
    db.execute_query(
        "INSERT INTO adventure_participants (adventure_id, character_id) VALUES (%s, %s)",
        (adventure[0]['id'], character[0]['id'])
    )
    
    await context.bot.send_message(chat_id=update.effective_chat.id, text="You have joined the adventure!")

async def leave_adventure(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Leave current adventure"""
    if update.effective_chat.id != ALLOWED_CHAT_ID:
        return
    
    user_id = update.effective_user.id
    db = get_db()
    
    if not db.connection or not db.connection.is_connected():
        db.connect()
    
    # Find user's character in active adventure
    participation = db.execute_query(
        "SELECT ap.id FROM adventure_participants ap "
        "INNER JOIN characters c ON ap.character_id = c.id "
        "INNER JOIN adventures a ON ap.adventure_id = a.id "
        "WHERE c.user_id = %s AND a.status = 'active' AND a.chat_id = %s",
        (user_id, update.effective_chat.id)
    )
    
    if not participation:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="You are not in an active adventure.")
        return
    
    # Remove from adventure
    db.execute_query(
        "DELETE FROM adventure_participants WHERE id = %s",
        (participation[0]['id'],)
    )
    
    await context.bot.send_message(chat_id=update.effective_chat.id, text="You have left the adventure.")

async def show_character(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show current character information"""
    logger.info(f"Character command called by user {update.effective_user.id} in chat {update.effective_chat.id}")
    
    if update.effective_chat.id != ALLOWED_CHAT_ID:
        logger.warning(f"Character command blocked - chat {update.effective_chat.id} not allowed (expected: {ALLOWED_CHAT_ID})")
        await update.message.reply_text("❌ Эта команда недоступна в данном чате.")
        return
    
    user_id = update.effective_user.id
    logger.info(f"Processing character command for user {user_id}")
    db = get_db()
    
    if not db.connection or not db.connection.is_connected():
        db.connect()
    
    # Get character data
    character_query = """
        SELECT c.*, r.name as race_name, o.name as origin_name, cl.name as class_name,
               cl.hit_die, cl.is_spellcaster, l.proficiency_bonus
        FROM characters c
        LEFT JOIN races r ON c.race_id = r.id
        LEFT JOIN origins o ON c.origin_id = o.id
        LEFT JOIN classes cl ON c.class_id = cl.id
        LEFT JOIN levels l ON c.level = l.level
        WHERE c.user_id = %s AND c.is_active = TRUE
    """
    
    character = db.execute_query(character_query, (user_id,))
    
    if not character:
        await update.message.reply_text("❌ У вас нет активного персонажа. Используйте /generate для создания персонажа.")
        return
    
    char = character[0]
    
    # Format character information
    char_info = format_character_display(char, db)
    
    await update.message.reply_text(char_info, parse_mode='HTML')

async def show_party(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show current party members"""
    if update.effective_chat.id != ALLOWED_CHAT_ID:
        return
    
    db = get_db()
    
    if not db.connection or not db.connection.is_connected():
        db.connect()
    
    # Find active adventure in this chat
    adventure = db.execute_query(
        "SELECT id FROM adventures WHERE chat_id = %s AND status = 'active'",
        (update.effective_chat.id,)
    )
    
    if not adventure:
        await update.message.reply_text("❌ В этом чате нет активного приключения.")
        return
    
    # Get party members
    party_query = """
        SELECT c.name, c.level, c.experience, c.user_id, cl.name as class_name
        FROM adventure_participants ap
        INNER JOIN characters c ON ap.character_id = c.id
        INNER JOIN classes cl ON c.class_id = cl.id
        WHERE ap.adventure_id = %s
        ORDER BY c.name
    """
    
    party_members = db.execute_query(party_query, (adventure[0]['id'],))
    
    if not party_members:
        await update.message.reply_text("👥 В группе пока нет участников.")
        return
    
    party_text = "👥 <b>Состав группы:</b>\n\n"
    
    for i, member in enumerate(party_members, 1):
        # Get user info from Telegram
        try:
            user = await context.bot.get_chat_member(update.effective_chat.id, member['user_id'])
            username = user.user.username or user.user.first_name or "Unknown"
        except:
            username = "Unknown"
        
        party_text += f"{i}. <b>{member['name']}</b>\n"
        party_text += f"   👤 Игрок: @{username}\n"
        party_text += f"   ⚔️ Класс: {member['class_name']}\n"
        party_text += f"   📊 Уровень: {member['level']}\n"
        party_text += f"   ⭐ Опыт: {member['experience']}\n\n"
    
    await update.message.reply_text(party_text, parse_mode='HTML')

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler for errors"""
    logger.error(f"Update {update} caused error {context.error}")
    
    # Try to respond to the user if possible
    try:
        if update.message:
            await update.message.reply_text("Произошла ошибка. Попробуйте еще раз.")
        elif update.callback_query:
            await update.callback_query.answer("Произошла ошибка. Попробуйте еще раз.", show_alert=True)
    except Exception as e:
        logger.error(f"Failed to send error message to user: {e}")

async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler for unknown commands"""
    if update.message:
        await update.message.reply_text("Sorry, I didn't understand that command.")

# Main function to start the bot
async def main() -> None:
    # Create the Application
    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Register handlers for commands
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("version", version_command))
    application.add_handler(CommandHandler("generate", character_gen.start_character_generation))
    application.add_handler(CommandHandler("character", show_character))
    application.add_handler(CommandHandler("party", show_party))
    application.add_handler(CommandHandler("startnewadventure", adventure_manager.start_new_adventure))
    application.add_handler(CommandHandler("terminateadventure", adventure_manager.terminate_adventure))
    application.add_handler(CommandHandler("deletecharacter", delete_character))
    application.add_handler(CommandHandler("joinadventure", join_adventure))
    application.add_handler(CommandHandler("leaveadventure", leave_adventure))
    application.add_handler(CommandHandler("action", action_handler.handle_action_command))
    
    # Add callback query handler
    application.add_handler(CallbackQueryHandler(handle_callback_query))
    
    # Add message handler for character name input
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, character_gen.handle_name_input))
    
    # Register error handler
    application.add_error_handler(error_handler)

    # Start the bot
    logger.info("Starting the bot...")
    await application.run_polling()

def run_bot():
    """Run the bot using a more compatible approach"""
    import asyncio
    import sys
    import platform
    
    try:
        # Try the standard approach first
        asyncio.run(main())
    except RuntimeError as e:
        error_msg = str(e).lower()
        if ("cannot be called from a running event loop" in error_msg or 
            "this event loop is already running" in error_msg):
            
            logger.info("Detected running event loop, using alternative startup method...")
            
            # Alternative approach for environments with existing event loops
            try:
                # On Windows with Python < 3.8, we need to handle things differently
                if platform.system() == 'Windows' and hasattr(asyncio, 'WindowsProactorEventLoopPolicy'):
                    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
                
                # Create a completely new event loop
                new_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(new_loop)
                
                try:
                    new_loop.run_until_complete(main())
                except KeyboardInterrupt:
                    logger.info("Bot stopped by user")
                finally:
                    # Don't close the loop, just let it be
                    pass
                    
            except Exception as fallback_error:
                logger.error(f"Failed to start bot with fallback method: {fallback_error}")
                # Try one more approach with threading
                try:
                    import threading
                    import time
                    
                    def run_in_thread():
                        thread_loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(thread_loop)
                        thread_loop.run_until_complete(main())
                    
                    thread = threading.Thread(target=run_in_thread)
                    thread.daemon = True
                    thread.start()
                    
                    # Keep the main thread alive
                    try:
                        while thread.is_alive():
                            time.sleep(1)
                    except KeyboardInterrupt:
                        logger.info("Bot stopped by user")
                        
                except Exception as thread_error:
                    logger.error(f"All startup methods failed: {thread_error}")
                    sys.exit(1)
        else:
            logger.error(f"Failed to start bot: {e}")
            sys.exit(1)
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Unexpected error starting bot: {e}")
        sys.exit(1)

if __name__ == "__main__":
    run_bot()

