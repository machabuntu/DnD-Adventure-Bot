#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Модуль для обработки команд отдыха персонажей с голосованием
"""

import logging
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import get_db
from spell_slot_manager import spell_slot_manager

logger = logging.getLogger(__name__)

class RestHandler:
    def __init__(self):
        self.db = get_db()
        self.rest_votes = {}  # {adventure_id: {user_id: bool}}
        self.rest_message_ids = {}  # {adventure_id: message_id}
        
    async def handle_rest_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Инициация голосования за отдых"""
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        
        if not self.db.connection or not self.db.connection.is_connected():
            self.db.connect()
        
        # Проверяем, есть ли у игрока персонаж в активном приключении
        adventure_info = self.db.execute_query("""
            SELECT a.id, a.status, c.id as character_id, c.name
            FROM adventures a
            JOIN adventure_participants ap ON a.id = ap.adventure_id
            JOIN characters c ON ap.character_id = c.id
            WHERE c.user_id = %s AND a.chat_id = %s AND a.status = 'active'
        """, (user_id, chat_id))
        
        if not adventure_info:
            await update.message.reply_text("❌ Вы не участвуете в активном приключении или приключение в состоянии боя.")
            return
        
        adventure_id = adventure_info[0]['id']
        character_name = adventure_info[0]['name']
        
        # Проверяем, не идет ли уже голосование за отдых
        if adventure_id in self.rest_votes:
            await update.message.reply_text("⏳ Голосование за отдых уже идет!")
            return
        
        # Получаем всех участников приключения
        participants = self.db.execute_query("""
            SELECT c.user_id, c.name
            FROM adventure_participants ap
            JOIN characters c ON ap.character_id = c.id
            WHERE ap.adventure_id = %s
        """, (adventure_id,))
        
        if len(participants) < 2:
            # Если игрок один, сразу отправляем на отдых
            await self.initiate_rest(update, context, adventure_id)
            return
        
        # Инициализируем голосование
        self.rest_votes[adventure_id] = {user_id: True}  # Инициатор автоматически голосует "за"
        
        # Создаем кнопки для голосования
        keyboard = [
            [InlineKeyboardButton("✅ За отдых (1)", callback_data=f"rest_vote_yes_{adventure_id}")],
            [InlineKeyboardButton("❌ Против отдыха (0)", callback_data=f"rest_vote_no_{adventure_id}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Формируем список участников для отображения
        participants_text = "\n".join([f"• {p['name']}" for p in participants])
        total_needed = len(participants) // 2 + (1 if len(participants) % 2 == 1 else 0)
        
        vote_text = f"""
🏕️ **Голосование за отдых**

{character_name} предлагает устроить привал и отдохнуть.

👥 **Участники приключения:**
{participants_text}

📊 Для принятия решения нужно минимум **{total_needed}** голосов из **{len(participants)}**

⏱️ Голосование продлится 30 секунд.
        """
        
        message = await update.message.reply_text(
            vote_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        
        self.rest_message_ids[adventure_id] = message.message_id
        
        # Запускаем таймер на 30 секунд
        await asyncio.sleep(30)
        await self.finalize_rest_vote(update, context, adventure_id)
    
    async def handle_rest_vote(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка голосования за отдых"""
        query = update.callback_query
        data = query.data
        user_id = update.effective_user.id
        
        # Парсим callback data
        parts = data.split('_')
        vote_type = parts[2]  # yes или no
        adventure_id = int(parts[3])
        
        if not self.db.connection or not self.db.connection.is_connected():
            self.db.connect()
        
        # Проверяем, что голосование активно
        if adventure_id not in self.rest_votes:
            await query.answer("Голосование уже завершено")
            return
        
        # Проверяем, является ли пользователь участником приключения
        participant = self.db.execute_query("""
            SELECT c.id, c.name
            FROM adventure_participants ap
            JOIN characters c ON ap.character_id = c.id
            WHERE ap.adventure_id = %s AND c.user_id = %s
        """, (adventure_id, user_id))
        
        if not participant:
            await query.answer("Вы не участвуете в этом приключении")
            return
        
        # Записываем голос
        self.rest_votes[adventure_id][user_id] = (vote_type == "yes")
        
        # Обновляем сообщение с количеством голосов
        await self.update_vote_display(query, adventure_id)
        await query.answer(f"Ваш голос {'за' if vote_type == 'yes' else 'против'} отдых учтен!")
        
    async def update_vote_display(self, query, adventure_id: int):
        """Обновляет отображение голосования"""
        if adventure_id not in self.rest_votes:
            return
        
        # Получаем всех участников
        participants = self.db.execute_query("""
            SELECT c.user_id, c.name
            FROM adventure_participants ap
            JOIN characters c ON ap.character_id = c.id
            WHERE ap.adventure_id = %s
        """, (adventure_id,))
        
        votes = self.rest_votes[adventure_id]
        yes_votes = sum(1 for v in votes.values() if v)
        no_votes = sum(1 for v in votes.values() if not v)
        total_needed = len(participants) // 2 + (1 if len(participants) % 2 == 1 else 0)
        
        # Формируем список кто как проголосовал
        vote_status = []
        for p in participants:
            if p['user_id'] in votes:
                vote_emoji = "✅" if votes[p['user_id']] else "❌"
                vote_status.append(f"{vote_emoji} {p['name']}")
            else:
                vote_status.append(f"⏳ {p['name']}")
        
        vote_status_text = "\n".join(vote_status)
        
        # Обновляем кнопки
        keyboard = [
            [InlineKeyboardButton(f"✅ За отдых ({yes_votes})", callback_data=f"rest_vote_yes_{adventure_id}")],
            [InlineKeyboardButton(f"❌ Против отдыха ({no_votes})", callback_data=f"rest_vote_no_{adventure_id}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        vote_text = f"""
🏕️ **Голосование за отдых**

📊 Для принятия решения нужно минимум **{total_needed}** голосов из **{len(participants)}**

**Статус голосования:**
{vote_status_text}

⏱️ Голосование активно...
        """
        
        try:
            await query.edit_message_text(
                vote_text,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
        except:
            pass  # Ignore if message wasn't modified
    
    async def finalize_rest_vote(self, update: Update, context: ContextTypes.DEFAULT_TYPE, adventure_id: int):
        """Завершает голосование и принимает решение"""
        if adventure_id not in self.rest_votes:
            return
        
        votes = self.rest_votes[adventure_id]
        
        # Получаем всех участников
        participants = self.db.execute_query("""
            SELECT c.user_id, c.name
            FROM adventure_participants ap
            JOIN characters c ON ap.character_id = c.id
            WHERE ap.adventure_id = %s
        """, (adventure_id,))
        
        yes_votes = sum(1 for v in votes.values() if v)
        total_needed = len(participants) // 2 + (1 if len(participants) % 2 == 1 else 0)
        
        # Удаляем сообщение с голосованием
        if adventure_id in self.rest_message_ids:
            try:
                await context.bot.delete_message(
                    chat_id=update.effective_chat.id,
                    message_id=self.rest_message_ids[adventure_id]
                )
            except:
                pass
            del self.rest_message_ids[adventure_id]
        
        # Очищаем данные голосования
        del self.rest_votes[adventure_id]
        
        if yes_votes >= total_needed:
            # Отдых принят
            await self.initiate_rest(update, context, adventure_id)
        else:
            # Отдых отклонен
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"❌ Голосование завершено. За отдых проголосовало {yes_votes} из необходимых {total_needed}. Приключение продолжается!"
            )
    
    async def initiate_rest(self, update: Update, context: ContextTypes.DEFAULT_TYPE, adventure_id: int):
        """Инициирует отдых для всей группы"""
        if not self.db.connection or not self.db.connection.is_connected():
            self.db.connect()
        
        # Получаем всех персонажей в приключении
        characters = self.db.execute_query("""
            SELECT c.id, c.name, c.current_hp, c.max_hp, cl.is_spellcaster
            FROM adventure_participants ap
            JOIN characters c ON ap.character_id = c.id
            JOIN classes cl ON c.class_id = cl.id
            WHERE ap.adventure_id = %s
        """, (adventure_id,))
        
        rest_text = "🏕️ **Группа устраивает длинный отдых (8 часов)**\n\n"
        
        for char in characters:
            # Полное восстановление HP
            self.db.execute_query(
                "UPDATE characters SET current_hp = max_hp WHERE id = %s",
                (char['id'],)
            )
            
            # Восстановление слотов для заклинателей
            if char['is_spellcaster']:
                spell_slot_manager.rest_long(char['id'])
            
            rest_text += f"• **{char['name']}**: ❤️ Здоровье восстановлено ({char['max_hp']}/{char['max_hp']})\n"
            if char['is_spellcaster']:
                rest_text += f"  🔮 Слоты заклинаний восстановлены\n"
        
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=rest_text,
            parse_mode='Markdown'
        )
        
        # Отправляем информацию о привале в Grok API для продолжения приключения
        from action_handler import action_handler
        
        # Формируем "действие" отдыха для отправки в Grok
        rest_action = {
            'character_name': 'Вся группа',
            'action': 'устраивает привал и отдыхает 8 часов, полностью восстанавливая силы'
        }
        
        # Сохраняем это как единственное действие в этом цикле
        if adventure_id not in action_handler.pending_actions:
            action_handler.pending_actions[adventure_id] = {}
        
        # Очищаем все предыдущие действия и добавляем только отдых
        action_handler.pending_actions[adventure_id] = {0: rest_action}  # Используем 0 как специальный ID для группового действия
        
        # Обрабатываем действие через обычный механизм
        await action_handler.process_actions(update, context, adventure_id)

# Глобальный экземпляр
rest_handler = RestHandler()
