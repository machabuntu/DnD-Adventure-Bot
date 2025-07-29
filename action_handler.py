import logging
from telegram import Update
from telegram.ext import ContextTypes
from database import get_db
from grok_api import grok
from combat_manager import combat_manager
import asyncio

logger = logging.getLogger(__name__)

class ActionHandler:
    def __init__(self):
        self.db = get_db()
        self.pending_actions = {}  # Store pending actions per adventure

    async def handle_action_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /action command from players"""
        if not context.args:
            await update.message.reply_text("Использование: /action <описание действия>")
            return

        user_id = update.effective_user.id
        action_text = " ".join(context.args)

        if not self.db.connection or not self.db.connection.is_connected():
            self.db.connect()

        # Check if user has character in active adventure
        character_info = self.db.execute_query("""
            SELECT c.id, c.name, a.id as adventure_id
            FROM characters c
            JOIN adventure_participants ap ON c.id = ap.character_id
            JOIN adventures a ON ap.adventure_id = a.id
            WHERE c.user_id = %s AND a.status = 'active' AND a.chat_id = %s
        """, (user_id, update.effective_chat.id))

        if not character_info:
            await update.message.reply_text("Вы не участвуете в активном приключении.")
            return

        character = character_info[0]
        adventure_id = character['adventure_id']

        # Store the action
        if adventure_id not in self.pending_actions:
            self.pending_actions[adventure_id] = {}

        self.pending_actions[adventure_id][user_id] = {
            'character_name': character['name'],
            'action': action_text
        }

        await update.message.reply_text(f"✅ Действие записано: {action_text}")

        # Check if all participants have submitted actions
        await self.check_all_actions_submitted(update, context, adventure_id)

    async def check_all_actions_submitted(self, update: Update, context: ContextTypes.DEFAULT_TYPE, adventure_id: int):
        """Check if all participants have submitted their actions"""
        if not self.db.connection or not self.db.connection.is_connected():
            self.db.connect()

        # Get all participants
        participants = self.db.execute_query("""
            SELECT c.user_id, c.name
            FROM adventure_participants ap
            JOIN characters c ON ap.character_id = c.id
            WHERE ap.adventure_id = %s
        """, (adventure_id,))

        if not participants:
            return

        participant_ids = [p['user_id'] for p in participants]
        submitted_ids = list(self.pending_actions.get(adventure_id, {}).keys())

        # Check if all participants submitted actions
        if set(participant_ids) == set(submitted_ids):
            await self.process_actions(update, context, adventure_id)

    async def process_actions(self, update: Update, context: ContextTypes.DEFAULT_TYPE, adventure_id: int):
        """Process all submitted actions with Grok"""
        actions = list(self.pending_actions[adventure_id].values())
        
        # Send to Grok
        response_text, enemies, xp_reward = await asyncio.to_thread(
            grok.continue_adventure, 
            adventure_id, 
            actions
        )

        # Send response to chat
        await update.message.reply_text(response_text)

        # Handle XP reward if any
        if xp_reward > 0:
            await self.award_experience(update, adventure_id, xp_reward)

        # Handle combat if enemies were generated
        if enemies:
            await combat_manager.start_combat(update, context, adventure_id, enemies)
            # Update adventure status to combat
            self.db.execute_query(
                "UPDATE adventures SET status = 'combat' WHERE id = %s",
                (adventure_id,)
            )

        # Clear pending actions
        self.pending_actions[adventure_id] = {}

    async def award_experience(self, update: Update, adventure_id: int, xp_amount: int):
        """Award experience to all participants"""
        if not self.db.connection or not self.db.connection.is_connected():
            self.db.connect()

        # Get all participants
        participants = self.db.execute_query("""
            SELECT c.id, c.name, c.experience, c.level
            FROM adventure_participants ap
            JOIN characters c ON ap.character_id = c.id
            WHERE ap.adventure_id = %s
        """, (adventure_id,))

        leveled_up = []

        for participant in participants:
            new_xp = participant['experience'] + xp_amount
            
            # Check for level up
            new_level = self.calculate_level_from_xp(new_xp)
            old_level = participant['level']

            # Update character
            self.db.execute_query(
                "UPDATE characters SET experience = %s, level = %s WHERE id = %s",
                (new_xp, new_level, participant['id'])
            )

            if new_level > old_level:
                leveled_up.append(f"{participant['name']} достиг {new_level} уровня!")

        # Notify about XP and level ups
        xp_text = f"🌟 Участники получают {xp_amount} опыта!"
        if leveled_up:
            xp_text += "\n\n🎊 Повышения уровня:\n" + "\n".join(leveled_up)

        await update.message.reply_text(xp_text)

    def calculate_level_from_xp(self, xp: int) -> int:
        """Calculate character level from experience points"""
        if not self.db.connection or not self.db.connection.is_connected():
            self.db.connect()

        level_data = self.db.execute_query(
            "SELECT level FROM levels WHERE experience_required <= %s ORDER BY level DESC LIMIT 1",
            (xp,)
        )

        return level_data[0]['level'] if level_data else 1

    async def handle_join_group_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle join group callback from character creation"""
        query = update.callback_query
        await query.answer()

        user_id = update.effective_user.id

        if not self.db.connection or not self.db.connection.is_connected():
            self.db.connect()

        # Check if user has character
        character = self.db.execute_query(
            "SELECT id, name FROM characters WHERE user_id = %s AND is_active = TRUE",
            (user_id,)
        )

        if not character:
            await query.edit_message_text("У вас нет активного персонажа.")
            return

        # Check if there's a preparing adventure
        adventure = self.db.execute_query(
            "SELECT id FROM adventures WHERE chat_id = %s AND status = 'preparing'",
            (update.effective_chat.id,)
        )

        if adventure:
            # Join the adventure
            self.db.execute_query(
                "INSERT IGNORE INTO adventure_participants (adventure_id, character_id) VALUES (%s, %s)",
                (adventure[0]['id'], character[0]['id'])
            )
            await query.edit_message_text(f"✅ {character[0]['name']} присоединился к группе!")
        else:
            await query.edit_message_text("Нет доступных приключений для присоединения.")

# Global instance
action_handler = ActionHandler()
