#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Модуль управления системой достижений для пользователей.
"""

import logging
from typing import List, Dict, Optional, Tuple
from datetime import datetime
import mysql.connector
from config import DB_HOST, DB_USER, DB_PASSWORD, DB_NAME

logger = logging.getLogger(__name__)

class AchievementManager:
    """Менеджер для работы с системой достижений."""
    
    def __init__(self):
        """Инициализация менеджера достижений."""
        self.db_config = {
            'host': DB_HOST,
            'user': DB_USER,
            'password': DB_PASSWORD,
            'database': DB_NAME,
            'charset': 'utf8mb4',
            'collation': 'utf8mb4_unicode_ci'
        }
    
    def _get_connection(self):
        """Создает новое подключение к базе данных."""
        return mysql.connector.connect(**self.db_config)
    
    def get_achievement_by_code(self, code: str) -> Optional[Dict]:
        """Получает достижение по его коду."""
        conn = self._get_connection()
        cursor = conn.cursor(dictionary=True)
        
        try:
            query = "SELECT * FROM achievements WHERE code = %s"
            cursor.execute(query, (code,))
            result = cursor.fetchone()
            return result
        finally:
            cursor.close()
            conn.close()
    
    def get_user_achievements(self, user_id: int) -> List[Dict]:
        """Получает список достижений пользователя."""
        conn = self._get_connection()
        cursor = conn.cursor(dictionary=True)
        
        try:
            query = """
                SELECT a.*, ua.achieved_at, ua.character_name, ua.details
                FROM achievements a
                JOIN user_achievements ua ON a.id = ua.achievement_id
                WHERE ua.user_id = %s
                ORDER BY ua.achieved_at DESC
            """
            cursor.execute(query, (user_id,))
            return cursor.fetchall()
        finally:
            cursor.close()
            conn.close()
    
    def has_achievement(self, user_id: int, code: str) -> bool:
        """Проверяет, есть ли у пользователя достижение."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            query = """
                SELECT COUNT(*) FROM user_achievements ua
                JOIN achievements a ON ua.achievement_id = a.id
                WHERE ua.user_id = %s AND a.code = %s
            """
            cursor.execute(query, (user_id, code))
            count = cursor.fetchone()[0]
            return count > 0
        finally:
            cursor.close()
            conn.close()
    
    def grant_achievement(self, user_id: int, code: str, character_name: str = None, details: str = None) -> Optional[Dict]:
        """
        Выдает достижение пользователю.
        Возвращает информацию о достижении, если оно было выдано, иначе None.
        """
        conn = self._get_connection()
        cursor = conn.cursor(dictionary=True)
        
        try:
            # Проверяем, существует ли достижение
            achievement = self.get_achievement_by_code(code)
            if not achievement:
                logger.error(f"Достижение с кодом {code} не найдено")
                return None
            
            # Проверяем, не получено ли уже достижение
            if self.has_achievement(user_id, code):
                logger.info(f"Пользователь {user_id} уже имеет достижение {code}")
                return None
            
            # Выдаем достижение
            query = """
                INSERT INTO user_achievements (user_id, achievement_id, character_name, details)
                VALUES (%s, %s, %s, %s)
            """
            cursor.execute(query, (user_id, achievement['id'], character_name, details))
            conn.commit()
            
            logger.info(f"Пользователю {user_id} выдано достижение: {achievement['name']}")
            return achievement
            
        except mysql.connector.IntegrityError:
            # Достижение уже есть (race condition)
            return None
        except Exception as e:
            logger.error(f"Ошибка при выдаче достижения: {e}")
            conn.rollback()
            return None
        finally:
            cursor.close()
            conn.close()
    
    def get_user_achievement_summary(self, user_id: int) -> Dict:
        """Получает сводку по достижениям пользователя."""
        conn = self._get_connection()
        cursor = conn.cursor(dictionary=True)
        
        try:
            # Получаем достижения пользователя
            achievements = self.get_user_achievements(user_id)
            
            # Считаем общие очки
            total_points = sum(a['points'] for a in achievements)
            
            # Получаем общее количество достижений
            cursor.execute("SELECT COUNT(*) as total FROM achievements WHERE is_hidden = FALSE")
            total_visible = cursor.fetchone()['total']
            
            cursor.execute("SELECT COUNT(*) as total FROM achievements")
            total_all = cursor.fetchone()['total']
            
            # Группируем по категориям
            categories = {}
            for achievement in achievements:
                cat = achievement.get('category', 'other')
                if cat not in categories:
                    categories[cat] = {'count': 0, 'points': 0}
                categories[cat]['count'] += 1
                categories[cat]['points'] += achievement['points']
            
            return {
                'total_achievements': len(achievements),
                'total_points': total_points,
                'total_available': total_all,
                'total_visible': total_visible,
                'categories': categories,
                'achievements': achievements
            }
        finally:
            cursor.close()
            conn.close()
    
    def update_progress(self, user_id: int, code: str, progress: int = 1, increment: bool = True) -> bool:
        """
        Обновляет прогресс к достижению.
        
        Args:
            user_id: ID пользователя
            code: Код достижения
            progress: Значение прогресса
            increment: Если True, добавляет к текущему прогрессу, иначе устанавливает новое значение
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            if increment:
                query = """
                    INSERT INTO achievement_progress (user_id, achievement_code, progress)
                    VALUES (%s, %s, %s)
                    ON DUPLICATE KEY UPDATE progress = progress + VALUES(progress)
                """
            else:
                query = """
                    INSERT INTO achievement_progress (user_id, achievement_code, progress)
                    VALUES (%s, %s, %s)
                    ON DUPLICATE KEY UPDATE progress = VALUES(progress)
                """
            
            cursor.execute(query, (user_id, code, progress))
            conn.commit()
            return True
            
        except Exception as e:
            logger.error(f"Ошибка при обновлении прогресса: {e}")
            conn.rollback()
            return False
        finally:
            cursor.close()
            conn.close()
    
    def get_progress(self, user_id: int, code: str) -> Tuple[int, int]:
        """
        Получает прогресс к достижению.
        Возвращает кортеж (текущий_прогресс, цель).
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            query = """
                SELECT progress, target FROM achievement_progress
                WHERE user_id = %s AND achievement_code = %s
            """
            cursor.execute(query, (user_id, code))
            result = cursor.fetchone()
            
            if result:
                return result[0], result[1]
            return 0, 1
            
        finally:
            cursor.close()
            conn.close()
    
    def check_level_achievement(self, user_id: int, level: int, character_name: str = None) -> Optional[Dict]:
        """Проверяет и выдает достижение за достижение уровня."""
        code = f"level_{level}"
        if level < 2 or level > 20:
            return None
        
        return self.grant_achievement(user_id, code, character_name, f"Достиг {level}-го уровня")
    
    def check_damage_achievement(self, user_id: int, damage: int, character_name: str = None) -> Optional[Dict]:
        """Проверяет и выдает достижение за нанесенный урон."""
        if damage >= 100:
            return self.grant_achievement(user_id, "damage_100", character_name, f"Нанес {damage} урона")
        elif damage >= 50:
            return self.grant_achievement(user_id, "damage_50", character_name, f"Нанес {damage} урона")
        elif damage >= 30:
            return self.grant_achievement(user_id, "damage_30", character_name, f"Нанес {damage} урона")
        return None
    
    def check_stat_achievement(self, user_id: int, stat_name: str, stat_value: int, character_name: str = None) -> Optional[Dict]:
        """Проверяет и выдает достижение за характеристику."""
        stat_map = {
            'strength': 'max_strength',
            'dexterity': 'max_dexterity',
            'constitution': 'max_constitution',
            'intelligence': 'max_intelligence',
            'wisdom': 'max_wisdom',
            'charisma': 'max_charisma'
        }
        
        dump_map = {
            'strength': 'dump_strength',
            'dexterity': 'dump_dexterity',
            'constitution': 'dump_constitution',
            'intelligence': 'dump_intelligence',
            'wisdom': 'dump_wisdom',
            'charisma': 'dump_charisma'
        }
        
        # Проверка на максимальную характеристику
        if stat_value >= 20 and stat_name in stat_map:
            return self.grant_achievement(user_id, stat_map[stat_name], character_name, f"{stat_name} = {stat_value}")
        
        # Проверка на минимальную характеристику
        if stat_value < 5 and stat_name in dump_map:
            return self.grant_achievement(user_id, dump_map[stat_name], character_name, f"{stat_name} = {stat_value}")
        
        return None
    
    def check_multikill_achievement(self, user_id: int, kills: int, character_name: str = None) -> Optional[Dict]:
        """Проверяет и выдает достижение за мультикилл."""
        if kills >= 5:
            return self.grant_achievement(user_id, "multikill_5", character_name, f"Убил {kills} врагов одним действием")
        elif kills >= 3:
            return self.grant_achievement(user_id, "multikill_3", character_name, f"Убил {kills} врагов одним действием")
        return None
    
    def format_achievement_notification(self, achievement: Dict) -> str:
        """Форматирует уведомление о получении достижения."""
        icon = achievement.get('icon', '🏆')
        name = achievement['name']
        desc = achievement.get('description', '')
        points = achievement['points']
        
        text = f"\n{icon} <b>НОВОЕ ДОСТИЖЕНИЕ!</b> {icon}\n"
        text += f"<b>{name}</b>\n"
        if desc:
            text += f"<i>{desc}</i>\n"
        text += f"📊 Очки: <b>+{points}</b>\n"
        
        return text
    
    def format_achievements_list(self, user_id: int) -> str:
        """Форматирует список достижений пользователя."""
        summary = self.get_user_achievement_summary(user_id)
        
        text = "🏆 <b>ВАШИ ДОСТИЖЕНИЯ</b> 🏆\n\n"
        text += f"📊 Всего очков: <b>{summary['total_points']}</b>\n"
        text += f"🎯 Получено: <b>{summary['total_achievements']}/{summary['total_visible']}</b> "
        
        # Процент выполнения
        if summary['total_visible'] > 0:
            percent = (summary['total_achievements'] / summary['total_visible']) * 100
            text += f"({percent:.1f}%)\n\n"
        else:
            text += "\n\n"
        
        # Группируем по категориям
        category_names = {
            'levels': '📈 Уровни',
            'combat': '⚔️ Бой',
            'stats': '💪 Характеристики',
            'defense': '🛡️ Защита',
            'magic': '✨ Магия',
            'special': '🌟 Особые',
            'funny': '😄 Забавные'
        }
        
        if summary['achievements']:
            # Сортируем достижения по категориям
            by_category = {}
            for ach in summary['achievements']:
                cat = ach.get('category', 'other')
                if cat not in by_category:
                    by_category[cat] = []
                by_category[cat].append(ach)
            
            # Выводим по категориям
            for cat in ['levels', 'combat', 'stats', 'defense', 'magic', 'special', 'funny']:
                if cat in by_category:
                    text += f"\n{category_names.get(cat, cat.title())}\n"
                    for ach in by_category[cat]:
                        icon = ach.get('icon', '🏆')
                        text += f"  {icon} <b>{ach['name']}</b> (+{ach['points']})\n"
                        if ach.get('description'):
                            text += f"      <i>{ach['description']}</i>\n"
        else:
            text += "У вас пока нет достижений. Играйте и получайте награды!"
        
        return text

# Создаем глобальный экземпляр менеджера
achievement_manager = AchievementManager()
