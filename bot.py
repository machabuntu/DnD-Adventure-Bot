import logging
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

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler for /start command"""
    if update.effective_chat.id != ALLOWED_CHAT_ID:
        await update.message.reply_text("This bot is not allowed in this chat.")
        return
        
    await update.message.reply_text("Welcome to the D&D adventure bot!")
    
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler for /help command"""
    if update.effective_chat.id != ALLOWED_CHAT_ID:
        return
    
    help_text = """Available commands:\n
    /start - Start the bot\n
    /generate - Generate a new D&D character\n
    /startnewadventure - Start a new adventure\n
    /terminateadventure - Terminate the current adventure\n
    /deletecharacter - Delete your character\n
    /joinadventure - Join an ongoing adventure\n
    /leaveadventure - Leave the current adventure\n
    """
    
    await update.message.reply_text(help_text)

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
        await update.message.reply_text("Cannot delete character while in an active adventure.")
        return
    
    # Delete character
    result = db.execute_query(
        "UPDATE characters SET is_active = FALSE WHERE user_id = %s AND is_active = TRUE",
        (user_id,)
    )
    
    if result:
        await update.message.reply_text("Your character has been deleted.")
    else:
        await update.message.reply_text("No active character found to delete.")

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
        await update.message.reply_text("You need to generate a character first.")
        return
    
    # Check if there's an active adventure
    adventure = db.execute_query(
        "SELECT id FROM adventures WHERE chat_id = %s AND status = 'active'",
        (update.effective_chat.id,)
    )
    
    if not adventure:
        await update.message.reply_text("No active adventure to join.")
        return
    
    # Check if already in adventure
    already_in = db.execute_query(
        "SELECT id FROM adventure_participants WHERE adventure_id = %s AND character_id = %s",
        (adventure[0]['id'], character[0]['id'])
    )
    
    if already_in:
        await update.message.reply_text("You are already in this adventure.")
        return
    
    # Join adventure
    db.execute_query(
        "INSERT INTO adventure_participants (adventure_id, character_id) VALUES (%s, %s)",
        (adventure[0]['id'], character[0]['id'])
    )
    
    await update.message.reply_text("You have joined the adventure!")

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
        await update.message.reply_text("You are not in an active adventure.")
        return
    
    # Remove from adventure
    db.execute_query(
        "DELETE FROM adventure_participants WHERE id = %s",
        (participation[0]['id'],)
    )
    
    await update.message.reply_text("You have left the adventure.")

async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler for unknown commands"""
    await update.message.reply_text("Sorry, I didn't understand that command.")

# Main function to start the bot
async def main() -> None:
    # Create the Application
    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Register handlers for commands
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("generate", character_gen.start_character_generation))
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
    
    # Register handler for unknown commands
    application.add_error_handler(unknown_command)

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

