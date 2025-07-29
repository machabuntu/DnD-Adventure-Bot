import random
import json
import logging
from typing import Dict, List, Tuple, Optional
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import get_db

logger = logging.getLogger(__name__)

# Emoji для характеристик
STAT_EMOJIS = {
    'strength': '🐂',      # Бык - Сила
    'dexterity': '🐱',     # Кот - Ловкость  
    'constitution': '🐻',  # Медведь - Телосложение
    'intelligence': '🦊',  # Лиса - Интеллект
    'wisdom': '🦉',        # Сова - Мудрость
    'charisma': '🦅'       # Орёл - Харизма
}

# Названия характеристик на русском
STAT_NAMES = {
    'strength': 'Сила',
    'dexterity': 'Ловкость',
    'constitution': 'Телосложение', 
    'intelligence': 'Интеллект',
    'wisdom': 'Мудрость',
    'charisma': 'Харизма'
}

class CharacterGenerator:
    def __init__(self):
        self.db = get_db()
        
    def roll_stats(self) -> List[int]:
        """Генерирует характеристики персонажа (4d6, отбросить наименьший)"""
        stats = []
        for _ in range(6):
            rolls = [random.randint(1, 6) for _ in range(4)]
            rolls.sort(reverse=True)
            stat = sum(rolls[:3])  # Берем 3 наибольших
            stats.append(stat)
        return stats
    
    def get_modifier(self, stat: int) -> int:
        """Вычисляет модификатор характеристики"""
        return (stat - 10) // 2
    
    def format_character_info(self, char_data: dict) -> str:
        """Форматирует информацию о персонаже для отображения"""
        logger.info(f"Formatting character info for step: {char_data.get('step', 'unknown')}")
        
        # Базовые характеристики с emoji
        stats = char_data.get('stats', [])
        stat_names = ['strength', 'dexterity', 'constitution', 'intelligence', 'wisdom', 'charisma']
        
        # Применяем бонусы если есть
        final_stats = {}
        stat_adjustments = char_data.get('stat_adjustments', {})
        stat_mapping = {'str': 'strength', 'dex': 'dexterity', 'con': 'constitution', 
                       'int': 'intelligence', 'wis': 'wisdom', 'cha': 'charisma'}
        
        for i, stat_name in enumerate(stat_names):
            if i < len(stats):
                base_value = stats[i]
                # Применяем бонусы
                bonus = 0
                for stat_code, bonus_value in stat_adjustments.items():
                    if stat_code in stat_mapping and stat_mapping[stat_code] == stat_name:
                        bonus = bonus_value
                        break
                final_stats[stat_name] = base_value + bonus
            else:
                final_stats[stat_name] = 10
        
        # Форматируем характеристики вертикально
        stats_text = "\n📊 **Характеристики:**\n"
        for stat_name in stat_names:
            emoji = STAT_EMOJIS.get(stat_name, '❓')
            ru_name = STAT_NAMES.get(stat_name, stat_name)
            value = final_stats.get(stat_name, 10)
            modifier = self.get_modifier(value)
            bonus_text = ""
            
            # Показываем бонус если есть
            for stat_code, bonus_value in stat_adjustments.items():
                if stat_code in stat_mapping and stat_mapping[stat_code] == stat_name and bonus_value > 0:
                    base_value = value - bonus_value
                    bonus_text = f" ({base_value}+{bonus_value})"
                    break
            
            stats_text += f"{emoji} **{ru_name}:** {value}{bonus_text} ({modifier:+d})\n"
        
        # Добавляем информацию о персонаже
        info_text = "🎭 **Создание персонажа**\n\n"
        
        # Имя
        if char_data.get('name'):
            info_text += f"👤 **Имя:** {char_data['name']}\n"
        
        # Раса
        if char_data.get('race_id'):
            try:
                if not self.db.connection or not self.db.connection.is_connected():
                    self.db.connect()
                race_info = self.db.execute_query("SELECT name FROM races WHERE id = %s", (char_data['race_id'],))
                if race_info:
                    info_text += f"🧝‍♂️ **Раса:** {race_info[0]['name']}\n"
            except Exception as e:
                logger.error(f"Error getting race info: {e}")
        
        # Происхождение
        if char_data.get('origin_id'):
            try:
                origin_info = self.db.execute_query("SELECT name FROM origins WHERE id = %s", (char_data['origin_id'],))
                if origin_info:
                    info_text += f"🎭 **Происхождение:** {origin_info[0]['name']}\n"
            except Exception as e:
                logger.error(f"Error getting origin info: {e}")
        
        # Класс
        if char_data.get('class_id'):
            try:
                class_info = self.db.execute_query("SELECT name FROM classes WHERE id = %s", (char_data['class_id'],))
                if class_info:
                    info_text += f"⚔️ **Класс:** {class_info[0]['name']}\n"
            except Exception as e:
                logger.error(f"Error getting class info: {e}")
        
        # Навыки
        if char_data.get('selected_skills'):
            skills_text = ", ".join(char_data['selected_skills'])
            info_text += f"🎯 **Навыки:** {skills_text}\n"
        
        # Деньги
        if 'money' in char_data:
            info_text += f"💰 **Деньги:** {char_data['money']} монет\n"
        
        # Экипировка
        equipment_text = ""
        for equipment in char_data.get('equipment', []):
            if equipment['type'] == 'armor':
                armor_info = self.db.execute_query("SELECT name FROM armor WHERE id = %s", (equipment['id'],))
                if armor_info:
                    equipment_text += f"🛡️ **Доспехи:** {armor_info[0]['name']}\n"
            elif equipment['type'] == 'weapon':
                weapon_info = self.db.execute_query(
                    "SELECT name, damage, damage_type, properties FROM weapons WHERE id = %s", 
                    (equipment['id'],)
                )
                if weapon_info:
                    weapon = weapon_info[0]
                    equipment_text += f"⚔️ **Оружие:** {weapon['name']} ({weapon['damage']} {weapon['damage_type']})\n"
        
        if equipment_text:
            info_text += equipment_text
        
        # Дополнительная информация если есть класс
        if char_data.get('class_id'):
            try:
                # Получаем бонус мастерства из таблицы levels
                level_info = self.db.execute_query("SELECT proficiency_bonus FROM levels WHERE level = 1")
                proficiency_bonus = level_info[0]['proficiency_bonus'] if level_info else 2
                info_text += f"🎯 **Бонус мастерства:** +{proficiency_bonus}\n"
                
                # Класс доспехов
                armor_class = 10 + self.get_modifier(final_stats.get('dexterity', 10))
                armor_description = f"{armor_class}"
                
                # Проверяем наличие доспехов
                for equipment in char_data.get('equipment', []):
                    if equipment['type'] == 'armor':
                        armor_info = self.db.execute_query("SELECT armor_class, name FROM armor WHERE id = %s", (equipment['id'],))
                        if armor_info:
                            armor_base = armor_info[0]['armor_class']
                            armor_name = armor_info[0]['name']
                            
                            # Обрабатываем различные типы КД доспехов
                            if "+" in armor_base:
                                # Например: "11 + Лов" или "12 + Лов (макс 2)"
                                if "макс" in armor_base:
                                    # Средние доспехи с ограничением
                                    base_ac = int(armor_base.split()[0])
                                    max_dex = int(armor_base.split("макс ")[1].split(")")[0])
                                    dex_mod = min(self.get_modifier(final_stats.get('dexterity', 10)), max_dex)
                                    armor_class = base_ac + dex_mod
                                else:
                                    # Легкие доспехи
                                    base_ac = int(armor_base.split()[0])
                                    armor_class = base_ac + self.get_modifier(final_stats.get('dexterity', 10))
                            elif armor_base.startswith("+"):
                                # Щит: "+2"
                                armor_class += int(armor_base[1:])
                            else:
                                # Тяжелые доспехи: фиксированный КД
                                try:
                                    armor_class = int(armor_base)
                                except ValueError:
                                    # Если не удается преобразовать, используем базовый КД
                                    pass
                            
                            armor_description = f"{armor_class} ({armor_name})"
                            break
                
                info_text += f"🛡️ **КД:** {armor_description}\n"
                
                # Информация об атаке для финального отображения
                if char_data.get('step') == 'finalized':
                    for equipment in char_data.get('equipment', []):
                        if equipment['type'] == 'weapon':
                            weapon_info = self.db.execute_query(
                                "SELECT name, damage, damage_type, properties FROM weapons WHERE id = %s", 
                                (equipment['id'],)
                            )
                            if weapon_info:
                                weapon = weapon_info[0]
                                # Проверяем свойства оружия
                                try:
                                    properties = json.loads(weapon['properties']) if weapon['properties'] else []
                                except:
                                    properties = []
                                
                                # Определяем модификатор для атаки
                                str_mod = self.get_modifier(final_stats.get('strength', 10))
                                dex_mod = self.get_modifier(final_stats.get('dexterity', 10))
                                
                                # Если оружие фехтовальное, используем лучший модификатор
                                if "Фехтовальное" in properties:
                                    attack_mod = max(str_mod, dex_mod)
                                    damage_mod = max(str_mod, dex_mod)
                                else:
                                    # Для обычного оружия используем силу
                                    attack_mod = str_mod
                                    damage_mod = str_mod
                                
                                attack_bonus = attack_mod + proficiency_bonus
                                
                                # Формируем строку атаки с правильной обработкой урона
                                damage_str = str(weapon['damage'])
                                damage_type_str = str(weapon['damage_type'])
                                info_text += f"⚔️ **Атака ({weapon['name']}):** {attack_bonus:+d} к атаке, {damage_str}{damage_mod:+d} {damage_type_str}\n"
                    
                    # Заклинания для заклинателей
                    class_info = self.db.execute_query("SELECT is_spellcaster FROM classes WHERE id = %s", (char_data['class_id'],))
                    if class_info and class_info[0]['is_spellcaster']:
                        # Получаем заклинания персонажа из базы данных
                        if 'character_id' in char_data:
                            spells = self.db.execute_query("""
                                SELECT s.name, s.level 
                                FROM character_spells cs
                                JOIN spells s ON cs.spell_id = s.id
                                WHERE cs.character_id = %s
                                ORDER BY s.level, s.name
                            """, (char_data['character_id'],))
                            
                            if spells:
                                spells_by_level = {}
                                for spell in spells:
                                    level = spell['level']
                                    if level not in spells_by_level:
                                        spells_by_level[level] = []
                                    spells_by_level[level].append(spell['name'])
                                
                                info_text += "\n📜 **Заклинания:**\n"
                                for level in sorted(spells_by_level.keys()):
                                    level_name = "Заговоры" if level == 0 else f"{level} уровень"
                                    spells_list = ", ".join(spells_by_level[level])
                                    info_text += f"• {level_name}: {spells_list}\n"
                            
            except Exception as e:
                logger.error(f"Error getting additional character info: {e}")
        
        return info_text + "\n" + stats_text
    
    async def update_character_info_display(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обновляет отображение информации о персонаже"""
        logger.info("Updating character info display")
        
        char_data = context.user_data.get('character_generation')
        if not char_data:
            logger.warning("Character generation data not found")
            return
        
        try:
            character_info = self.format_character_info(char_data)
            
            # Если есть сохраненное сообщение, редактируем его
            if 'character_info_message_id' in char_data:
                try:
                    await context.bot.edit_message_text(
                        chat_id=update.effective_chat.id,
                        message_id=char_data['character_info_message_id'],
                        text=character_info,
                        parse_mode='Markdown'
                    )
                except Exception as edit_error:
                    logger.warning(f"Could not edit message, sending new one: {edit_error}")
                    # Если не удалось отредактировать, отправляем новое
                    message = await context.bot.send_message(
                        chat_id=update.effective_chat.id,
                        text=character_info,
                        parse_mode='Markdown'
                    )
                    char_data['character_info_message_id'] = message.message_id
            else:
                # Отправляем первое сообщение и сохраняем его ID
                message = await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=character_info,
                    parse_mode='Markdown'
                )
                char_data['character_info_message_id'] = message.message_id
                
        except Exception as e:
            logger.error(f"Error updating character info display: {e}")
    
    async def start_character_generation(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Начинает процесс создания персонажа"""
        user_id = update.effective_user.id
        logger.info(f"Starting character generation for user {user_id}")
        
        if not self.db.connection or not self.db.connection.is_connected():
            self.db.connect()
        
        # Проверяем, есть ли уже персонаж у игрока
        existing_char = self.db.execute_query(
            "SELECT id FROM characters WHERE user_id = %s AND is_active = TRUE",
            (user_id,)
        )
        
        if existing_char:
            logger.info(f"User {user_id} already has an active character")
            await update.message.reply_text(
                "У вас уже есть активный персонаж! Используйте /deletecharacter чтобы удалить его перед созданием нового.",
                parse_mode='HTML'
            )
            return
        
        # Генерируем характеристики
        stats = self.roll_stats()
        logger.info(f"Generated stats for user {user_id}: {stats}")
        
        # Сохраняем временные данные в context
        context.user_data['character_generation'] = {
            'step': 'name',
            'stats': stats,
            'assigned_stats': {},
            'name': '',
            'race_id': None,
            'origin_id': None,
            'class_id': None,
            'selected_skills': [],
            'equipment': [],
            'stat_adjustments': {}
        }
        
        char_data = context.user_data['character_generation']
        
        # Показываем характеристики с эмодзи вертикально
        await self.update_character_info_display(update, context)
        
        message = await update.message.reply_text("Пожалуйста, введите имя для вашего персонажа:", parse_mode='HTML')
        char_data['name_prompt_message_id'] = message.message_id
    
    async def handle_name_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обрабатывает ввод имени персонажа"""
        if 'character_generation' not in context.user_data:
            logger.warning("No character generation data found for name input")
            return
        
        char_data = context.user_data['character_generation']
        if char_data['step'] != 'name':
            logger.info(f"Wrong step for name input: {char_data['step']}")
            return
        
        name = update.message.text.strip()
        logger.info(f"User entered name: {name}")
        
        if len(name) < 2 or len(name) > 50:
            await update.message.reply_text("Имя должно содержать от 2 до 50 символов. Попробуйте еще раз:")
            return
        
        char_data['name'] = name
        char_data['step'] = 'race'
        logger.info(f"Character name set to: {name}, moving to race selection")
        
        # Удаляем сообщение с просьбой ввести имя
        if 'name_prompt_message_id' in char_data:
            try:
                await context.bot.delete_message(
                    chat_id=update.effective_chat.id,
                    message_id=char_data['name_prompt_message_id']
                )
            except Exception as delete_error:
                logger.warning(f"Could not delete name prompt message: {delete_error}")

        await self.show_race_selection(update, context)
    
    async def show_race_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показывает выбор расы"""
        logger.info("Showing race selection")
        
        if not self.db.connection or not self.db.connection.is_connected():
            self.db.connect()
        
        races = self.db.execute_query("SELECT id, name FROM races ORDER BY name")
        logger.info(f"Found {len(races)} races in database")
        
        keyboard = []
        for i in range(0, len(races), 2):
            row = []
            for j in range(2):
                if i + j < len(races):
                    race = races[i + j]
                    row.append(InlineKeyboardButton(race['name'], callback_data=f"race_{race['id']}"))
            keyboard.append(row)
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await self.update_character_info_display(update, context)
        
        text = "Выберите расу вашего персонажа:"
        
        char_data = context.user_data.get('character_generation')
        
        # Обновляем окно создания персонажа до финального состояния
        final_character_text = self.format_character_info(char_data)
        final_character_text = final_character_text.replace("🎭 **Создание персонажа**\n\n", "🎭 **Персонаж создан!**\n\n")
        
        # Обновляем окно создания персонажа с финальной информацией и кнопкой
        await context.bot.edit_message_text(
            chat_id=update.effective_chat.id,
            message_id=char_data['character_info_message_id'],
            text=final_character_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    async def handle_race_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обрабатывает выбор расы"""
        query = update.callback_query
        await query.answer()
        
        if 'character_generation' not in context.user_data:
            logger.warning("No character generation data found for race selection")
            return
        
        char_data = context.user_data['character_generation']
        if char_data['step'] != 'race':
            logger.warning(f"Wrong step for race selection: {char_data['step']}")
            return
        
        race_id = int(query.data.split('_')[1])
        char_data['race_id'] = race_id
        char_data['step'] = 'origin'
        
        # Получаем название расы для отображения
        if not self.db.connection or not self.db.connection.is_connected():
            self.db.connect()
        
        race_info = self.db.execute_query("SELECT name FROM races WHERE id = %s", (race_id,))
        race_name = race_info[0]['name'] if race_info else "Неизвестная раса"
        logger.info(f"User selected race: {race_name} (ID: {race_id})")

        # Удаляем окно выбора расы
        await query.delete_message()
        
        # Обновляем отображение информации о персонаже
        await self.update_character_info_display(update, context)
        
        await self.show_origin_selection(update, context)
    
    async def show_origin_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показывает выбор происхождения"""
        if not self.db.connection or not self.db.connection.is_connected():
            self.db.connect()
        
        origins = self.db.execute_query("SELECT id, name, stat_bonuses FROM origins ORDER BY name")
        
        # Мэппинг для кратких обозначений
        stat_short_names = {
            'str': 'СИЛ',
            'dex': 'ЛОВ', 
            'con': 'ТЕЛ',
            'int': 'ИНТ',
            'wis': 'МУД',
            'cha': 'ХАР'
        }
        
        keyboard = []
        for origin in origins:
            # Парсим бонусы характеристик
            try:
                stat_bonuses = json.loads(origin['stat_bonuses']) if origin['stat_bonuses'] else {}
                bonus_stats = [stat_short_names.get(stat, stat.upper()) for stat in stat_bonuses.keys()]
                bonus_text = f" ({'/'.join(bonus_stats)})" if bonus_stats else ""
            except:
                bonus_text = ""
            
            button_text = f"{origin['name']}{bonus_text}"
            keyboard.append([InlineKeyboardButton(button_text, callback_data=f"origin_{origin['id']}")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        char_data = context.user_data['character_generation']
        text = f"🎭 <b>{char_data['name']}</b>, выберите происхождение вашего персонажа:"
        
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=text,
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
    
    async def handle_origin_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обрабатывает выбор происхождения"""
        query = update.callback_query
        await query.answer()
        
        if 'character_generation' not in context.user_data:
            logger.warning("No character generation data found for origin selection")
            return
        
        char_data = context.user_data['character_generation']
        if char_data['step'] != 'origin':
            logger.warning(f"Wrong step for origin selection: {char_data['step']}")
            return
        
        origin_id = int(query.data.split('_')[1])
        char_data['origin_id'] = origin_id
        char_data['step'] = 'stat_assignment'
        
        # Получаем информацию о происхождении
        if not self.db.connection or not self.db.connection.is_connected():
            self.db.connect()
        
        origin_info = self.db.execute_query("SELECT name, stat_bonuses FROM origins WHERE id = %s", (origin_id,))
        origin_name = origin_info[0]['name'] if origin_info else "Неизвестное происхождение"
        logger.info(f"User selected origin: {origin_name} (ID: {origin_id})")
        
        # Удаляем окно выбора происхождения
        await query.delete_message()
        
        # Обновляем отображение информации о персонаже
        await self.update_character_info_display(update, context)
        
        await self.show_stat_assignment(update, context)
    
    async def show_stat_assignment(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показывает назначение характеристик"""
        char_data = context.user_data['character_generation']
        
        # Получаем бонусы происхождения
        if not self.db.connection or not self.db.connection.is_connected():
            self.db.connect()
        
        origin_info = self.db.execute_query("SELECT stat_bonuses FROM origins WHERE id = %s", (char_data['origin_id'],))
        stat_bonuses = json.loads(origin_info[0]['stat_bonuses']) if origin_info else {}
        
        # Показываем варианты распределения бонусов
        keyboard = [
            [InlineKeyboardButton("Вариант 1: +2 к одной, +1 к другой", callback_data="bonus_2_1")],
            [InlineKeyboardButton("Вариант 2: +1 к каждой из трех", callback_data="bonus_1_1_1")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        stats_list = ["Сила", "Ловкость", "Телосложение", "Интеллект", "Мудрость", "Харизма"]
        available_stats = [stat for stat in ["str", "dex", "con", "int", "wis", "cha"] if stat in stat_bonuses]
        available_names = [stats_list[["str", "dex", "con", "int", "wis", "cha"].index(stat)] for stat in available_stats]
        
        text = f"""
📊 <b>Распределение бонусов характеристик</b>

Ваше происхождение дает бонусы к: <b>{', '.join(available_names)}</b>

Выберите способ распределения:
        """
        
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=text,
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
    
    async def handle_stat_bonus_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обрабатывает выбор распределения бонусов"""
        query = update.callback_query
        await query.answer()
        
        char_data = context.user_data['character_generation']
        bonus_type = query.data.split('_', 1)[1]
        
        # Получаем доступные характеристики для бонусов
        if not self.db.connection or not self.db.connection.is_connected():
            self.db.connect()
        
        origin_info = self.db.execute_query("SELECT stat_bonuses FROM origins WHERE id = %s", (char_data['origin_id'],))
        stat_bonuses = json.loads(origin_info[0]['stat_bonuses']) if origin_info else {}
        available_stats = list(stat_bonuses.keys())
        
        logger.info(f"User selected bonus type: {bonus_type}, available stats: {available_stats}")
        
        char_data['bonus_type'] = bonus_type
        char_data['available_stats'] = available_stats
        
        if bonus_type == "2_1" and len(available_stats) >= 2:
            char_data['step'] = 'select_bonus_stat'
            stat_mapping = {'str': 'strength', 'dex': 'dexterity', 'con': 'constitution', 
                           'int': 'intelligence', 'wis': 'wisdom', 'cha': 'charisma'}
            stats_list = [STAT_NAMES.get(stat_mapping[s], s) for s in available_stats]
            text = f"Выберите одну характеристику для +2: {'/'.join(stats_list)}"
            keyboard = [[InlineKeyboardButton(stat, callback_data=f"select_bonus_2_{s}")] for s, stat in zip(available_stats, stats_list)]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(text=text, reply_markup=reply_markup)
            return
        elif bonus_type == "1_1_1" and len(available_stats) >= 3:
            char_data['stat_adjustments'] = {stat: 1 for stat in available_stats[:3]}
            # Удаляем окно распределения бонусов
            await query.delete_message()
            await self.show_class_selection(update, context)
        else:
            char_data['stat_adjustments'] = {}
            # Удаляем окно распределения бонусов
            await query.delete_message()
            await self.show_class_selection(update, context)
    
    async def handle_bonus_stat_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обрабатывает выбор характеристик для бонусов"""
        query = update.callback_query
        await query.answer()
        
        logger.info(f"Handling bonus stat selection: {query.data}")
        
        char_data = context.user_data['character_generation']
        stat_choice = query.data.split('_')[-1]
        current_bonus_type = len(char_data.get('stat_adjustments', {}))
        
        logger.info(f"Stat choice: {stat_choice}, current bonus count: {current_bonus_type}")
        
        if current_bonus_type == 0:  # Если выбираем +2
            char_data['stat_adjustments'] = {stat_choice: 2}
            char_data['available_stats'].remove(stat_choice)
            # Показываем выбор для +1
            stat_mapping = {'str': 'strength', 'dex': 'dexterity', 'con': 'constitution', 
                           'int': 'intelligence', 'wis': 'wisdom', 'cha': 'charisma'}
            stats_list = [STAT_NAMES.get(stat_mapping[s], s) for s in char_data['available_stats']]
            text = "Выберите одну характеристику для +1: " + '/'.join(stats_list)
            keyboard = [[InlineKeyboardButton(stat, callback_data=f"select_bonus_1_{s}")] for s, stat in zip(char_data['available_stats'], stats_list)]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(text=text, reply_markup=reply_markup)
            return
        else:  # Если выбираем +1
            char_data['stat_adjustments'][stat_choice] = 1
            
            # Удаляем окно распределения бонусов
            await query.delete_message()
            
            await self.show_class_selection(update, context)

    async def show_class_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показывает выбор класса"""
        if not self.db.connection or not self.db.connection.is_connected():
            self.db.connect()
        
        await self.update_character_info_display(update, context)

        classes = self.db.execute_query("SELECT id, name FROM classes ORDER BY name")
        
        keyboard = []
        for i in range(0, len(classes), 2):
            row = []
            for j in range(2):
                if i + j < len(classes):
                    cls = classes[i + j]
                    row.append(InlineKeyboardButton(cls['name'], callback_data=f"class_{cls['id']}"))
            keyboard.append(row)
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        char_data = context.user_data['character_generation']
        text = f"⚔️ <b>{char_data['name']}</b>, выберите класс вашего персонажа:"
        
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=text,
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
    
    async def handle_class_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обрабатывает выбор класса"""
        query = update.callback_query
        await query.answer()
        
        char_data = context.user_data['character_generation']
        class_id = int(query.data.split('_')[1])
        char_data['class_id'] = class_id
        char_data['step'] = 'skills'
        
        # Получаем информацию о классе
        if not self.db.connection or not self.db.connection.is_connected():
            self.db.connect()
        
        class_info = self.db.execute_query("SELECT name FROM classes WHERE id = %s", (class_id,))
        class_name = class_info[0]['name'] if class_info else "Неизвестный класс"
        logger.info(f"User selected class: {class_name} (ID: {class_id})")
        
        # Удаляем окно выбора класса
        await query.delete_message()
        
        # Обновляем отображение информации о персонаже
        await self.update_character_info_display(update, context)
        
        await self.show_skill_selection(update, context)
    
    async def show_skill_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показывает выбор навыков"""
        char_data = context.user_data['character_generation']
        
        if not self.db.connection or not self.db.connection.is_connected():
            self.db.connect()
        
        class_info = self.db.execute_query(
            "SELECT skills_available, skills_count FROM classes WHERE id = %s", 
            (char_data['class_id'],)
        )
        
        if not class_info:
            return
        
        available_skills = json.loads(class_info[0]['skills_available'])
        skills_count = class_info[0]['skills_count']
        
        char_data['available_skills'] = available_skills
        char_data['skills_count'] = skills_count
        char_data['selected_skills'] = []
        
        await self.update_skill_selection(update, context)
    
    async def update_skill_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обновляет интерфейс выбора навыков"""
        char_data = context.user_data['character_generation']
        available_skills = char_data['available_skills']
        selected_skills = char_data['selected_skills']
        skills_count = char_data['skills_count']
        
        if len(selected_skills) >= skills_count:
            char_data['step'] = 'equipment'
            await self.show_equipment_selection(update, context)
            return
        
        # Показываем доступные навыки
        keyboard = []
        for skill in available_skills:
            if skill not in selected_skills and skill != "любые три":
                keyboard.append([InlineKeyboardButton(skill, callback_data=f"skill_{skill}")])
        
        if keyboard:
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            text = f"""
🎯 <b>Выбор навыков</b>

Выбрано: {len(selected_skills)}/{skills_count}
Уже выбранные: {', '.join(selected_skills) if selected_skills else 'нет'}

Выберите навык:
            """
            
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=text,
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
    
    async def handle_skill_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обрабатывает выбор навыка"""
        query = update.callback_query
        await query.answer()
        
        char_data = context.user_data['character_generation']
        skill = query.data.split('_', 1)[1]
        
        char_data['selected_skills'].append(skill)
        logger.info(f"User selected skill: {skill}")
        
        # Обновляем отображение информации о персонаже
        await self.update_character_info_display(update, context)
        
        # Удаляем окно выбора навыков
        await query.delete_message()
        await self.update_skill_selection(update, context)
    
    async def show_equipment_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показывает выбор экипировки"""
        char_data = context.user_data['character_generation']
        
        if not self.db.connection or not self.db.connection.is_connected():
            self.db.connect()
        
        # Получаем стартовые деньги из класса и происхождения
        class_info = self.db.execute_query("SELECT starting_money FROM classes WHERE id = %s", (char_data['class_id'],))
        origin_info = self.db.execute_query("SELECT starting_money FROM origins WHERE id = %s", (char_data['origin_id'],))
        
        starting_money = (class_info[0]['starting_money'] if class_info else 0) + \
                        (origin_info[0]['starting_money'] if origin_info else 0)
        
        char_data['money'] = starting_money
        char_data['step'] = 'armor'
        
        await self.show_armor_selection(update, context)
    
    def can_use_armor(self, armor_type: str, armor_proficiency: list) -> bool:
        """Проверяет, может ли персонаж использовать доспех"""
        if not armor_proficiency:
            return False
        
        # Проверяем специальные случаи
        if "все" in armor_proficiency:
            return True
        
        # Проверяем конкретный тип доспеха
        if armor_type in ["легкий", "средний", "тяжелый", "щит"]:
            return armor_type in [prof.replace("ие", "ий").replace("ие", "ий") for prof in armor_proficiency]
        
        return False
    
    async def show_armor_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показывает выбор доспехов"""
        char_data = context.user_data['character_generation']
        
        if not self.db.connection or not self.db.connection.is_connected():
            self.db.connect()
        
        # Получаем владение доспехами класса
        class_info = self.db.execute_query("SELECT armor_proficiency FROM classes WHERE id = %s", (char_data['class_id'],))
        armor_prof = json.loads(class_info[0]['armor_proficiency']) if class_info else []
        
        # Получаем доступные доспехи
        armor_query = "SELECT id, name, price, armor_class, armor_type FROM armor WHERE price <= %s"
        available_armor = self.db.execute_query(armor_query, (char_data['money'],))
        
        keyboard = []
        keyboard.append([InlineKeyboardButton("Не покупать доспехи", callback_data="armor_none")])
        
        for armor in available_armor:
            # Правильная проверка владения
            if self.can_use_armor(armor['armor_type'], armor_prof):
                keyboard.append([InlineKeyboardButton(
                    f"{armor['name']} - {armor['price']} монет (КД: {armor['armor_class']})", 
                    callback_data=f"armor_{armor['id']}"
                )])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        text = f"""
🛡️ <b>Выбор доспехов</b>

Доступно монет: <b>{char_data['money']}</b>
Выберите доспехи:
        """
        
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=text,
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
    
    async def handle_armor_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обрабатывает выбор доспехов"""
        query = update.callback_query
        await query.answer()
        
        char_data = context.user_data['character_generation']
        
        if query.data == "armor_none":
            logger.info("User chose no armor")
            await query.delete_message()
        else:
            armor_id = int(query.data.split('_')[1])
            
            if not self.db.connection or not self.db.connection.is_connected():
                self.db.connect()
            
            armor_info = self.db.execute_query("SELECT name, price FROM armor WHERE id = %s", (armor_id,))
            if armor_info:
                armor = armor_info[0]
                char_data['money'] -= armor['price']
                char_data['equipment'].append({'type': 'armor', 'id': armor_id})
                logger.info(f"User bought armor: {armor['name']} for {armor['price']} coins")
                
                await query.delete_message()
        
        # Обновляем отображение информации о персонаже
        await self.update_character_info_display(update, context)
        
        char_data['step'] = 'weapon'
        await self.show_weapon_selection(update, context)
    
    def can_use_weapon(self, weapon_name: str, weapon_type: str, weapon_properties: str, weapon_proficiency: list) -> bool:
        """Проверяет, может ли персонаж использовать оружие"""
        if not weapon_proficiency:
            return False
        
        # Парсим свойства оружия
        try:
            properties = json.loads(weapon_properties) if weapon_properties else []
        except:
            properties = []
        
        # Проверяем каждое владение
        for prof in weapon_proficiency:
            # Простое и воинское оружие
            if prof == "простое" and weapon_type == "Простое":
                return True
            if prof == "воинское" and weapon_type == "Воинское":
                return True
            
            # Специальные случаи
            if "короткие мечи" in prof and weapon_name == "Короткий меч":
                return True
            
            # Плут - воинское со свойством фехтовальное или легкое
            if "воинское со свойством фехтовальное или легкое" in prof:
                if weapon_type == "Воинское" and ("Фехтовальное" in properties or "Лёгкое" in properties):
                    return True
        
        return False
    
    async def show_weapon_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показывает выбор оружия"""
        char_data = context.user_data['character_generation']
        
        if not self.db.connection or not self.db.connection.is_connected():
            self.db.connect()
        
        # Получаем владение оружием класса
        class_info = self.db.execute_query("SELECT weapon_proficiency FROM classes WHERE id = %s", (char_data['class_id'],))
        weapon_prof = json.loads(class_info[0]['weapon_proficiency']) if class_info else []
        
        # Получаем доступное оружие
        weapon_query = "SELECT id, name, price, damage, damage_type, weapon_type, properties FROM weapons WHERE price <= %s"
        available_weapons = self.db.execute_query(weapon_query, (char_data['money'],))
        
        keyboard = []
        keyboard.append([InlineKeyboardButton("Закончить покупки", callback_data="weapon_done")])
        
        for weapon in available_weapons:
            # Правильная проверка владения
            if self.can_use_weapon(weapon['name'], weapon['weapon_type'], weapon['properties'], weapon_prof):
                keyboard.append([InlineKeyboardButton(
                    f"{weapon['name']} - {weapon['price']} монет ({weapon['damage']} {weapon['damage_type']})", 
                    callback_data=f"weapon_{weapon['id']}"
                )])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        text = f"""
⚔️ <b>Выбор оружия</b>

Доступно монет: <b>{char_data['money']}</b>
Выберите оружие:
        """
        
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=text,
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
    
    async def handle_weapon_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обрабатывает выбор оружия"""
        query = update.callback_query
        await query.answer()
        
        char_data = context.user_data['character_generation']
        
        if query.data == "weapon_done":
            logger.info("User finished equipment purchase")
            # Удаляем окно выбора оружия
            await query.delete_message()
            await self.finalize_character(update, context)
        else:
            weapon_id = int(query.data.split('_')[1])
            
            if not self.db.connection or not self.db.connection.is_connected():
                self.db.connect()
            
            weapon_info = self.db.execute_query("SELECT name, price FROM weapons WHERE id = %s", (weapon_id,))
            if weapon_info:
                weapon = weapon_info[0]
                if char_data['money'] >= weapon['price']:
                    char_data['money'] -= weapon['price']
                    char_data['equipment'].append({'type': 'weapon', 'id': weapon_id})
                    logger.info(f"User bought weapon: {weapon['name']} for {weapon['price']} coins")
                    
                    # Обновляем отображение информации о персонаже
                    await self.update_character_info_display(update, context)
                    
                    await query.delete_message()
                    await self.show_weapon_selection(update, context)
                else:
                    await query.answer("Недостаточно денег!", show_alert=True)
    
    async def finalize_character(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Завершает создание персонажа"""
        char_data = context.user_data['character_generation']
        user_id = update.effective_user.id
        
        if not self.db.connection or not self.db.connection.is_connected():
            self.db.connect()
        
        # Назначаем характеристики
        stats = char_data['stats']
        stat_names = ['strength', 'dexterity', 'constitution', 'intelligence', 'wisdom', 'charisma']
        final_stats = {}
        
        # Применяем базовые значения
        for i, stat_name in enumerate(stat_names):
            final_stats[stat_name] = stats[i]
        
        # Применяем бонусы происхождения
        stat_adjustments = char_data.get('stat_adjustments', {})
        for stat_code, bonus in stat_adjustments.items():
            stat_mapping = {'str': 'strength', 'dex': 'dexterity', 'con': 'constitution', 
                          'int': 'intelligence', 'wis': 'wisdom', 'cha': 'charisma'}
            if stat_code in stat_mapping:
                final_stats[stat_mapping[stat_code]] += bonus
        
        # Вычисляем хиты
        class_info = self.db.execute_query("SELECT hit_die FROM classes WHERE id = %s", (char_data['class_id'],))
        hit_die = class_info[0]['hit_die'] if class_info else 8
        con_modifier = self.get_modifier(final_stats['constitution'])
        max_hp = hit_die + con_modifier
        
        # Создаем персонажа в базе данных
        character_id = self.db.execute_query("""
            INSERT INTO characters (user_id, name, race_id, origin_id, class_id, level, experience,
                                  strength, dexterity, constitution, intelligence, wisdom, charisma,
                                  hit_points, max_hit_points, money)
            VALUES (%s, %s, %s, %s, %s, 1, 0, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (user_id, char_data['name'], char_data['race_id'], char_data['origin_id'], char_data['class_id'],
              final_stats['strength'], final_stats['dexterity'], final_stats['constitution'],
              final_stats['intelligence'], final_stats['wisdom'], final_stats['charisma'],
              max_hp, max_hp, char_data['money']))
        
        if character_id:
            # Получаем ID созданного персонажа
            char_id_result = self.db.execute_query("SELECT LAST_INSERT_ID() as id")
            if char_id_result:
                character_id = char_id_result[0]['id']
                
                # Добавляем экипировку
                for equipment in char_data['equipment']:
                    self.db.execute_query(
                        "INSERT INTO character_equipment (character_id, item_type, item_id, is_equipped) VALUES (%s, %s, %s, TRUE)",
                        (character_id, equipment['type'], equipment['id'])
                    )
                
                # Добавляем заклинания если класс заклинатель
                class_info = self.db.execute_query("SELECT is_spellcaster FROM classes WHERE id = %s", (char_data['class_id'],))
                if class_info and class_info[0]['is_spellcaster']:
                    # Даем 2 случайных заклинания 0-1 уровня
                    spells = self.db.execute_query("SELECT id FROM spells WHERE level <= 1 ORDER BY RAND() LIMIT 2")
                    for spell in spells:
                        self.db.execute_query(
                            "INSERT INTO character_spells (character_id, spell_id) VALUES (%s, %s)",
                            (character_id, spell['id'])
                        )
        
        # Устанавливаем финальное состояние для отображения полной информации
        char_data['step'] = 'finalized'
        char_data['character_id'] = character_id
        
        # Обновляем окно создания персонажа до финального состояния
        final_character_text = self.format_character_info(char_data)
        final_character_text = final_character_text.replace("🎭 **Создание персонажа**\n\n", "🎭 **Персонаж создан!**\n\n")
        
        # Добавляем кнопку присоединения к группе
        keyboard = [[InlineKeyboardButton("Вступить в группу", callback_data="join_group")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Обновляем окно создания персонажа с финальной информацией и кнопкой
        await context.bot.edit_message_text(
            chat_id=update.effective_chat.id,
            message_id=char_data['character_info_message_id'],
            text=final_character_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        
        # Очищаем временные данные
        del context.user_data['character_generation']
    
    async def show_final_character(self, update: Update, context: ContextTypes.DEFAULT_TYPE, character_id: int):
        """Показывает финальную информацию о созданном персонаже"""
        if not self.db.connection or not self.db.connection.is_connected():
            self.db.connect()
        
        # Получаем полную информацию о персонаже
        char_info = self.db.execute_query("""
            SELECT c.*, r.name as race_name, o.name as origin_name, cl.name as class_name
            FROM characters c
            LEFT JOIN races r ON c.race_id = r.id
            LEFT JOIN origins o ON c.origin_id = o.id
            LEFT JOIN classes cl ON c.class_id = cl.id
            WHERE c.id = %s
        """, (character_id,))
        
        if not char_info:
            return
        
        char = char_info[0]
        
        text = f"""
🎭 <b>Персонаж создан!</b>

👤 <b>Имя:</b> {char['name']}
🧝‍♂️ <b>Раса:</b> {char['race_name']}
🎭 <b>Происхождение:</b> {char['origin_name']}
⚔️ <b>Класс:</b> {char['class_name']}
📊 <b>Уровень:</b> {char['level']}

<b>Характеристики:</b>
💪 Сила: {char['strength']} ({self.get_modifier(char['strength']):+d})
🏃 Ловкость: {char['dexterity']} ({self.get_modifier(char['dexterity']):+d})
🛡️ Телосложение: {char['constitution']} ({self.get_modifier(char['constitution']):+d})
🧠 Интеллект: {char['intelligence']} ({self.get_modifier(char['intelligence']):+d})
👁️ Мудрость: {char['wisdom']} ({self.get_modifier(char['wisdom']):+d})
💬 Харизма: {char['charisma']} ({self.get_modifier(char['charisma']):+d})

❤️ <b>Хиты:</b> {char['hit_points']}/{char['max_hit_points']}
💰 <b>Монеты:</b> {char['money']}
        """
        
        # Добавляем кнопку присоединения к группе
        keyboard = [[InlineKeyboardButton("Вступить в группу", callback_data="join_group")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=text,
            reply_markup=reply_markup,
            parse_mode='HTML'
        )

# Глобальный экземпляр
character_gen = CharacterGenerator()
