import logging
import re
from telegram import Update
from telegram.ext import ContextTypes
from database import get_db
from grok_api import grok
from combat_manager import combat_manager
from telegram_utils import send_long_message
from spell_slot_manager import spell_slot_manager
import asyncio

logger = logging.getLogger(__name__)

class ActionHandler:
    def __init__(self):
        self.db = get_db()
        self.pending_actions = {}  # Store pending actions per adventure

    async def handle_action_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /action command from players"""
        if not context.args:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="Использование: /action <описание действия>")
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
            await context.bot.send_message(chat_id=update.effective_chat.id, text="Вы не участвуете в активном приключении.")
            return

        character = character_info[0]
        adventure_id = character['adventure_id']
        character_id = character['id']
        
        # Проверяем навыки и заклинания в квадратных скобках
        skill_spell_pattern = r'\[([^\]]+)\]'
        matches = re.findall(skill_spell_pattern, action_text)
        
        if matches:
            # Получаем навыки персонажа
            character_skills = self.db.execute_query(
                "SELECT skill_name FROM character_skills WHERE character_id = %s",
                (character_id,)
            )
            skill_names = [skill['skill_name'] for skill in character_skills] if character_skills else []
            
            # Получаем заклинания персонажа с уровнем
            character_spells = self.db.execute_query(
                "SELECT s.name, s.level, s.id FROM character_spells cs "
                "JOIN spells s ON cs.spell_id = s.id "
                "WHERE cs.character_id = %s",
                (character_id,)
            )
            spell_data = {spell['name']: {'level': spell['level'], 'id': spell['id']} 
                         for spell in character_spells} if character_spells else {}
            spell_names = list(spell_data.keys())
            
            # Проверяем каждое упоминание в квадратных скобках
            for match in matches:
                if match not in skill_names and match not in spell_names:
                    await context.bot.send_message(
                        chat_id=update.effective_chat.id,
                        text=f"❌ У вашего персонажа нет навыка или заклинания '{match}'. "
                        f"Доступные навыки: {', '.join(skill_names) if skill_names else 'нет'}. "
                        f"Доступные заклинания: {', '.join(spell_names) if spell_names else 'нет'}."
                    )
                    return
                
                # Если это заклинание, проверяем наличие слотов
                if match in spell_names:
                    spell_level = spell_data[match]['level']
                    if not spell_slot_manager.has_available_slot(character_id, spell_level):
                        slot_info = spell_slot_manager.get_spell_slots_info(character_id)
                        await context.bot.send_message(
                            chat_id=update.effective_chat.id,
                            text=f"❌ У вас нет доступных слотов для заклинания '{match}' (уровень {spell_level})!\n\n{slot_info}"
                        )
                        return
            
            # Расходуем слоты заклинаний (после всех проверок)
            used_spells = []
            for match in matches:
                if match in spell_names:
                    spell_level = spell_data[match]['level']
                    used_slot_level = spell_slot_manager.use_spell_slot(character_id, spell_level)
                    if used_slot_level is not None:
                        used_spell_text = f"{match}"
                        if used_slot_level > spell_level:
                            used_spell_text += f" (использован слот {used_slot_level} уровня)"
                        used_spells.append(used_spell_text)
                        logger.info(f"Character {character_id} used spell slot for '{match}'")

        # Store the action
        if adventure_id not in self.pending_actions:
            self.pending_actions[adventure_id] = {}

        self.pending_actions[adventure_id][user_id] = {
            'character_name': character['name'],
            'action': action_text
        }
        
        # Подтверждение действия с информацией об использованных слотах
        confirmation_text = f"✅ Действие записано: {action_text}"
        if 'used_spells' in locals() and used_spells:
            confirmation_text += f"\n🔮 Использованы заклинания: {', '.join(used_spells)}"
            slot_info = spell_slot_manager.get_spell_slots_info(character_id)
            confirmation_text += f"\n{slot_info}"

        await context.bot.send_message(chat_id=update.effective_chat.id, text=confirmation_text)

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
        
        logger.info(f"ACTION DEBUG: Processing actions for adventure {adventure_id}")
        logger.info(f"ACTION DEBUG: Number of actions: {len(actions)}")
        for i, action in enumerate(actions):
            logger.info(f"ACTION DEBUG: Action {i+1}: {action['character_name']} - {action['action']}")
        
        # Send to Grok
        logger.info(f"ACTION DEBUG: Sending actions to Grok API...")
        response_text, enemies, xp_reward = await asyncio.to_thread(
            grok.continue_adventure, 
            adventure_id, 
            actions
        )
        
        logger.info(f"ACTION DEBUG: Received response from Grok API")
        logger.info(f"ACTION DEBUG: Response length: {len(response_text)} characters")
        logger.info(f"ACTION DEBUG: Number of enemies parsed: {len(enemies)}")
        logger.info(f"ACTION DEBUG: XP reward: {xp_reward}")
        logger.info(f"ACTION DEBUG: Response contains COMBAT_START: {'***COMBAT_START***' in response_text}")

        # Clean response for players (remove enemy stats)
        clean_response = grok.clean_response_for_players(response_text)
        logger.info(f"ACTION DEBUG: Clean response length: {len(clean_response)} characters")
        
        # Send response to chat
        logger.info(f"ACTION DEBUG: Sending clean response to chat...")
        await send_long_message(update, context, clean_response)

        # Handle XP reward if any
        if xp_reward > 0:
            logger.info(f"ACTION DEBUG: Awarding {xp_reward} XP to participants")
            await self.award_experience(update, adventure_id, xp_reward)

        # Check if adventure should end
        if grok.is_adventure_ended(response_text):
            logger.info(f"ACTION DEBUG: Adventure end trigger detected, ending adventure {adventure_id}")
            await self.end_adventure(update, context, adventure_id)
            return

        # Handle combat if enemies were generated
        if enemies:
            logger.info(f"ACTION DEBUG: Starting combat with {len(enemies)} enemies!")
            for i, enemy in enumerate(enemies):
                logger.info(f"ACTION DEBUG: Enemy {i+1}: {enemy['name']} (HP: {enemy['hit_points']})")
            await combat_manager.start_combat(update, context, adventure_id, enemies)
            # Update adventure status to combat
            self.db.execute_query(
                "UPDATE adventures SET status = 'combat' WHERE id = %s",
                (adventure_id,)
            )
            logger.info(f"ACTION DEBUG: Adventure status updated to 'combat'")
        else:
            logger.info(f"ACTION DEBUG: No enemies found, continuing normal adventure")

        # Clear pending actions
        self.pending_actions[adventure_id] = {}
        logger.info(f"ACTION DEBUG: Cleared pending actions for adventure {adventure_id}")

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

        await context.bot.send_message(chat_id=update.effective_chat.id, text=xp_text)

    def calculate_level_from_xp(self, xp: int) -> int:
        """Calculate character level from experience points"""
        if not self.db.connection or not self.db.connection.is_connected():
            self.db.connect()

        level_data = self.db.execute_query(
            "SELECT level FROM levels WHERE experience_required <= %s ORDER BY level DESC LIMIT 1",
            (xp,)
        )

        return level_data[0]['level'] if level_data else 1
    
    async def end_adventure(self, update: Update, context: ContextTypes.DEFAULT_TYPE, adventure_id: int):
        """Завершает приключение"""
        if not self.db.connection or not self.db.connection.is_connected():
            self.db.connect()
        
        logger.info(f"ACTION DEBUG: Ending adventure {adventure_id}")
        
        # Update adventure status to finished
        self.db.execute_query(
            "UPDATE adventures SET status = 'finished' WHERE id = %s",
            (adventure_id,)
        )
        
        # Clear any pending actions
        if adventure_id in self.pending_actions:
            del self.pending_actions[adventure_id]
        
        # Clear combat data if any
        self.db.execute_query(
            "DELETE FROM combat_participants WHERE adventure_id = %s",
            (adventure_id,)
        )
        
        # Also clear accumulated combat metrics for this adventure
        self.db.execute_query(
            "DELETE FROM combat_metrics WHERE adventure_id = %s",
            (adventure_id,)
        )
        
        # Send adventure end message
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="🎆 Приключение завершено!\n\n"
                 "Спасибо за игру! Для нового приключения используйте /start_adventure."
        )
        
        logger.info(f"ACTION DEBUG: Adventure {adventure_id} ended successfully")

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
            # Join the existing adventure
            self.db.execute_query(
                "INSERT IGNORE INTO adventure_participants (adventure_id, character_id) VALUES (%s, %s)",
                (adventure[0]['id'], character[0]['id'])
            )
            await query.edit_message_text(f"✅ {character[0]['name']} присоединился к группе!")
        else:
            # No preparing adventure exists, create a new one automatically
            logger.info(f"No preparing adventure found, creating new one for user {user_id} in chat {update.effective_chat.id}")
            
            # Check if there's already an active adventure
            active_adventure = self.db.execute_query(
                "SELECT id FROM adventures WHERE chat_id = %s AND status = 'active'",
                (update.effective_chat.id,)
            )
            
            if active_adventure:
                await query.edit_message_text("В этом чате уже есть активное приключение. Сначала завершите его.")
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
                    
                    # Add the character to the new adventure
                    self.db.execute_query(
                        "INSERT INTO adventure_participants (adventure_id, character_id) VALUES (%s, %s)",
                        (adventure_id, character[0]['id'])
                    )
                    
                    await query.edit_message_text(
                        f"🎉 Создана новая группа!\n"
                        f"✅ {character[0]['name']} присоединился к группе!\n\n"
                        f"Пригласите других игроков присоединиться, затем используйте команды для начала приключения."
                    )
                    
                    logger.info(f"Created new adventure {adventure_id} and added character {character[0]['id']} to it")
                else:
                    await query.edit_message_text("Ошибка при создании группы.")
            else:
                await query.edit_message_text("Ошибка при создании группы.")

# Global instance
action_handler = ActionHandler()
