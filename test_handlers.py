#!/usr/bin/env python3
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from telegram.ext import ApplicationBuilder
from config import TELEGRAM_BOT_TOKEN

def test_handlers():
    """Проверяем зарегистрированные обработчики команд"""
    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Импортируем функции регистрации из bot.py
    try:
        from bot import start, help_command, show_character, show_party
        from character_generation import character_gen
        from adventure_manager import adventure_manager
        from action_handler import action_handler
        from callback_handler import handle_callback_query
        
        print("✅ Все модули импортированы успешно")
        
        # Проверяем, что функции существуют
        functions_to_check = [
            ('start', start),
            ('help_command', help_command), 
            ('show_character', show_character),
            ('show_party', show_party),
            ('character_gen.start_character_generation', character_gen.start_character_generation),
        ]
        
        for name, func in functions_to_check:
            if callable(func):
                print(f"✅ {name} - функция найдена")
            else:
                print(f"❌ {name} - не является функцией")
        
        # Проверяем регистрацию обработчиков (симулируем то, что делается в main())
        from telegram.ext import CommandHandler, CallbackQueryHandler, MessageHandler, filters
        
        handlers_to_register = [
            ("start", start),
            ("help", help_command),
            ("generate", character_gen.start_character_generation),
            ("character", show_character),
            ("party", show_party),
            ("startnewadventure", adventure_manager.start_new_adventure),
            ("terminateadventure", adventure_manager.terminate_adventure),
        ]
        
        print("\n=== Проверка регистрации команд ===")
        for command, handler in handlers_to_register:
            try:
                cmd_handler = CommandHandler(command, handler)
                application.add_handler(cmd_handler)
                print(f"✅ /{command} - зарегистрирована")
            except Exception as e:
                print(f"❌ /{command} - ошибка регистрации: {e}")
        
        print(f"\nВсего зарегистрировано обработчиков: {len(application.handlers[0])}")
        
    except Exception as e:
        print(f"❌ Ошибка импорта: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_handlers()
