#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Тестовый скрипт для проверки работы системы достижений.
"""

from achievement_manager import achievement_manager
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_achievements():
    """Тестирует работу системы достижений."""
    
    # Тестовый ID пользователя
    test_user_id = 123456789
    
    print("\n=== ТЕСТИРОВАНИЕ СИСТЕМЫ ДОСТИЖЕНИЙ ===\n")
    
    # 1. Проверяем список достижений пользователя (должен быть пустой)
    print("1. Проверка списка достижений для нового пользователя:")
    achievements_list = achievement_manager.format_achievements_list(test_user_id)
    print(achievements_list.replace('<b>', '').replace('</b>', '').replace('<i>', '').replace('</i>', ''))
    
    # 2. Выдаем достижение за создание первого персонажа
    print("\n2. Выдаем достижение 'first_character':")
    achievement = achievement_manager.grant_achievement(test_user_id, 'first_character', 'Тестовый Герой')
    if achievement:
        notification = achievement_manager.format_achievement_notification(achievement)
        print(notification.replace('<b>', '').replace('</b>', '').replace('<i>', '').replace('</i>', ''))
    else:
        print("Достижение уже получено или произошла ошибка")
    
    # 3. Выдаем достижение за достижение 5-го уровня
    print("\n3. Выдаем достижение за 5-й уровень:")
    achievement = achievement_manager.check_level_achievement(test_user_id, 5, 'Тестовый Герой')
    if achievement:
        notification = achievement_manager.format_achievement_notification(achievement)
        print(notification.replace('<b>', '').replace('</b>', '').replace('<i>', '').replace('</i>', ''))
    else:
        print("Достижение уже получено или не выполнены условия")
    
    # 4. Выдаем достижение за высокий урон
    print("\n4. Выдаем достижение за урон 35:")
    achievement = achievement_manager.check_damage_achievement(test_user_id, 35, 'Тестовый Герой')
    if achievement:
        notification = achievement_manager.format_achievement_notification(achievement)
        print(notification.replace('<b>', '').replace('</b>', '').replace('<i>', '').replace('</i>', ''))
    else:
        print("Достижение уже получено или не выполнены условия")
    
    # 5. Пытаемся выдать то же достижение повторно
    print("\n5. Попытка повторной выдачи достижения 'first_character':")
    achievement = achievement_manager.grant_achievement(test_user_id, 'first_character', 'Тестовый Герой')
    if achievement:
        print("ОШИБКА: Достижение выдано повторно!")
    else:
        print("✓ Защита от повторной выдачи работает")
    
    # 6. Проверяем достижение за характеристику
    print("\n6. Выдаем достижение за максимальную Силу:")
    achievement = achievement_manager.check_stat_achievement(test_user_id, 'strength', 20, 'Тестовый Герой')
    if achievement:
        notification = achievement_manager.format_achievement_notification(achievement)
        print(notification.replace('<b>', '').replace('</b>', '').replace('<i>', '').replace('</i>', ''))
    else:
        print("Достижение уже получено или не выполнены условия")
    
    # 7. Проверяем достижение за низкую характеристику
    print("\n7. Выдаем достижение за низкий Интеллект:")
    achievement = achievement_manager.check_stat_achievement(test_user_id, 'intelligence', 3, 'Тупой Орк')
    if achievement:
        notification = achievement_manager.format_achievement_notification(achievement)
        print(notification.replace('<b>', '').replace('</b>', '').replace('<i>', '').replace('</i>', ''))
    else:
        print("Достижение уже получено или не выполнены условия")
    
    # 8. Финальный список достижений
    print("\n8. Итоговый список достижений пользователя:")
    achievements_list = achievement_manager.format_achievements_list(test_user_id)
    print(achievements_list.replace('<b>', '').replace('</b>', '').replace('<i>', '').replace('</i>', ''))
    
    # 9. Получаем сводку по достижениям
    print("\n9. Сводка по достижениям:")
    summary = achievement_manager.get_user_achievement_summary(test_user_id)
    print(f"Всего достижений: {summary['total_achievements']}/{summary['total_visible']}")
    print(f"Всего очков: {summary['total_points']}")
    print(f"По категориям:")
    for cat, data in summary['categories'].items():
        print(f"  - {cat}: {data['count']} достижений, {data['points']} очков")
    
    print("\n=== ТЕСТИРОВАНИЕ ЗАВЕРШЕНО ===\n")

if __name__ == "__main__":
    test_achievements()
