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
        
        3. СТРУКТУРА ОТВЕТОВ: Всегда пиши захватывающие описания, создавай атмосферу фэнтези мира D&D.
        
        4. ПЕРСОНАЖИ: Помни информацию о персонажах и их способностях. Адаптируй приключения под состав группы.
        
        5. СМЕРТЬ ПЕРСОНАЖЕЙ: Если персонаж умирает в бою, больше не упоминай его в дальнейшем повествовании.
        
        Создавай интересные приключения с загадками, ролевыми моментами, исследованием и боевыми столкновениями!
        """
    
    def send_request(self, messages: List[Dict[str, str]]) -> Dict[str, Any]:
        """Отправляет запрос к Grok API"""
        try:
            payload = {
                "model": self.model,
                "messages": messages,
                "temperature": 0.8,
                "max_tokens": 1500
            }
            
            response = requests.post(
                self.api_url, 
                headers=self.headers, 
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Grok API error: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Error calling Grok API: {e}")
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
            
        self.db.execute_query(
            "INSERT INTO chat_history (adventure_id, role, content) VALUES (%s, %s, %s)",
            (adventure_id, role, content)
        )
    
    def generate_adventure_intro(self, adventure_id: int, characters: List[Dict]) -> str:
        """Генерирует вступление к приключению"""
        character_info = []
        for char in characters:
            char_desc = f"- {char['name']} ({char['race']}, {char['class']}, {char['origin']})"
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
            
            # Сохраняем в историю
            self.save_message(adventure_id, "system", self.system_prompt)
            self.save_message(adventure_id, "user", user_prompt)
            self.save_message(adventure_id, "assistant", intro_text)
            
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
        
        # Сохраняем в историю
        self.save_message(adventure_id, "user", actions_text)
        self.save_message(adventure_id, "assistant", response_text)
        
        # Анализируем ответ на предмет боя и опыта
        enemies_data = self.parse_enemies(response_text, adventure_id)
        xp_reward = self.parse_xp_reward(response_text)
        
        return response_text, enemies_data, xp_reward
    
    def parse_enemies(self, text: str, adventure_id: int) -> List[Dict]:
        """Парсит данные о врагах из ответа Grok"""
        if "***COMBAT_START***" not in text:
            return []
        
        enemies = []
        
        # Ищем блоки с противниками
        enemy_pattern = r"ENEMY: (.+?)\nHP: (\d+)\nSTR: (\d+) \(мод: ([+-]?\d+)\)\nDEX: (\d+) \(мод: ([+-]?\d+)\)\nCON: (\d+) \(мод: ([+-]?\d+)\)\nINT: (\d+) \(мод: ([+-]?\d+)\)\nWIS: (\d+) \(мод: ([+-]?\d+)\)\nCHA: (\d+) \(мод: ([+-]?\d+)\)\nATTACK: (.+?) \((.+?), бонус к атаке: ([+-]?\d+)\)\nXP: (\d+)"
        
        matches = re.findall(enemy_pattern, text)
        
        for match in matches:
            enemy_data = {
                'name': match[0].strip(),
                'hit_points': int(match[1]),
                'max_hit_points': int(match[1]),
                'strength': int(match[2]),
                'dexterity': int(match[4]),
                'constitution': int(match[6]),
                'intelligence': int(match[8]),
                'wisdom': int(match[10]),
                'charisma': int(match[12]),
                'attack_name': match[14].strip(),
                'attack_damage': match[15].strip(),
                'attack_bonus': int(match[16]),
                'experience_reward': int(match[17])
            }
            
            # Сохраняем врага в базу данных
            if not self.db.connection or not self.db.connection.is_connected():
                self.db.connect()
                
            self.db.execute_query("""
                INSERT INTO enemies (adventure_id, name, hit_points, max_hit_points, 
                                   strength, dexterity, constitution, intelligence, wisdom, charisma,
                                   attack_name, attack_damage, attack_bonus, experience_reward)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (adventure_id, enemy_data['name'], enemy_data['hit_points'], 
                  enemy_data['max_hit_points'], enemy_data['strength'], enemy_data['dexterity'],
                  enemy_data['constitution'], enemy_data['intelligence'], enemy_data['wisdom'],
                  enemy_data['charisma'], enemy_data['attack_name'], enemy_data['attack_damage'],
                  enemy_data['attack_bonus'], enemy_data['experience_reward']))
            
            # Получаем ID созданного врага
            enemy_id_result = self.db.execute_query("SELECT LAST_INSERT_ID() as id")
            if enemy_id_result:
                enemy_data['id'] = enemy_id_result[0]['id']
            
            enemies.append(enemy_data)
        
        return enemies
    
    def parse_xp_reward(self, text: str) -> int:
        """Парсит награду опытом из ответа Grok"""
        xp_pattern = r"\*\*\*XP_REWARD: (\d+)\*\*\*"
        match = re.search(xp_pattern, text)
        
        if match:
            return int(match.group(1))
        
        return 0
    
    def inform_combat_end(self, adventure_id: int, combat_result: str, dead_characters: List[str] = None):
        """Информирует Grok об окончании боя"""
        messages = self.get_conversation_history(adventure_id)
        
        combat_info = f"Сражение завершено. Результат: {combat_result}"
        
        if dead_characters:
            combat_info += f" Погибшие персонажи (больше не упоминай их): {', '.join(dead_characters)}"
        
        combat_info += " Продолжи приключение."
        
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
