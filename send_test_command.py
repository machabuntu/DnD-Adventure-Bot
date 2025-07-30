#!/usr/bin/env python3
import sys
import os
import asyncio
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import TELEGRAM_BOT_TOKEN, ALLOWED_CHAT_ID
from telegram import Bot

async def send_test_command():
    """Отправляем тестовую команду /character"""
    try:
        bot = Bot(token=TELEGRAM_BOT_TOKEN)
        
        # Получаем информацию о боте
        me = await bot.get_me()
        print(f"Бот: @{me.username} (ID: {me.id})")
        
        # Получаем информацию о чате
        try:
            chat = await bot.get_chat(ALLOWED_CHAT_ID)
            print(f"Чат: {chat.title if chat.title else chat.first_name} (ID: {chat.id})")
        except Exception as e:
            print(f"Не удалось получить информацию о чате: {e}")
        
        # Отправляем команду /start для проверки
        print("\n=== Отправляем /start ===")
        try:
            message = await bot.send_message(chat_id=ALLOWED_CHAT_ID, text="/start")
            print(f"✅ Команда /start отправлена (ID сообщения: {message.message_id})")
        except Exception as e:
            print(f"❌ Ошибка отправки /start: {e}")
        
        # Небольшая пауза
        await asyncio.sleep(2)
        
        # Отправляем команду /character для проверки
        print("\n=== Отправляем /character ===")
        try:
            message = await bot.send_message(chat_id=ALLOWED_CHAT_ID, text="/character")
            print(f"✅ Команда /character отправлена (ID сообщения: {message.message_id})")
        except Exception as e:
            print(f"❌ Ошибка отправки /character: {e}")
        
        # Ждем и получаем последние обновления
        await asyncio.sleep(3)
        print("\n=== Проверяем последние обновления ===")
        updates = await bot.get_updates(limit=10)
        
        for update in updates[-10:]:  # Показываем последние 10
            if update.message:
                user_id = update.message.from_user.id
                text = update.message.text
                print(f"Update {update.update_id}: от {user_id} - '{text}'")
            
    except Exception as e:
        print(f"❌ Общая ошибка: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(send_test_command())
