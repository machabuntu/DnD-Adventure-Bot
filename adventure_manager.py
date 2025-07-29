import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import get_db
from grok_api import grok
import asyncio

logger = logging.getLogger(__name__)

class AdventureManager:
    def __init__(self):
        self.db = get_db()

    async def start_new_adventure(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        
        if not self.db.connection or not self.db.connection.is_connected():
            self.db.connect()

        # Check if there is already an active adventure
        active_adventure = self.db.execute_query(
            "SELECT id FROM adventures WHERE chat_id = %s AND status = 'active'",
            (update.effective_chat.id,)
        )

        if active_adventure:
            await update.message.reply_text("Already there is an active adventure. Terminate it first.")
            return

        characters = self.db.execute_query(
            "SELECT id, name FROM characters WHERE user_id = %s AND is_active = TRUE",
            (user_id,)
        )

        if not characters:
            await update.message.reply_text("You need a character to start an adventure. Generate one first.")
            return

        # Create new adventure
        result = self.db.execute_query(
            "INSERT INTO adventures (chat_id, status) VALUES (%s, 'preparing')",
            (update.effective_chat.id,)
        )

        if result:
            # Get the created adventure ID
            adventure_id_result = self.db.execute_query("SELECT LAST_INSERT_ID() as id")
            if adventure_id_result:
                adventure_id = adventure_id_result[0]['id']
                
                await update.message.reply_text("Adventure created! Invite others to join.")
                self.db.execute_query(
                    "INSERT INTO adventure_participants (adventure_id, character_id) VALUES (%s, %s)",
                    (adventure_id, characters[0]['id'])
                )
                # Output current party composition
                await self.show_party_composition(update, context, adventure_id)

    async def show_party_composition(self, update: Update, context: ContextTypes.DEFAULT_TYPE, adventure_id: int):
        if not self.db.connection or not self.db.connection.is_connected():
            self.db.connect()

        participants = self.db.execute_query(
            "SELECT characters.name FROM adventure_participants "
            "INNER JOIN characters ON adventure_participants.character_id = characters.id "
            "WHERE adventure_participants.adventure_id = %s",
            (adventure_id,)
        )

        if not participants:
            return

        party_names = [p['name'] for p in participants]
        party_text = f"🎉 Current party members:\n" + "\n".join(party_names)

        # Present option to start the adventure
        keyboard = [[InlineKeyboardButton("Start Adventure", callback_data=f"start_adventure_{adventure_id}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(party_text, reply_markup=reply_markup)

    async def handle_start_adventure(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()

        if not self.db.connection or not self.db.connection.is_connected():
            self.db.connect()

        adventure_id = int(query.data.split('_')[-1])
        
        # Get characters information
        characters = self.db.execute_query(
            "SELECT c.*, r.name as race_name, o.name as origin_name, cl.name as class_name "
            "FROM adventure_participants ap "
            "INNER JOIN characters c ON ap.character_id = c.id "
            "LEFT JOIN races r ON c.race_id = r.id "
            "LEFT JOIN origins o ON c.origin_id = o.id "
            "LEFT JOIN classes cl ON c.class_id = cl.id "
            "WHERE ap.adventure_id = %s",
            (adventure_id,)
        )

        if not characters:
            await query.edit_message_text("No participants found.")
            return

        # Generate adventure intro
        intro_text = await asyncio.to_thread(grok.generate_adventure_intro, adventure_id, characters)

        await query.edit_message_text(intro_text)
        # Update adventure status
        self.db.execute_query(
            "UPDATE adventures SET status = 'active' WHERE id = %s",
            (adventure_id,)
        )

    async def terminate_adventure(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.db.connection or not self.db.connection.is_connected():
            self.db.connect()

        # Checking if there is an active adventure
        active_adventure = self.db.execute_query(
            "SELECT id FROM adventures WHERE chat_id = %s AND status = 'active'",
            (update.effective_chat.id,)
        )

        if not active_adventure:
            await update.message.reply_text("No active adventure to terminate.")
            return

        # Terminate the active adventure
        adventure_id = active_adventure[0]['id']
        self.db.execute_query("UPDATE adventures SET status = 'terminated' WHERE id = %s", (adventure_id,))

        await update.message.reply_text("The adventure has been terminated.")

# Global instance
adventure_manager = AdventureManager()
