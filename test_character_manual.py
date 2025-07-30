#!/usr/bin/env python3
import sys
import os
import asyncio
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import ALLOWED_CHAT_ID
from database import get_db
from bot import format_character_display

class MockUpdate:
    def __init__(self, user_id, chat_id):
        self.effective_user = MockUser(user_id)
        self.effective_chat = MockChat(chat_id)
        self.message = MockMessage()

class MockUser:
    def __init__(self, user_id):
        self.id = user_id

class MockChat:
    def __init__(self, chat_id):
        self.id = chat_id

class MockMessage:
    async def reply_text(self, text, parse_mode=None):
        print(f"Bot replied: {text[:200]}..." if len(text) > 200 else f"Bot replied: {text}")

async def test_character_command():
    """Тестируем команду /character напрямую"""
    from bot import show_character
    
    # Получаем реального пользователя из базы
    db = get_db()
    if not db.connection or not db.connection.is_connected():
        db.connect()
    
    characters = db.execute_query("SELECT user_id FROM characters WHERE is_active = TRUE LIMIT 1")
    if not characters:
        print("❌ Нет активных персонажей для тестирования")
        return
    
    user_id = characters[0]['user_id']
    print(f"Тестируем с user_id: {user_id}")
    print(f"ALLOWED_CHAT_ID: {ALLOWED_CHAT_ID}")
    
    # Создаем mock объекты
    update = MockUpdate(user_id, ALLOWED_CHAT_ID)
    context = None  # Не используется в нашей функции
    
    print("\n=== Вызываем show_character ===")
    try:
        await show_character(update, context)
        print("✅ Функция show_character выполнена без ошибок")
    except Exception as e:
        print(f"❌ Ошибка в show_character: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_character_command())
