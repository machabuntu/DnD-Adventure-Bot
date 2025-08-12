#!/usr/bin/env python3
"""
Alternative bot startup script to avoid event loop issues
Usage: 
  python start_bot.py          # Normal mode with real Grok API
  python start_bot.py mock     # Mock mode for debugging
"""

import logging
import asyncio
import sys
import os
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Check for mock mode
MOCK_MODE = len(sys.argv) > 1 and sys.argv[1].lower() == 'mock'

if MOCK_MODE:
    print("\n🧪 MOCK MODE ACTIVATED 🧪")
    print("Bot will use mock Grok API responses from mock_responses/ directory")
    print("Make sure mock_grok_api.py is running on localhost:5001")
    print("-" * 50)
    
    # Override config for mock mode
    import config
    config.GROK_API_URL = "http://localhost:5001/v1/chat/completions"
    config.GROK_API_TOKEN = "mock-token"
    config.GROK_MODEL = "mock-grok"
    
    from config import TELEGRAM_BOT_TOKEN, ALLOWED_CHAT_ID
else:
    from config import TELEGRAM_BOT_TOKEN, ALLOWED_CHAT_ID
from character_generation import character_gen
from adventure_manager import adventure_manager
from database import get_db
from action_handler import action_handler
from callback_handler import handle_callback_query
from rest_handler import rest_handler
from bot import start, help_command, version_command, show_character, show_party, show_achievements, delete_character, join_adventure, leave_adventure, error_handler

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    """Main function to start the bot synchronously"""
    
    # Create the Application
    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Register handlers for commands
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("version", version_command))
    application.add_handler(CommandHandler("generate", character_gen.start_character_generation))
    application.add_handler(CommandHandler("character", show_character))
    application.add_handler(CommandHandler("party", show_party))
    application.add_handler(CommandHandler("achievements", show_achievements))
    application.add_handler(CommandHandler("startnewadventure", adventure_manager.start_new_adventure))
    application.add_handler(CommandHandler("terminateadventure", adventure_manager.terminate_adventure))
    application.add_handler(CommandHandler("deletecharacter", delete_character))
    application.add_handler(CommandHandler("joinadventure", join_adventure))
    application.add_handler(CommandHandler("leaveadventure", leave_adventure))
    application.add_handler(CommandHandler("action", action_handler.handle_action_command))
    application.add_handler(CommandHandler("rest", rest_handler.handle_rest_command))
    
    # Add callback query handler
    application.add_handler(CallbackQueryHandler(handle_callback_query))
    
    # Add message handler for character name input
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, character_gen.handle_name_input))
    
    # Register error handler
    application.add_error_handler(error_handler)

    # Start the bot using the polling method
    logger.info("Starting the bot...")
    
    try:
        application.run_polling(drop_pending_updates=True)
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Error running bot: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
