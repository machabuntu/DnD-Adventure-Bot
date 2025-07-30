#!/usr/bin/env python3
import sys
import os
import asyncio
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import TELEGRAM_BOT_TOKEN
from telegram import Bot

async def test_bot_connection():
    """Тестируем подключение к Telegram Bot API"""
    try:
        bot = Bot(token=TELEGRAM_BOT_TOKEN)
        
        print("=== Получаем информацию о боте ===")
        me = await bot.get_me()
        print(f"✅ Бот подключен успешно!")
        print(f"   Username: @{me.username}")
        print(f"   Name: {me.first_name}")
        print(f"   ID: {me.id}")
        
        print("\n=== Получаем обновления ===")
        updates = await bot.get_updates(limit=5)
        print(f"Получено {len(updates)} последних обновлений:")
        
        for update in updates:
            if update.message:
                print(f"  - Update {update.update_id}: {update.message.text} from {update.message.from_user.id}")
            elif update.callback_query:
                print(f"  - Update {update.update_id}: callback from {update.callback_query.from_user.id}")
        
        # Проверяем webhook
        webhook_info = await bot.get_webhook_info()
        print(f"\n=== Webhook info ===")
        print(f"URL: {webhook_info.url}")
        print(f"Pending updates: {webhook_info.pending_update_count}")
        
    except Exception as e:
        print(f"❌ Ошибка подключения к боту: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_bot_connection())
