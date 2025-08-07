import requests
import json
import logging
import re
from typing import List, Dict, Any, Tuple
from config import GROK_API_TOKEN, GROK_API_URL, GROK_MODEL
from database import get_db

logger = logging.getLogger(__name__)

class GrokAPI:
    def __init__(self):
        self.api_token = GROK_API_TOKEN
        self.api_url = GROK_API_URL
        self.model = GROK_MODEL
        self.db = get_db()
        self.headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json"
        }
        
        # System prompt для Grok
        self.system_prompt = """
        Ты - Данжен Мастер для игры в D&D 5e редакции 2024 года. Твоя задача - вести увлекательную игру для группы игроков.
        
        ВАЖНЫЕ ПРАВИЛА:
        
        1. НАЧАЛО СРАЖЕНИЯ: Если в ходе приключения начинается сражение, обязательно включи в свой ответ фразу "***COMBAT_START***". После этой фразы добавь блок с параметрами каждого противника в следующем формате:
        ```
        ENEMY: [Имя противника]
        HP: [Максимальные хиты]
        STR: [Сила] (мод: [модификатор])
        DEX: [Ловкость] (мод: [модификатор])
        CON: [Телосложение] (мод: [модификатор])
        INT: [Интеллект] (мод: [модификатор])
        WIS: [Мудрость] (мод: [модификатор])
        CHA: [Харизма] (мод: [модификатор])
        ATTACK: [Название атаки] ([урон], бонус к атаке: [бонус])
        XP: [Очки опыта за победу]
        ```
        
        2. НАГРАЖДЕНИЕ ОПЫТОМ: Если персонажи совершают важные свершения вне боя, включи в ответ фразу "***XP_REWARD: [количество опыта]***"
        
        3. КОНЕЦ ПРИКЛЮЧЕНИЯ: Если приключение завершено (игроки достигли цели, все игроки погибли, или ты считаешь, что история логично завершилась), обязательно включи в ответ фразу "***ADVENTURE_END***". Используй этот триггер в двух случаях:
           - После боя ты получил информацию о том, что сражение закончилось поражением всех игроков
           - Ты считаешь, что приключение завершено и игроки добились своей цели или история логично подошла к концу
        
        4. СТРУКТУРА ОТВЕТОВ: Всегда пиши захватывающие описания, создавай атмосферу фэнтези мира D&D.
        
        5. ПЕРСОНАЖИ: Помни информацию о персонажах и их способностях. Адаптируй приключения под состав группы.
        
        6. СМЕРТЬ ПЕРСОНАЖЕЙ: Если персонаж умирает в бою, больше не упоминай его в дальнейшем повествовании.
        
        7. НАВЫКИ И ЗАКЛИНАНИЯ: Если в запросе указано, что тот или иной персонаж использует навык или заклинание, считай, что у него оно всегда было.
        
        Создавай интересные приключения с загадками, ролевыми моментами, исследованием и боевыми столкновениями!
        Не заканчивай ответы предложением вариантов действий.
        """
    
    def send_request(self, messages: List[Dict[str, str]]) -> Dict[str, Any]:
        """Отправляет запрос к Grok API"""
        try:
            payload = {
                "model": self.model,
                "messages": messages,
                "temperature": 0.7,  # Slightly more focused responses
                "max_tokens": 2000,  # Increased token limit to reduce truncation
                "stream": False
            }
            
            logger.info(f"Sending request to Grok API: {self.api_url}")
            logger.info(f"Model: {self.model}")
            logger.info(f"Messages count: {len(messages)}")
            logger.info(f"Total characters in messages: {sum(len(msg['content']) for msg in messages)}")
            
            # Log full request content
            logger.info("=== FULL GROK REQUEST ===")
            for i, message in enumerate(messages):
                logger.info(f"Message {i+1} ({message['role']}):")
                logger.info(f"{message['content']}")
                logger.info("---")
            logger.info("=== END GROK REQUEST ===")
            
            # Try with longer timeout and session for connection reuse
            with requests.Session() as session:
                session.headers.update(self.headers)
                
                response = session.post(
                    self.api_url, 
                    json=payload,
                    timeout=(30, 180),  # connection timeout 30s, read timeout 3 minutes
                    stream=False
                )
                
                logger.info(f"Response status code: {response.status_code}")
                logger.info(f"Response headers: {dict(response.headers)}")
            
            if response.status_code == 200:
                result = response.json()
                logger.info(f"Successfully received response from Grok API")
                if 'choices' in result and len(result['choices']) > 0:
                    full_response = result['choices'][0]['message']['content']
                    content_length = len(full_response)
                    logger.info(f"Response content length: {content_length} characters")
                    logger.info(f"Full Grok response: {full_response}")
                return result
            else:
                logger.error(f"Grok API error: {response.status_code} - {response.text}")
                return None
                
        except requests.exceptions.Timeout as e:
            logger.error(f"Timeout error calling Grok API: {e}")
            logger.error(f"This might indicate the model is taking too long to respond")
            return None
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Connection error calling Grok API: {e}")
            logger.error(f"Check your internet connection and API URL: {self.api_url}")
            return None
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error calling Grok API: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error calling Grok API: {e}")
            logger.error(f"Error type: {type(e).__name__}")
            return None
    
    def get_conversation_history(self, adventure_id: int) -> List[Dict[str, str]]:
        """Получает историю разговора из базы данных"""
        if not self.db.connection or not self.db.connection.is_connected():
            self.db.connect()
            
        history = self.db.execute_query(
            "SELECT role, content FROM chat_history WHERE adventure_id = %s ORDER BY timestamp",
            (adventure_id,)
        )
        
        if not history:
            return []
        
        messages = []
        for entry in history:
            messages.append({
                "role": entry['role'],
                "content": entry['content']
            })
        
        return messages
    
    def save_message(self, adventure_id: int, role: str, content: str):
        """Сохраняет сообщение в историю разговора"""
        if not self.db.connection or not self.db.connection.is_connected():
            self.db.connect()
            
        logger.info(f"Saving message to database - Adventure ID: {adventure_id}, Role: {role}, Content length: {len(content)} characters")
        logger.debug(f"Message content being saved: {content[:500]}{'...' if len(content) > 500 else ''}")
        
        self.db.execute_query(
            "INSERT INTO chat_history (adventure_id, role, content) VALUES (%s, %s, %s)",
            (adventure_id, role, content)
        )
    
    def generate_adventure_intro(self, adventure_id: int, characters: List[Dict]) -> str:
        """Генерирует вступление к приключению"""
        logger.info(f"Starting adventure intro generation for adventure_id: {adventure_id}")
        character_info = []
        for char in characters:
            # Функция для вычисления модификатора характеристики
            def get_modifier(stat_value):
                return (stat_value - 10) // 2
            
            # Формируем детальную информацию о персонаже
            char_desc = f"- {char['name']} ({char['race_name']}, {char['class_name']}, {char['origin_name']})\n"
            char_desc += f"  Характеристики: Сила {char['strength']} ({get_modifier(char['strength']):+d}), "
            char_desc += f"Ловкость {char['dexterity']} ({get_modifier(char['dexterity']):+d}), "
            char_desc += f"Телосложение {char['constitution']} ({get_modifier(char['constitution']):+d}), "
            char_desc += f"Интеллект {char['intelligence']} ({get_modifier(char['intelligence']):+d}), "
            char_desc += f"Мудрость {char['wisdom']} ({get_modifier(char['wisdom']):+d}), "
            char_desc += f"Харизма {char['charisma']} ({get_modifier(char['charisma']):+d})\n"
            
            # Добавляем навыки
            if char.get('skills'):
                skills_text = ", ".join(char['skills'])
                char_desc += f"  Навыки: {skills_text}\n"
                
            # Добавляем заклинания
            if char.get('spells'):
                spells_by_level = {}
                for spell in char['spells']:
                    level = spell['level']
                    if level not in spells_by_level:
                        spells_by_level[level] = []
                    spells_by_level[level].append(spell['name'])
                
                char_desc += "  Заклинания:\n"
                for level in sorted(spells_by_level.keys()):
                    level_name = "Заговоры" if level == 0 else f"{level} уровень"
                    spells_list = ", ".join(spells_by_level[level])
                    char_desc += f"    {level_name}: {spells_list}\n"
            
            character_info.append(char_desc)
        
        characters_text = "\n".join(character_info)
        
        user_prompt = f"""
        Создай захватывающее вступление для D&D приключения для следующих персонажей:
        
        {characters_text}
        
        Приключение должно начинаться в фэнтези мире с элементами средневековья. 
        Создай интересный сюжетный крючок, который объединит всех персонажей и даст им общую цель.
        Опиши начальную локацию и ситуацию, в которой оказались персонажи.
        """
        
        # Создаем новую историю разговора
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        response = self.send_request(messages)
        
        if response and 'choices' in response:
            intro_text = response['choices'][0]['message']['content']
            
            logger.info(f"Generated intro text length: {len(intro_text)} characters")
            logger.info("FLOW: About to save messages to database in order: system, user, assistant")
            
            # Сохраняем в историю
            self.save_message(adventure_id, "system", self.system_prompt)
            self.save_message(adventure_id, "user", user_prompt)
            self.save_message(adventure_id, "assistant", intro_text)
            
            logger.info("FLOW: Finished saving messages to database, returning intro_text")
            return intro_text
        else:
            return "Произошла ошибка при генерации приключения. Попробуйте еще раз."
    
    def continue_adventure(self, adventure_id: int, player_actions: List[Dict[str, str]], 
                          additional_info: str = "") -> Tuple[str, List[Dict], int]:
        """
        Продолжает приключение на основе действий игроков
        Возвращает: (response_text, enemies_data, xp_reward)
        """
        # Получаем историю разговора
        messages = self.get_conversation_history(adventure_id)
        
        # Формируем текст с действиями игроков
        actions_text = "Действия игроков:\n"
        for action in player_actions:
            actions_text += f"- {action['character_name']}: {action['action']}\n"
        
        if additional_info:
            actions_text += f"\nДополнительная информация: {additional_info}"
        
        # Добавляем действия игроков к разговору
        messages.append({
            "role": "user", 
            "content": actions_text
        })
        
        # Отправляем запрос
        response = self.send_request(messages)
        
        if not response or 'choices' not in response:
            return "Произошла ошибка при обработке действий. Попробуйте еще раз.", [], 0
        
        response_text = response['choices'][0]['message']['content']
        
        logger.info(f"Generated continue adventure response length: {len(response_text)} characters")
        logger.info("FLOW: About to save messages to database in order: user, assistant")
        
        # Сохраняем в историю
        self.save_message(adventure_id, "user", actions_text)
        self.save_message(adventure_id, "assistant", response_text)
        
        logger.info("FLOW: Finished saving messages to database, returning response_text")
        
        # Анализируем ответ на предмет боя и опыта
        logger.info(f"COMBAT DEBUG: Checking response for combat triggers...")
        logger.info(f"COMBAT DEBUG: Response contains COMBAT_START: {'***COMBAT_START***' in response_text}")
        if "***COMBAT_START***" in response_text:
            logger.info(f"COMBAT DEBUG: Found COMBAT_START trigger in response!")
            combat_start_pos = response_text.find("***COMBAT_START***")
            logger.info(f"COMBAT DEBUG: COMBAT_START position: {combat_start_pos}")
            # Показываем часть текста вокруг триггера
            start_pos = max(0, combat_start_pos - 100)
            end_pos = min(len(response_text), combat_start_pos + 500)
            logger.info(f"COMBAT DEBUG: Text around COMBAT_START: ...{response_text[start_pos:end_pos]}...")
        else:
            logger.info(f"COMBAT DEBUG: No COMBAT_START trigger found in response")
        
        enemies_data = self.parse_enemies(response_text, adventure_id)
        xp_reward = self.parse_xp_reward(response_text)
        
        logger.info(f"COMBAT DEBUG: Parsed {len(enemies_data)} enemies from response")
        if enemies_data:
            for i, enemy in enumerate(enemies_data):
                logger.info(f"COMBAT DEBUG: Enemy {i+1}: {enemy['name']} (HP: {enemy['hit_points']})")
        
        return response_text, enemies_data, xp_reward
    
    def clean_response_for_players(self, text: str) -> str:
        """Убирает из ответа информацию о врагах и триггеры, которые игроки не должны видеть"""
        clean_text = text
        
        # Убираем триггеры опыта и окончания приключения
        import re
        clean_text = re.sub(r'\*\*\*XP_REWARD: \d+\*\*\*', '', clean_text)
        clean_text = re.sub(r'\*\*\*ADVENTURE_END\*\*\*', '', clean_text)
        
        # Убираем боевые блоки, если есть
        if "***COMBAT_START***" in clean_text:
            combat_start_index = clean_text.find("***COMBAT_START***")
            clean_text = clean_text[:combat_start_index].strip()
        
        return clean_text.strip()
    
    def parse_enemies(self, text: str, adventure_id: int) -> List[Dict]:
        """Парсит данные о врагах из ответа Grok"""
        logger.info(f"PARSE DEBUG: Starting enemy parsing...")
        if "***COMBAT_START***" not in text:
            logger.info(f"PARSE DEBUG: No COMBAT_START found, returning empty list")
            return []
        
        enemies = []
        
        # Получаем часть текста после COMBAT_START
        combat_start_pos = text.find("***COMBAT_START***")
        combat_text = text[combat_start_pos:]
        logger.info(f"PARSE DEBUG: Combat text length: {len(combat_text)} characters")
        logger.info(f"PARSE DEBUG: Combat text: {combat_text}")
        
        # Ищем блоки с противниками
        # Новый подход: парсим каждый блок врага отдельно
        enemy_blocks = re.split(r'(?=ENEMY:)', combat_text)[1:]  # Убираем первый пустой элемент
        logger.info(f"PARSE DEBUG: Found {len(enemy_blocks)} enemy blocks")
        
        for i, block in enumerate(enemy_blocks):
            logger.info(f"PARSE DEBUG: Processing enemy block {i+1}: {block[:200]}...")
            
            # Парсим основные характеристики врага
            enemy_match = re.search(r"ENEMY: (.+?)\nHP: (\d+)\nSTR: (\d+) \(мод: ([+-]?\d+)\)\nDEX: (\d+) \(мод: ([+-]?\d+)\)\nCON: (\d+) \(мод: ([+-]?\d+)\)\nINT: (\d+) \(мод: ([+-]?\d+)\)\nWIS: (\d+) \(мод: ([+-]?\d+)\)\nCHA: (\d+) \(мод: ([+-]?\d+)\)", block, re.DOTALL)
            
            if not enemy_match:
                logger.warning(f"PARSE DEBUG: Could not parse enemy stats from block {i+1}")
                continue
            
            # Парсим все атаки
            attack_matches = re.findall(r"ATTACK: (.+?) \((.+?), бонус к атаке: ([+-]?\d+)\)", block)
            logger.info(f"PARSE DEBUG: Found {len(attack_matches)} attacks for enemy {i+1}")
            
            # Парсим опыт
            xp_match = re.search(r"XP: (\d+)", block)
            if not xp_match:
                logger.warning(f"PARSE DEBUG: Could not parse XP from block {i+1}")
                continue
            
            enemy_data = {
                'name': enemy_match.group(1).strip(),
                'hit_points': int(enemy_match.group(2)),
                'max_hit_points': int(enemy_match.group(2)),
                'strength': int(enemy_match.group(3)),
                'dexterity': int(enemy_match.group(5)),
                'constitution': int(enemy_match.group(7)),
                'intelligence': int(enemy_match.group(9)),
                'wisdom': int(enemy_match.group(11)),
                'charisma': int(enemy_match.group(13)),
                'experience_reward': int(xp_match.group(1)),
                'armor_class': 12 + (int(enemy_match.group(6)) if int(enemy_match.group(6)) > 0 else 0)  # AC = 12 + DEX mod if positive
            }
            
            # Используем первую атаку для совместимости со старой схемой
            if attack_matches:
                enemy_data['attack_name'] = attack_matches[0][0].strip()
                enemy_data['attack_damage'] = attack_matches[0][1].strip()
                enemy_data['attack_bonus'] = int(attack_matches[0][2])
            else:
                enemy_data['attack_name'] = "Удар"
                enemy_data['attack_damage'] = "1d4"
                enemy_data['attack_bonus'] = 0
            
            logger.info(f"PARSE DEBUG: Enemy data: {enemy_data['name']} with {len(attack_matches)} attacks")
            
            # Сохраняем врага в базу данных
            if not self.db.connection or not self.db.connection.is_connected():
                self.db.connect()
                
            self.db.execute_query("""
                INSERT INTO enemies (adventure_id, name, hit_points, max_hit_points, 
                                   strength, dexterity, constitution, intelligence, wisdom, charisma,
                                   attack_name, attack_damage, attack_bonus, experience_reward, armor_class)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (adventure_id, enemy_data['name'], enemy_data['hit_points'], 
                  enemy_data['max_hit_points'], enemy_data['strength'], enemy_data['dexterity'],
                  enemy_data['constitution'], enemy_data['intelligence'], enemy_data['wisdom'],
                  enemy_data['charisma'], enemy_data['attack_name'], enemy_data['attack_damage'],
                  enemy_data['attack_bonus'], enemy_data['experience_reward'], enemy_data['armor_class']))
            
            # Получаем ID созданного врага
            enemy_id_result = self.db.execute_query("SELECT LAST_INSERT_ID() as id")
            if enemy_id_result:
                enemy_data['id'] = enemy_id_result[0]['id']
                
                # Сохраняем все атаки в отдельную таблицу
                for attack_name, attack_damage, attack_bonus in attack_matches:
                    self.db.execute_query(
                        "INSERT INTO enemy_attacks (enemy_id, name, damage, bonus) VALUES (%s, %s, %s, %s)",
                        (enemy_data['id'], attack_name.strip(), attack_damage.strip(), int(attack_bonus))
                    )
                    logger.info(f"PARSE DEBUG: Saved attack: {attack_name} ({attack_damage}, +{attack_bonus})")
            
            enemies.append(enemy_data)
        
        return enemies
    
    def parse_xp_reward(self, text: str) -> int:
        """Парсит награду опытом из ответа Grok"""
        xp_pattern = r"\*\*\*XP_REWARD: (\d+)\*\*\*"
        match = re.search(xp_pattern, text)
        
        if match:
            return int(match.group(1))
        
        return 0
    
    def is_adventure_ended(self, text: str) -> bool:
        """Проверяет, содержит ли текст триггер окончания приключения"""
        return "***ADVENTURE_END***" in text
    
    def inform_combat_end(self, adventure_id: int, combat_result: str, dead_characters: List[str] = None):
        """Информирует Grok об окончании боя"""
        messages = self.get_conversation_history(adventure_id)
        
        # Формируем развернутое сообщение в зависимости от результата
        if combat_result == "enemies":
            # Враги победили
            combat_info = (
                "Сражение завершилось поражением всех игроков. Враги победили. "
                "Опиши трагичное окончание приключения с поражением героев. "
                "После описания обязательно добавь триггер ***ADVENTURE_END***, "
                "чтобы официально завершить приключение."
            )
        elif combat_result == "players":
            if dead_characters:
                # Игроки победили, но есть потери
                dead_list = ", ".join(dead_characters)
                combat_info = (
                    f"Сражение завершилось победой игроков, но не без потерь! "
                    f"Погибшие персонажи (больше не упоминай их в дальнейшем повествовании): {dead_list}. "
                    "Опиши победу с оттенком горечи от потери спутников, "
                    "а затем продолжи приключение для оставшихся в живых персонажей."
                )
            else:
                # Полная победа без потерь
                combat_info = (
                    "Сражение завершилось полной победой игроков! Все персонажи остались живы. "
                    "Опиши их триумф и продолжи приключение."
                )
        else:
            # Неопределенный результат (например, ничья)
            combat_info = (
                f"Сражение завершилось с неопределенным результатом ({combat_result}). "
                "Опиши окончание боя и продолжи приключение."
            )
        
        messages.append({
            "role": "user",
            "content": combat_info
        })
        
        response = self.send_request(messages)
        
        if response and 'choices' in response:
            response_text = response['choices'][0]['message']['content']
            
            # Сохраняем в историю
            self.save_message(adventure_id, "user", combat_info)
            self.save_message(adventure_id, "assistant", response_text)
            
            return response_text
        
        return "Приключение продолжается..."

# Глобальный экземпляр
grok = GrokAPI()
