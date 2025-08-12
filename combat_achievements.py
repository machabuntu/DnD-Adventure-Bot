#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Учет боевых метрик и выдача достижений по итогам боя.
"""
import logging
from typing import Optional, List, Dict
from database import get_db
from achievement_manager import achievement_manager

logger = logging.getLogger(__name__)

db = get_db()

def ensure_tables():
    """Создает служебные таблицы для учета боя (если отсутствуют)."""
    queries = [
        """
        CREATE TABLE IF NOT EXISTS combat_state (
            adventure_id INT PRIMARY KEY,
            round INT NOT NULL DEFAULT 1,
            started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """,
        """
        CREATE TABLE IF NOT EXISTS combat_metrics (
            adventure_id INT NOT NULL,
            character_id INT NOT NULL,
            damage_dealt INT NOT NULL DEFAULT 0,
            damage_taken INT NOT NULL DEFAULT 0,
            kills INT NOT NULL DEFAULT 0,
            PRIMARY KEY (adventure_id, character_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """
    ]
    for q in queries:
        db.execute_query(q)


def init_combat(adventure_id: int):
    ensure_tables()
    db.execute_query(
        "INSERT IGNORE INTO combat_state (adventure_id, round) VALUES (%s, 1)",
        (adventure_id,)
    )
    # Инициализация метрик для участников боя
    participants = db.execute_query(
        """
        SELECT c.id AS character_id
        FROM adventure_participants ap
        JOIN characters c ON ap.character_id = c.id
        WHERE ap.adventure_id = %s
        """,
        (adventure_id,)
    )
    for p in participants:
        db.execute_query(
            "INSERT IGNORE INTO combat_metrics (adventure_id, character_id) VALUES (%s, %s)",
            (adventure_id, p['character_id'])
        )


def increment_round(adventure_id: int):
    db.execute_query(
        "UPDATE combat_state SET round = round + 1 WHERE adventure_id = %s",
        (adventure_id,)
    )


def get_round(adventure_id: int) -> int:
    row = db.execute_query("SELECT round FROM combat_state WHERE adventure_id = %s", (adventure_id,))
    return row[0]['round'] if row else 1


def record_damage_dealt(adventure_id: int, character_id: int, amount: int):
    if amount <= 0:
        return
    ensure_tables()
    db.execute_query(
        """
        INSERT INTO combat_metrics (adventure_id, character_id, damage_dealt)
        VALUES (%s, %s, %s)
        ON DUPLICATE KEY UPDATE damage_dealt = damage_dealt + VALUES(damage_dealt)
        """,
        (adventure_id, character_id, amount)
    )


def record_damage_taken(adventure_id: int, character_id: int, amount: int):
    if amount <= 0:
        return
    ensure_tables()
    db.execute_query(
        """
        INSERT INTO combat_metrics (adventure_id, character_id, damage_taken)
        VALUES (%s, %s, %s)
        ON DUPLICATE KEY UPDATE damage_taken = damage_taken + VALUES(damage_taken)
        """,
        (adventure_id, character_id, amount)
    )


def record_kill(adventure_id: int, character_id: int, kills: int = 1):
    if kills <= 0:
        return
    ensure_tables()
    db.execute_query(
        """
        INSERT INTO combat_metrics (adventure_id, character_id, kills)
        VALUES (%s, %s, %s)
        ON DUPLICATE KEY UPDATE kills = kills + VALUES(kills)
        """,
        (adventure_id, character_id, kills)
    )


def get_metrics_for_adventure(adventure_id: int) -> List[Dict]:
    return db.execute_query(
        "SELECT * FROM combat_metrics WHERE adventure_id = %s",
        (adventure_id,)
    )


def award_end_combat_achievements(adventure_id: int, victory: Optional[str] = None):
    """Выдает достижения по итогам боя."""
    ensure_tables()
    round_num = get_round(adventure_id)

    # Получаем участников и их метрики
    metrics = get_metrics_for_adventure(adventure_id)
    participants = db.execute_query(
        """
        SELECT c.id as character_id, c.user_id, c.name, c.current_hp
        FROM adventure_participants ap
        JOIN characters c ON ap.character_id = c.id
        WHERE ap.adventure_id = %s
        """,
        (adventure_id,)
    )
    metrics_map = {(m['character_id']): m for m in metrics}

    # Победа за 1 раунд
    if victory == 'players' and round_num == 1:
        for p in participants:
            if p['user_id']:
                achievement_manager.grant_achievement(p['user_id'], 'speedrun', p['name'])

    for p in participants:
        user_id = p['user_id']
        if not user_id:
            continue
        char_id = p['character_id']
        m = metrics_map.get(char_id, {'damage_dealt': 0, 'damage_taken': 0, 'kills': 0})

        # Пацифист: завершить бой без нанесения урона
        if m.get('damage_dealt', 0) == 0 and victory == 'players':
            achievement_manager.grant_achievement(user_id, 'pacifist', p['name'])

        # Выживший: завершить бой с 1 HP
        if p.get('current_hp', 0) == 1 and victory == 'players':
            achievement_manager.grant_achievement(user_id, 'survivor', p['name'])

        # Танк: 100+ полученного урона за одно приключение
        if m.get('damage_taken', 0) >= 100:
            achievement_manager.grant_achievement(user_id, 'tank', p['name'])

    # Очистка состояния боя (не метрик приключения, они накапливаются)
    db.execute_query("DELETE FROM combat_state WHERE adventure_id = %s", (adventure_id,))

