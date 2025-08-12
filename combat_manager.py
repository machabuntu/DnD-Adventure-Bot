import logging
import random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Bot
from telegram.ext import ContextTypes
from database import get_db
from grok_api import grok
from telegram_utils import send_long_message
from dice_utils import roll_d20, roll_dice, roll_dice_detailed, is_critical_hit, is_critical_miss
from armor_utils import calculate_character_ac, update_character_ac
from achievement_manager import achievement_manager
from combat_achievements import init_combat, increment_round, get_round, record_damage_taken, award_end_combat_achievements
import asyncio

logger = logging.getLogger(__name__)

class CombatManager:
    def __init__(self):
        self.db = get_db()
    
    async def send_message_to_adventure(self, adventure_id: int, message: str, context: ContextTypes.DEFAULT_TYPE = None, reply_markup=None):
        """Send a message to the adventure chat using chat_id from database."""
        try:
            # Get chat_id for the adventure
            adventure_query = "SELECT chat_id FROM adventures WHERE id = %s"
            adventure_result = self.db.execute_query(adventure_query, (adventure_id,))
            
            if not adventure_result or not adventure_result[0]['chat_id']:
                logger.error(f"Could not find chat_id for adventure {adventure_id}")
                return False
            
            chat_id = adventure_result[0]['chat_id']
            
            # Send message using context bot if available
            if context and context.bot:
                if reply_markup:
                    await context.bot.send_message(chat_id=chat_id, text=message, reply_markup=reply_markup)
                else:
                    await context.bot.send_message(chat_id=chat_id, text=message)
                return True
            else:
                logger.warning("No context.bot available for sending message")
                return False
                
        except Exception as e:
            logger.error(f"Error sending message to adventure {adventure_id}: {e}")
            logger.exception("Full exception traceback:")
            return False

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
        
        # Инициализируем состояние боя (раунд, метрики)
        try:
            init_combat(adventure_id)
        except Exception as e:
            logger.warning(f"COMBAT INIT WARNING: failed to init combat state for adventure {adventure_id}: {e}")
        
        # Start the first turn
        await self.handle_turn(update, context, adventure_id, 0)

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
        logger.info(f"COMBAT DEBUG: Starting turn {turn_index} for adventure {adventure_id}")
        
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
            logger.info(f"COMBAT DEBUG: No participant found for turn {turn_index}, ending combat")
            await self.end_combat(update, adventure_id, victory=None, context=context)
            return

        participant = current_turn[0]
        logger.info(f"COMBAT DEBUG: Turn for {participant['name']} ({participant['participant_type']})")
        
        if participant['participant_type'] == 'character':
            # Display player's actions options and wait for response
            # The response will be handled by callback_handler which should call next_turn
            await self.display_actions(update, context, participant['participant_id'], adventure_id, turn_index)
        else:
            # Enemy's turn - execute immediately and move to next turn
            await self.enemy_action(update, adventure_id, participant, context)
            # Move to next turn automatically for enemies
            await self.next_turn(update, context, adventure_id, turn_index)

    async def display_actions(self, update: Update, context: ContextTypes.DEFAULT_TYPE, character_id: int, adventure_id: int, turn_index: int):
        """Display action choices to the player."""
        # Проверяем, есть ли у персонажа боевые заклинания
        combat_spells_query = """
            SELECT COUNT(*) as count
            FROM character_spells cs
            JOIN spells s ON cs.spell_id = s.id
            WHERE cs.character_id = %s AND s.is_combat = TRUE
        """
        
        has_combat_spells = self.db.execute_query(combat_spells_query, (character_id,))
        spell_count = has_combat_spells[0]['count'] if has_combat_spells else 0
        
        keyboard = [
            [InlineKeyboardButton("⚔️ Attack", callback_data=f"action_attack_{character_id}_{adventure_id}_{turn_index}")],
            [InlineKeyboardButton("⏭️ Pass Turn", callback_data=f"action_pass_{character_id}_{adventure_id}_{turn_index}")]
        ]
        
        # Добавляем кнопку заклинаний только если у персонажа есть боевые заклинания
        if spell_count > 0:
            keyboard.insert(1, [InlineKeyboardButton("🪄 Cast Spell", callback_data=f"action_spell_{character_id}_{adventure_id}_{turn_index}")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)

        # Try to send message using update.message first
        message_sent = False
        if update and hasattr(update, 'message') and update.message:
            try:
                await update.message.reply_text("Choose your action:", reply_markup=reply_markup)
                message_sent = True
                logger.info(f"DISPLAY ACTIONS DEBUG: Successfully sent via update.message")
            except Exception as e:
                logger.warning(f"DISPLAY ACTIONS DEBUG: Failed to send via update.message: {e}")
        
        # Fallback to callback query
        if not message_sent and hasattr(update, 'callback_query') and update.callback_query:
            try:
                await update.callback_query.message.reply_text("Choose your action:", reply_markup=reply_markup)
                message_sent = True
                logger.info(f"DISPLAY ACTIONS DEBUG: Successfully sent via callback_query")
            except Exception as e:
                logger.warning(f"DISPLAY ACTIONS DEBUG: Failed to send via callback_query: {e}")
        
        # Final fallback - use adventure messaging system with inline keyboard support
        if not message_sent and context:
            logger.info(f"DISPLAY ACTIONS DEBUG: Using adventure messaging system with inline keyboard")
            # Get character name for context
            char_query = "SELECT name FROM characters WHERE id = %s"
            char_result = self.db.execute_query(char_query, (character_id,))
            char_name = char_result[0]['name'] if char_result else "Unknown"
            
            # Send message with inline keyboard through adventure messaging system
            success = await self.send_message_to_adventure(
                adventure_id, 
                f"⚡ {char_name}, choose your action:", 
                context, 
                reply_markup
            )
            
            if success:
                message_sent = True
                logger.info(f"DISPLAY ACTIONS DEBUG: Successfully sent via adventure messaging system")
            else:
                logger.error(f"DISPLAY ACTIONS DEBUG: Failed to send via adventure messaging system")
        
        if not message_sent:
            logger.error(f"DISPLAY ACTIONS DEBUG: All fallback methods failed to send action selection message")
    
    async def display_attack_targets(self, update: Update, character_id: int, adventure_id: int, turn_index: int):
        """Display available attack targets for the player."""
        if not self.db.connection or not self.db.connection.is_connected():
            self.db.connect()
        
        # Get all alive enemies in the combat
        enemies_query = (
            "SELECT e.id, e.name, e.hit_points, e.max_hit_points "
            "FROM combat_participants cp "
            "JOIN enemies e ON cp.participant_id = e.id "
            "WHERE cp.adventure_id = %s AND cp.participant_type = 'enemy' AND e.hit_points > 0"
        )
        
        alive_enemies = self.db.execute_query(enemies_query, (adventure_id,))
        
        if not alive_enemies:
            # No enemies left - end combat
            await self.end_combat(update, adventure_id, victory='players')
            return
        
        # Create buttons for each alive enemy
        keyboard = []
        for enemy in alive_enemies:
            enemy_name = enemy['name']
            callback_data = f"target_{character_id}_{adventure_id}_{turn_index}_{enemy['id']}"
            keyboard.append([InlineKeyboardButton(enemy_name, callback_data=callback_data)])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.callback_query.edit_message_text("Choose your target:", reply_markup=reply_markup)
    
    async def next_turn(self, update: Update, context: ContextTypes.DEFAULT_TYPE, adventure_id: int, current_turn_index: int):
        """Move to the next turn in combat."""
        if not self.db.connection or not self.db.connection.is_connected():
            self.db.connect()
        
        # Get total number of participants
        participants_query = "SELECT COUNT(*) as count FROM combat_participants WHERE adventure_id = %s"
        participants_count_result = self.db.execute_query(participants_query, (adventure_id,))
        
        if not participants_count_result:
            logger.error(f"COMBAT DEBUG: Could not get participant count for adventure {adventure_id}")
            await self.end_combat(update, adventure_id, victory=None, context=context)
            return
            
        total_participants = participants_count_result[0]['count']
        next_turn_index = (current_turn_index + 1) % total_participants
        
        logger.info(f"COMBAT DEBUG: Moving from turn {current_turn_index} to turn {next_turn_index} (total: {total_participants})")
        
        # Если круг завершился, увеличиваем номер раунда
        if next_turn_index == 0:
            try:
                increment_round(adventure_id)
                logger.info(f"COMBAT DEBUG: Round incremented to {get_round(adventure_id)} for adventure {adventure_id}")
            except Exception as e:
                logger.warning(f"COMBAT ROUND WARNING: failed to increment round for adventure {adventure_id}: {e}")
        
        # Continue to next turn
        await self.handle_turn(update, context, adventure_id, next_turn_index)

    async def enemy_action(self, update: Update, adventure_id: int, participant: dict, context: ContextTypes.DEFAULT_TYPE = None):
        """Perform an enemy action."""
        logger.info(f"ENEMY ACTION DEBUG: Starting enemy action for participant {participant}")
        
        try:
            # Get full enemy data from database
            enemy_query = "SELECT * FROM enemies WHERE id = %s"
            logger.info(f"ENEMY ACTION DEBUG: Getting enemy data with query: {enemy_query}")
            enemy_data = self.db.execute_query(enemy_query, (participant['participant_id'],))
            
            if not enemy_data:
                logger.error(f"COMBAT DEBUG: Could not find enemy data for participant_id {participant['participant_id']}")
                return
            
            enemy = enemy_data[0]
            enemy_name = enemy['name']
            
            # Check if enemy is still alive before attacking
            if enemy['hit_points'] <= 0:
                logger.info(f"ENEMY ACTION DEBUG: Enemy {enemy_name} is dead (HP: {enemy['hit_points']}), skipping turn")
                return
            
            # Select random character target
            target_query = ("SELECT c.id, c.name, c.current_hp, c.max_hp FROM characters c "
                            "JOIN adventure_participants ap ON c.id = ap.character_id "
                            "WHERE ap.adventure_id = %s AND c.current_hp > 0")

            targets = self.db.execute_query(target_query, (adventure_id,))
            if not targets:
                logger.info(f"ENEMY ACTION DEBUG: No alive targets found, ending combat")
                await self.end_combat(update, adventure_id, victory='enemies', context=context)
                return

            target = random.choice(targets)
            # Use stored AC from database for now to avoid hanging
            logger.info(f"COMBAT DEBUG: Getting AC for character {target['id']} ({target['name']})")
            
            # Get AC from character record
            ac_query = "SELECT armor_class FROM characters WHERE id = %s"
            ac_result = self.db.execute_query(ac_query, (target['id'],))
            
            if ac_result and ac_result[0]['armor_class'] is not None:
                target_ac = ac_result[0]['armor_class']
                logger.info(f"COMBAT DEBUG: Using stored AC for {target['name']}: {target_ac}")
            else:
                # Fallback: calculate simple AC (10 + DEX modifier)
                char_query = "SELECT dexterity FROM characters WHERE id = %s"
                char_result = self.db.execute_query(char_query, (target['id'],))
                if char_result:
                    dex_mod = (char_result[0]['dexterity'] - 10) // 2
                    target_ac = 10 + dex_mod
                    logger.info(f"COMBAT DEBUG: Calculated fallback AC for {target['name']}: 10 + {dex_mod} = {target_ac}")
                else:
                    target_ac = 10
                    logger.warning(f"COMBAT DEBUG: Using default AC 10 for {target['name']}")
            
            # Get enemy's attacks from database
            attacks_query = "SELECT name, damage, attack_bonus FROM enemy_attacks WHERE enemy_id = %s"
            enemy_attacks = self.db.execute_query(attacks_query, (enemy['id'],))
            
            if enemy_attacks:
                # Use random attack from the list
                attack = random.choice(enemy_attacks)
                attack_name = attack['name']
                attack_damage = attack['damage']
                attack_bonus = int(attack['attack_bonus']) if attack['attack_bonus'] else 0
                
                logger.info(f"COMBAT DEBUG: {enemy_name} using attack: {attack_name} ({attack_damage}, +{attack_bonus})")
            else:
                # Fallback to stored attack in enemies table
                attack_name = enemy.get('attack_name', 'Удар')
                attack_damage = enemy.get('attack_damage', '1d4')
                attack_bonus = int(enemy.get('attack_bonus', 0))
                
                logger.info(f"COMBAT DEBUG: {enemy_name} using fallback attack: {attack_name} ({attack_damage}, +{attack_bonus})")
            
            # Perform actual attack roll
            attack_roll_result, attack_breakdown = roll_d20(attack_bonus)
            raw_roll = attack_roll_result - attack_bonus  # Get the raw d20 roll
            
            result_text = f"⚔️ {enemy_name} атакует {target['name']} с помощью {attack_name}!\n"
            result_text += f"🎲 Бросок атаки: {attack_breakdown} против AC {target_ac}"
            
            # Check for critical hit/miss
            if is_critical_hit(raw_roll):
                result_text += f"\n🎯 КРИТИЧЕСКОЕ ПОПАДАНИЕ! (натуральная 20)"
                # Double damage dice on crit - roll twice and combine
                total1, rolls1, modifier1, _ = roll_dice_detailed(attack_damage)
                total2, rolls2, modifier2, _ = roll_dice_detailed(attack_damage)
                
                # Combine all rolls
                all_rolls = rolls1 + rolls2
                combined_modifier = modifier1  # Should be the same
                total_damage = sum(all_rolls) + combined_modifier
                
                # Create detailed breakdown
                if len(all_rolls) == 1:
                    if combined_modifier != 0:
                        damage_text = f"{all_rolls[0]} + {combined_modifier} = {total_damage}"
                    else:
                        damage_text = f"{all_rolls[0]} = {total_damage}"
                else:
                    rolls_str = " + ".join(map(str, all_rolls))
                    if combined_modifier != 0:
                        damage_text = f"{rolls_str} + {combined_modifier} = {total_damage}"
                    else:
                        damage_text = f"{rolls_str} = {total_damage}"
                        
                result_text += f"\n💥 Урон: {damage_text} урона"
                
                # Apply damage
                new_hp = max(0, target['current_hp'] - total_damage)
                self.db.execute_query("UPDATE characters SET current_hp = %s WHERE id = %s", 
                                      (new_hp, target['id']))
                result_text += f"\n❤️ {target['name']}: {target['current_hp']} → {new_hp} HP"
                
                # Учет полученного урона персонажем (кумулятивно по приключению)
                try:
                    dealt = target['current_hp'] - new_hp
                    if dealt > 0:
                        record_damage_taken(adventure_id, target['id'], dealt)
                except Exception as e:
                    logger.warning(f"COMBAT METRICS WARNING: record_damage_taken failed: {e}")
                
            elif is_critical_miss(raw_roll):
                result_text += f"\n💨 КРИТИЧЕСКИЙ ПРОМАХ! (натуральная 1)"
                
            elif attack_roll_result >= target_ac:
                result_text += f"\n✅ ПОПАДАНИЕ!"
                # Calculate damage
                damage_result, damage_breakdown = roll_dice(attack_damage)
                result_text += f"\n💥 Урон: {damage_breakdown} урона"
                
                # Apply damage
                new_hp = max(0, target['current_hp'] - damage_result)
                self.db.execute_query("UPDATE characters SET current_hp = %s WHERE id = %s", 
                                      (new_hp, target['id']))
                result_text += f"\n❤️ {target['name']}: {target['current_hp']} → {new_hp} HP"
                
                # Учет полученного урона персонажем (кумулятивно по приключению)
                try:
                    dealt = target['current_hp'] - new_hp
                    if dealt > 0:
                        record_damage_taken(adventure_id, target['id'], dealt)
                except Exception as e:
                    logger.warning(f"COMBAT METRICS WARNING: record_damage_taken failed: {e}")
                
                # Check if character is defeated
                if new_hp <= 0:
                    result_text += f"\n💀 {target['name']} потерял сознание!"
                    # Достижение за героическую смерть
                    user_query = "SELECT user_id FROM characters WHERE id = %s"
                    user_result = self.db.execute_query(user_query, (target['id'],))
                    if user_result and user_result[0]['user_id']:
                        ach = achievement_manager.grant_achievement(user_result[0]['user_id'], 'character_death', target['name'])
                    # Remove character from active group and make inactive
                    await self.remove_character_from_combat(target['id'], adventure_id)
                    
            else:
                result_text += f"\n❌ ПРОМАХ!"

            # Send result message using alternative method if update is invalid
            message_sent = False
            if update and hasattr(update, 'message') and update.message:
                try:
                    await update.message.reply_text(result_text)
                    message_sent = True
                except Exception as e:
                    logger.warning(f"ENEMY ACTION DEBUG: Failed to send via update.message: {e}")
            
            # Fallback to alternative sending method
            if not message_sent:
                logger.info(f"ENEMY ACTION DEBUG: Using alternative message sending for adventure {adventure_id}")
                await self.send_message_to_adventure(adventure_id, result_text, context)
            
            # Check if all characters are defeated
            alive_chars_query = ("SELECT COUNT(*) as count FROM characters c "
                                "JOIN adventure_participants ap ON c.id = ap.character_id "
                                "WHERE ap.adventure_id = %s AND c.current_hp > 0")
            alive_chars = self.db.execute_query(alive_chars_query, (adventure_id,))
            
            if alive_chars and alive_chars[0]['count'] == 0:
                await self.end_combat(update, adventure_id, victory='enemies', context=context)
                
        except Exception as e:
            logger.error(f"ENEMY ACTION DEBUG: Exception occurred: {e}")
            logger.exception("Full exception traceback:")

    async def end_combat(self, update_or_query, adventure_id: int, victory: str = None, context: ContextTypes.DEFAULT_TYPE = None):
        """End combat and declare outcome."""
        victory_msg = ""
        if victory == 'players':
            victory_msg = "🎊 Игроки победили в бою!"
        elif victory == 'enemies':
            victory_msg = "💀 Враги победили в бою..."
        else:
            victory_msg = "Бой завершен."
        
        logger.info(f"COMBAT END DEBUG: Ending combat with victory: {victory}")
        
        # Send victory message through adventure messaging system to avoid replacing previous messages
        victory_sent = False
        if context:
            victory_sent = await self.send_message_to_adventure(adventure_id, victory_msg, context)
            if victory_sent:
                logger.info("COMBAT END DEBUG: Victory message sent via adventure messaging system")
            else:
                logger.warning("COMBAT END DEBUG: Failed to send victory message via adventure messaging system")
        
        # Fallback for victory message if adventure messaging failed
        if not victory_sent and update_or_query is not None:
            try:
                if hasattr(update_or_query, 'message') and update_or_query.message is not None:
                    await update_or_query.message.reply_text(victory_msg)
                elif hasattr(update_or_query, 'callback_query') and update_or_query.callback_query:
                    # For callback queries, send a new message instead of editing
                    chat_id = update_or_query.callback_query.message.chat.id
                    if context and context.bot:
                        await context.bot.send_message(chat_id=chat_id, text=victory_msg)
                logger.info("COMBAT END DEBUG: Victory message sent via fallback method")
            except Exception as e:
                logger.warning(f"COMBAT END DEBUG: Failed to send victory message via fallback: {e}")

        # Get list of dead characters before clearing combat data
        dead_characters = []
        if victory == 'players':
            # Check for characters that died during combat (now inactive)
            dead_chars_query = (
                "SELECT c.name FROM characters c "
                "JOIN adventure_participants ap ON c.id = ap.character_id "
                "WHERE ap.adventure_id = %s AND c.current_hp <= 0 AND c.is_active = FALSE"
            )
            dead_chars_result = self.db.execute_query(dead_chars_query, (adventure_id,))
            if dead_chars_result:
                dead_characters = [char['name'] for char in dead_chars_result]
                logger.info(f"COMBAT END DEBUG: Found {len(dead_characters)} dead characters: {dead_characters}")
        
        # Выдаем достижения по итогам боя
        try:
            award_end_combat_achievements(adventure_id, victory)
        except Exception as e:
            logger.warning(f"ACHIEVEMENTS WARNING: awarding end-combat achievements failed: {e}")
        
        # Clear combat data
        self.db.execute_query("DELETE FROM combat_participants WHERE adventure_id = %s", (adventure_id,))

        # Update adventure status
        self.db.execute_query("UPDATE adventures SET status = 'active' WHERE id = %s", (adventure_id,))
        
        # Inform Grok and get continuation with dead characters info
        continuation_text = await asyncio.to_thread(
            grok.inform_combat_end, 
            adventure_id, 
            victory or "unknown", 
            dead_characters if dead_characters else None
        )
        
        # Clean response for players (remove any combat info if present)
        clean_continuation = grok.clean_response_for_players(continuation_text)
        
        # Send the continuation message FIRST as a separate message through adventure messaging system
        continuation_sent = False
        if context and clean_continuation.strip():
            continuation_sent = await self.send_message_to_adventure(adventure_id, clean_continuation, context)
            if continuation_sent:
                logger.info("COMBAT END DEBUG: Continuation message sent via adventure messaging system")
            else:
                logger.warning("COMBAT END DEBUG: Failed to send continuation message via adventure messaging system")
        
        # Parse XP reward from continuation text and award AFTER the story continuation
        xp_reward = grok.parse_xp_reward(continuation_text)
        if xp_reward > 0:
            logger.info(f"COMBAT END DEBUG: Found XP reward: {xp_reward}")
            # Award XP to all participants
            await self.award_experience_to_participants(adventure_id, xp_reward, context)
        
        # Check if adventure should end after combat
        if grok.is_adventure_ended(continuation_text):
            logger.info(f"COMBAT END DEBUG: Adventure end trigger detected after combat, ending adventure {adventure_id}")
            await self.end_adventure_after_combat(adventure_id, context)
        
        # Fallback for continuation message if adventure messaging failed
        if not continuation_sent and update_or_query is not None and clean_continuation.strip():
            try:
                if hasattr(update_or_query, 'message') and update_or_query.message is not None:
                    # Use send_long_message for proper handling of long texts
                    if context:
                        await send_long_message(update_or_query, context, clean_continuation)
                    else:
                        await update_or_query.message.reply_text(clean_continuation[:4000])
                elif hasattr(update_or_query, 'callback_query') and update_or_query.callback_query:
                    # For callback queries, send a new message instead of editing
                    chat_id = update_or_query.callback_query.message.chat.id
                    if context and context.bot:
                        # Split long messages if needed
                        if len(clean_continuation) > 4000:
                            chunks = [clean_continuation[i:i+4000] for i in range(0, len(clean_continuation), 4000)]
                            for chunk in chunks:
                                await context.bot.send_message(chat_id=chat_id, text=chunk)
                        else:
                            await context.bot.send_message(chat_id=chat_id, text=clean_continuation)
                logger.info("COMBAT END DEBUG: Continuation message sent via fallback method")
            except Exception as e:
                logger.warning(f"COMBAT END DEBUG: Failed to send continuation message via fallback: {e}")
    
    async def award_experience_to_participants(self, adventure_id: int, xp_amount: int, context: ContextTypes.DEFAULT_TYPE = None):
        """Award experience to all participants in the adventure"""
        if not self.db.connection or not self.db.connection.is_connected():
            self.db.connect()
        
        # Get all participants
        participants = self.db.execute_query("""
            SELECT c.id, c.name, c.experience, c.level, c.user_id
            FROM adventure_participants ap
            JOIN characters c ON ap.character_id = c.id
            WHERE ap.adventure_id = %s
        """, (adventure_id,))
        
        if not participants:
            logger.warning(f"COMBAT END DEBUG: No participants found for adventure {adventure_id}")
            return
        
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
            
            logger.info(f"COMBAT END DEBUG: {participant['name']}: {participant['experience']} + {xp_amount} = {new_xp} XP, level {old_level} -> {new_level}")
            
            if new_level > old_level:
                leveled_up.append(f"{participant['name']} достиг {new_level} уровня!")
                # Достижения за уровни для каждого достигнутого уровня
                try:
                    user_id = participant.get('user_id')
                    if user_id:
                        for lvl in range(old_level + 1, new_level + 1):
                            achievement_manager.check_level_achievement(user_id, lvl, participant['name'])
                except Exception as e:
                    logger.warning(f"ACHIEVEMENTS WARNING: level achievements failed for {participant['name']}: {e}")
        
        # Notify about XP and level ups
        xp_text = f"🌟 Участники получают {xp_amount} опыта!"
        if leveled_up:
            xp_text += "\n\n🎊 Повышения уровня:\n" + "\n".join(leveled_up)
        
        # Send XP notification through adventure messaging system
        if context:
            success = await self.send_message_to_adventure(adventure_id, xp_text, context)
            if success:
                logger.info("COMBAT END DEBUG: XP message sent via adventure messaging system")
            else:
                logger.warning("COMBAT END DEBUG: Failed to send XP message via adventure messaging system")
    
    def calculate_level_from_xp(self, xp: int) -> int:
        """Calculate character level from experience points"""
        if not self.db.connection or not self.db.connection.is_connected():
            self.db.connect()
        
        level_data = self.db.execute_query(
            "SELECT level FROM levels WHERE experience_required <= %s ORDER BY level DESC LIMIT 1",
            (xp,)
        )
        
        return level_data[0]['level'] if level_data else 1
    
    async def remove_character_from_combat(self, character_id: int, adventure_id: int):
        """Удаляет персонажа с 0 HP из активной группы и делает его неактивным"""
        if not self.db.connection or not self.db.connection.is_connected():
            self.db.connect()
        
        logger.info(f"COMBAT DEBUG: Removing character {character_id} from combat and making inactive")
        
        # Make character inactive
        self.db.execute_query(
            "UPDATE characters SET is_active = FALSE WHERE id = %s",
            (character_id,)
        )
        
        # Remove from adventure participants
        self.db.execute_query(
            "DELETE FROM adventure_participants WHERE character_id = %s AND adventure_id = %s",
            (character_id, adventure_id)
        )
        
        # Remove from combat participants (this will affect turn order)
        self.db.execute_query(
            "DELETE FROM combat_participants WHERE participant_id = %s AND participant_type = 'character' AND adventure_id = %s",
            (character_id, adventure_id)
        )
        
        logger.info(f"COMBAT DEBUG: Character {character_id} removed from combat and marked as inactive")
    
    async def end_adventure_after_combat(self, adventure_id: int, context: ContextTypes.DEFAULT_TYPE = None):
        """Завершает приключение после боя"""
        if not self.db.connection or not self.db.connection.is_connected():
            self.db.connect()
        
        logger.info(f"COMBAT END DEBUG: Ending adventure {adventure_id} after combat")
        
        # Update adventure status to finished
        self.db.execute_query(
            "UPDATE adventures SET status = 'finished' WHERE id = %s",
            (adventure_id,)
        )
        
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
        if context:
            success = await self.send_message_to_adventure(
                adventure_id,
                "🎆 Приключение завершено!\n\n"
                "Спасибо за игру! Для нового приключения используйте /start_adventure.",
                context
            )
            if success:
                logger.info("COMBAT END DEBUG: Adventure end message sent via adventure messaging system")
            else:
                logger.warning("COMBAT END DEBUG: Failed to send adventure end message via adventure messaging system")
        
        logger.info(f"COMBAT END DEBUG: Adventure {adventure_id} ended successfully after combat")

# Global Instance
combat_manager = CombatManager()
