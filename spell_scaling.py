#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Модуль для работы с системой усиления заклинаний.
Обрабатывает усиление заговоров по уровню персонажа и усиление заклинаний через слоты.
"""

import json
import logging
import re
from database import execute_query

logger = logging.getLogger(__name__)

def get_cantrip_scaling(spell_id: int, character_level: int) -> dict:
    """
    Получает параметры усиления заговора для указанного уровня персонажа.
    
    Args:
        spell_id: ID заклинания
        character_level: Уровень персонажа
        
    Returns:
        Словарь с параметрами усиления
    """
    try:
        # Получаем данные усиления для ближайшего подходящего уровня
        scaling_data = execute_query("""
            SELECT damage_dice, num_beams, other_effects
            FROM cantrip_scaling
            WHERE spell_id = %s AND character_level <= %s
            ORDER BY character_level DESC
            LIMIT 1
        """, (spell_id, character_level))
        
        if scaling_data:
            data = scaling_data[0]
            result = {
                'damage_dice': data['damage_dice'],
                'num_beams': data['num_beams']
            }
            
            if data['other_effects']:
                result['other_effects'] = json.loads(data['other_effects'])
            
            return result
    except Exception as e:
        logger.error(f"Ошибка при получении усиления заговора {spell_id}: {e}")
    
    return {}

def get_spell_slot_scaling(spell_id: int, slot_level: int) -> dict:
    """
    Получает параметры усиления заклинания при использовании слота указанного уровня.
    
    Args:
        spell_id: ID заклинания
        slot_level: Уровень используемого слота
        
    Returns:
        Словарь с параметрами усиления
    """
    try:
        scaling_data = execute_query("""
            SELECT damage_bonus, duration_bonus, target_bonus, other_effects
            FROM spell_slot_scaling
            WHERE spell_id = %s AND slot_level = %s
        """, (spell_id, slot_level))
        
        if scaling_data:
            data = scaling_data[0]
            result = {}
            
            if data['damage_bonus']:
                result['damage_bonus'] = data['damage_bonus']
            if data['duration_bonus']:
                result['duration_bonus'] = data['duration_bonus']
            if data['target_bonus']:
                result['target_bonus'] = data['target_bonus']
            if data['other_effects']:
                result['other_effects'] = json.loads(data['other_effects'])
            
            return result
    except Exception as e:
        logger.error(f"Ошибка при получении усиления заклинания {spell_id} для слота {slot_level}: {e}")
    
    return {}

def get_spell_scaling_rules(spell_id: int) -> list:
    """
    Получает специальные правила усиления для заклинания.
    
    Args:
        spell_id: ID заклинания
        
    Returns:
        Список правил усиления
    """
    try:
        rules = execute_query("""
            SELECT rule_type, rule_value, rule_description
            FROM spell_scaling_rules
            WHERE spell_id = %s
        """, (spell_id,))
        
        return rules or []
    except Exception as e:
        logger.error(f"Ошибка при получении правил усиления для заклинания {spell_id}: {e}")
        return []

def calculate_scaled_damage(base_damage: str, scaling: dict, character_level: int = None) -> str:
    """
    Вычисляет усиленный урон заклинания.
    
    Args:
        base_damage: Базовый урон (например, "1d10")
        scaling: Данные усиления
        character_level: Уровень персонажа (для заговоров)
        
    Returns:
        Усиленный урон в виде строки
    """
    # Для заговоров используем damage_dice из scaling
    if 'damage_dice' in scaling and scaling['damage_dice']:
        return scaling['damage_dice']
    
    # Для обычных заклинаний добавляем бонусный урон
    if 'damage_bonus' in scaling and scaling['damage_bonus']:
        # Парсим базовый урон
        base_match = re.match(r'(\d+)d(\d+)(?:\+(\d+))?', base_damage)
        bonus_match = re.match(r'\+(\d+)d(\d+)', scaling['damage_bonus'])
        
        if base_match and bonus_match:
            base_num = int(base_match.group(1))
            base_die = int(base_match.group(2))
            base_mod = int(base_match.group(3) or 0)
            
            bonus_num = int(bonus_match.group(1))
            bonus_die = int(bonus_match.group(2))
            
            # Если кости одинаковые, складываем количество
            if base_die == bonus_die:
                total_num = base_num + bonus_num
                if base_mod:
                    return f"{total_num}d{base_die}+{base_mod}"
                else:
                    return f"{total_num}d{base_die}"
            else:
                # Иначе показываем отдельно
                if base_mod:
                    return f"{base_damage} + {bonus_num}d{bonus_die}"
                else:
                    return f"{base_damage} + {bonus_num}d{bonus_die}"
    
    return base_damage

def get_spell_description_with_scaling(spell_id: int, slot_level: int = None, character_level: int = None) -> str:
    """
    Получает описание заклинания с учетом усиления.
    
    Args:
        spell_id: ID заклинания
        slot_level: Уровень используемого слота (для обычных заклинаний)
        character_level: Уровень персонажа (для заговоров)
        
    Returns:
        Описание с учетом усиления
    """
    try:
        # Получаем базовую информацию о заклинании
        spell_data = execute_query("""
            SELECT name, level, damage, description, scaling_type
            FROM spells
            WHERE id = %s
        """, (spell_id,))
        
        if not spell_data:
            return ""
        
        spell = spell_data[0]
        description_parts = []
        
        # Базовое описание
        if spell['description']:
            description_parts.append(spell['description'])
        
        # Усиление для заговоров
        if spell['level'] == 0 and character_level:
            scaling = get_cantrip_scaling(spell_id, character_level)
            if scaling:
                if 'damage_dice' in scaling:
                    description_parts.append(f"💥 Урон на {character_level} уровне: {scaling['damage_dice']}")
                if 'num_beams' in scaling and scaling['num_beams']:
                    description_parts.append(f"🎯 Количество лучей: {scaling['num_beams']}")
                if 'other_effects' in scaling:
                    effects = scaling['other_effects']
                    if 'description' in effects:
                        description_parts.append(f"✨ {effects['description']}")
        
        # Усиление для обычных заклинаний
        elif spell['level'] > 0 and slot_level and slot_level > spell['level']:
            scaling = get_spell_slot_scaling(spell_id, slot_level)
            if scaling:
                description_parts.append(f"\n📈 Усиление слотом {slot_level} уровня:")
                
                if 'damage_bonus' in scaling:
                    scaled_damage = calculate_scaled_damage(spell['damage'] or "0", scaling)
                    description_parts.append(f"  💥 Урон: {scaled_damage}")
                
                if 'target_bonus' in scaling:
                    description_parts.append(f"  🎯 Дополнительные цели: +{scaling['target_bonus']}")
                
                if 'other_effects' in scaling:
                    effects = scaling['other_effects']
                    for key, value in effects.items():
                        description_parts.append(f"  ✨ {value}")
        
        # Специальные правила
        rules = get_spell_scaling_rules(spell_id)
        if rules:
            description_parts.append("\n📜 Правила усиления:")
            for rule in rules:
                description_parts.append(f"  • {rule['rule_description']}")
        
        return "\n".join(description_parts)
        
    except Exception as e:
        logger.error(f"Ошибка при получении описания заклинания {spell_id} с усилением: {e}")
        return ""

def apply_spell_scaling_in_combat(spell_id: int, base_damage: str, slot_level: int = None, 
                                 character_level: int = None, num_targets: int = 1) -> dict:
    """
    Применяет усиление заклинания для боевых расчетов.
    
    Args:
        spell_id: ID заклинания
        base_damage: Базовый урон
        slot_level: Уровень используемого слота
        character_level: Уровень персонажа
        num_targets: Количество целей (базовое)
        
    Returns:
        Словарь с усиленными параметрами
    """
    result = {
        'damage': base_damage,
        'num_targets': num_targets,
        'num_attacks': 1,
        'special_effects': []
    }
    
    try:
        # Получаем информацию о заклинании
        spell_data = execute_query("""
            SELECT level, scaling_type
            FROM spells
            WHERE id = %s
        """, (spell_id,))
        
        if not spell_data:
            return result
        
        spell = spell_data[0]
        
        # Усиление заговоров
        if spell['level'] == 0 and character_level:
            scaling = get_cantrip_scaling(spell_id, character_level)
            if scaling:
                if 'damage_dice' in scaling:
                    result['damage'] = scaling['damage_dice']
                if 'num_beams' in scaling and scaling['num_beams']:
                    result['num_attacks'] = scaling['num_beams']
                if 'other_effects' in scaling:
                    result['special_effects'].append(scaling['other_effects'])
        
        # Усиление обычных заклинаний
        elif spell['level'] > 0 and slot_level and slot_level > spell['level']:
            scaling = get_spell_slot_scaling(spell_id, slot_level)
            if scaling:
                if 'damage_bonus' in scaling:
                    result['damage'] = calculate_scaled_damage(base_damage, scaling)
                if 'target_bonus' in scaling:
                    result['num_targets'] += scaling['target_bonus']
                if 'other_effects' in scaling:
                    result['special_effects'].append(scaling['other_effects'])
        
        # Применяем специальные правила
        rules = get_spell_scaling_rules(spell_id)
        for rule in rules:
            if rule['rule_type'] == 'missiles_per_slot' and slot_level:
                # Для Magic Missile и подобных
                spell_level = spell['level']
                if slot_level > spell_level:
                    additional = (slot_level - spell_level)
                    result['num_attacks'] += additional
            elif rule['rule_type'] == 'rays_per_slot' and slot_level:
                # Для Scorching Ray и подобных
                spell_level = spell['level']
                if slot_level > spell_level:
                    additional = (slot_level - spell_level)
                    result['num_attacks'] += additional
        
    except Exception as e:
        logger.error(f"Ошибка при применении усиления заклинания {spell_id}: {e}")
    
    return result

def format_spell_with_scaling(spell_name: str, slot_level: int = None, character_level: int = None) -> str:
    """
    Форматирует название заклинания с указанием уровня усиления.
    
    Args:
        spell_name: Название заклинания
        slot_level: Уровень слота (для обычных заклинаний)
        character_level: Уровень персонажа (для заговоров)
        
    Returns:
        Отформатированное название
    """
    if slot_level:
        return f"{spell_name} (слот {slot_level} ур.)"
    elif character_level:
        # Показываем уровень усиления для заговоров на ключевых уровнях
        if character_level >= 17:
            return f"{spell_name} (4-й уровень силы)"
        elif character_level >= 11:
            return f"{spell_name} (3-й уровень силы)"
        elif character_level >= 5:
            return f"{spell_name} (2-й уровень силы)"
    
    return spell_name
