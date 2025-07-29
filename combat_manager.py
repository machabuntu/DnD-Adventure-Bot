import logging
import random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import get_db
from grok_api import grok
import asyncio

logger = logging.getLogger(__name__)

class CombatManager:
    def __init__(self):
        self.db = get_db()

    def roll_initiative(self, dex_modifier: int) -> int:
        """Roll initiative for a participant."""
        return random.randint(1, 20) + dex_modifier

    async def start_combat(self, update: Update, context: ContextTypes.DEFAULT_TYPE, adventure_id: int, enemies: list):
        """Initialize combat and determine initiative order."""
        if not self.db.connection or not self.db.connection.is_connected():
            self.db.connect()

        participants = []

        # Characters' initiatives
        char_query = ("SELECT c.id, c.name, c.dexterity "
                      "FROM adventure_participants ap "
                      "INNER JOIN characters c ON ap.character_id = c.id "
                      "WHERE ap.adventure_id = %s")
        chars = self.db.execute_query(char_query, (adventure_id,))
        
        for char in chars:
            dex_modifier = (char['dexterity'] - 10) // 2
            initiative = self.roll_initiative(dex_modifier)
            participants.append({'type': 'character', 'name': char['name'], 'id': char['id'], 'initiative': initiative})

        # Enemies' initiatives
        for enemy in enemies:
            enemy_id = enemy['id']
            dex_modifier = (enemy['dexterity'] - 10) // 2
            initiative = self.roll_initiative(dex_modifier)
            participants.append({'type': 'enemy', 'name': enemy['name'], 'id': enemy_id, 'initiative': initiative})

        # Sort by initiative descending
        participants.sort(key=lambda x: x['initiative'], reverse=True)

        # Save combat data
        for turn_order, participant in enumerate(participants):
            self.db.execute_query(
                "INSERT INTO combat_participants (adventure_id, participant_type, participant_id, initiative, turn_order) "
                "VALUES (%s, %s, %s, %s, %s)",
                (adventure_id, participant['type'], participant['id'], participant['initiative'], turn_order)
            )

        # Inform players
        await self.show_initiative_order(update, adventure_id)

    async def show_initiative_order(self, update: Update, adventure_id: int):
        """Show the initiative order to the players."""
        if not self.db.connection or not self.db.connection.is_connected():
            self.db.connect()

        order_query = ("SELECT cp.participant_type, cp.initiative, "
                       "CASE WHEN cp.participant_type = 'character' THEN c.name ELSE e.name END as name "
                       "FROM combat_participants cp "
                       "LEFT JOIN characters c ON cp.participant_id = c.id AND cp.participant_type = 'character' "
                       "LEFT JOIN enemies e ON cp.participant_id = e.id AND cp.participant_type = 'enemy' "
                       "WHERE cp.adventure_id = %s ORDER BY cp.turn_order")

        order = self.db.execute_query(order_query, (adventure_id,))

        if order:
            order_text = "🔥 Initiative Order:\n" + "\n".join([f"{p['name']} ({p['participant_type']}) - {p['initiative']}" for p in order])
            await update.message.reply_text(order_text)

    async def handle_turn(self, update: Update, context: ContextTypes.DEFAULT_TYPE, adventure_id: int, turn_index: int):
        """Progress through turns."""
        if not self.db.connection or not self.db.connection.is_connected():
            self.db.connect()

        # Get current participant
        turn_query = ("SELECT cp.participant_type, cp.participant_id, cp.turn_order, "
                      "CASE WHEN cp.participant_type = 'character' THEN c.name ELSE e.name END as name "
                      "FROM combat_participants cp "
                      "LEFT JOIN characters c ON cp.participant_id = c.id AND cp.participant_type = 'character' "
                      "LEFT JOIN enemies e ON cp.participant_id = e.id AND cp.participant_type = 'enemy' "
                      "WHERE cp.adventure_id = %s AND cp.turn_order = %s")

        current_turn = self.db.execute_query(turn_query, (adventure_id, turn_index))

        if not current_turn:
            await self.end_combat(update, adventure_id, victory=None)
            return

        participant = current_turn[0]
        
        if participant['participant_type'] == 'character':
            # Display player's actions options
            await self.display_actions(update, participant['participant_id'])
        else:
            # Enemy's turn
            await self.enemy_action(update, adventure_id, participant)

        # Move to next turn, loop back to start
        next_turn = (turn_index + 1) % len(current_turn)
        await self.handle_turn(update, context, adventure_id, next_turn)

    async def display_actions(self, update: Update, character_id: int):
        """Display action choices to the player."""
        keyboard = [
            [InlineKeyboardButton("Attack", callback_data=f"action_attack_{character_id}")],
            [InlineKeyboardButton("Cast Spell", callback_data=f"action_spell_{character_id}")],
            [InlineKeyboardButton("Pass Turn", callback_data=f"action_pass_{character_id}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text("Choose your action:", reply_markup=reply_markup)

    async def enemy_action(self, update: Update, adventure_id: int, enemy: dict):
        """Perform an enemy action."""
        # Select random character target
        target_query = ("SELECT c.id, c.name FROM characters c "
                        "JOIN adventure_participants ap ON c.id = ap.character_id "
                        "WHERE ap.adventure_id = %s")

        targets = self.db.execute_query(target_query, (adventure_id,))
        if not targets:
            await self.end_combat(update, adventure_id, victory='enemies')
            return

        target = random.choice(targets)
        
        # Perform attack (simple damage roll)
        damage_roll = random.randint(1, 6) + enemy['dexterity'] - 10 // 2
        result_text = f"{enemy['name']} attacks {target['name']} for {damage_roll} damage!"

        await update.message.reply_text(result_text)

    async def end_combat(self, update: Update, adventure_id: int, victory: str = None):
        """End combat and declare outcome."""
        if victory == 'players':
            await update.message.reply_text("🎊 Players have won the combat!")
        elif victory == 'enemies':
            await update.message.reply_text("💀 Enemies have won the combat...")
        else:
            await update.message.reply_text("Combat ended.")

        # Clear combat data
        self.db.execute_query("DELETE FROM combat_participants WHERE adventure_id = %s", (adventure_id,))

        # Update adventure status
        self.db.execute_query("UPDATE adventures SET status = 'active' WHERE id = %s", (adventure_id,))
        
        # Inform Grok
        await asyncio.to_thread(grok.inform_combat_end, adventure_id, victory or "unknown")

# Global Instance
combat_manager = CombatManager()
