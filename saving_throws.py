#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Модуль для работы со спасбросками в D&D.
Обрабатывает спасброски для заклинаний и других эффектов.
"""

import json
import logging
from typing import Optional, Tuple, Dict
from database import get_db
from dice_utils import roll_d20, calculate_modifier

logger = logging.getLogger(__name__)

class SavingThrowManager:
    def __init__(self):
        self.db = get_db()
        
        # Маппинг названий характеристик на поля в БД
        self.stat_mapping = {
            'Сила': 'strength',
            'Ловкость': 'dexterity',
            'Телосложение': 'constitution',
            'Интеллект': 'intelligence',
            'Мудрость': 'wisdom',
            'Харизма': 'charisma'
        }
    
    def calculate_spell_save_dc(self, caster_id: int) -> int:
        """
        Вычисляет сложность спасброска от заклинаний персонажа.
        
        Формула: 8 + бонус мастерства + модификатор заклинательной характеристики
        """
        if not self.db.connection or not self.db.connection.is_connected():
            self.db.connect()
        
        # Получаем информацию о персонаже и его классе
        query = """
            SELECT c.level, c.intelligence, c.wisdom, c.charisma,
                   cl.primary_stat, cl.name as class_name
            FROM characters c
            JOIN classes cl ON c.class_id = cl.id
            WHERE c.id = %s
        """
        
        result = self.db.execute_query(query, (caster_id,))
        
        if not result:
            logger.error(f"Персонаж {caster_id} не найден")
            return 13  # Базовая сложность по умолчанию
        
        char_data = result[0]
        
        # Определяем заклинательную характеристику
        spell_stat = None
        class_name = char_data['class_name']
        
        # Определяем основную характеристику заклинателя по классу
        if class_name == 'Волшебник':
            spell_stat = char_data['intelligence']
        elif class_name in ['Жрец', 'Друид', 'Следопыт', 'Монах']:
            spell_stat = char_data['wisdom']
        elif class_name in ['Бард', 'Чародей', 'Колдун', 'Паладин']:
            spell_stat = char_data['charisma']
        else:
            # Для не-заклинателей используем основную характеристику класса
            primary_stat = char_data.get('primary_stat', '').lower()
            if primary_stat in ['strength', 'dexterity', 'constitution', 'intelligence', 'wisdom', 'charisma']:
                spell_stat = char_data.get(primary_stat, 10)
            else:
                spell_stat = 10  # Значение по умолчанию
        
        # Вычисляем модификатор характеристики
        spell_modifier = calculate_modifier(spell_stat or 10)
        
        # Вычисляем бонус мастерства
        proficiency_bonus = 2 + (char_data['level'] - 1) // 4
        
        # Сложность спасброска = 8 + бонус мастерства + модификатор характеристики
        save_dc = 8 + proficiency_bonus + spell_modifier
        
        logger.info(f"Персонаж {caster_id} ({class_name}): DC спасброска = {save_dc} "
                   f"(8 + {proficiency_bonus} проф. + {spell_modifier} мод.)")
        
        return save_dc
    
    def make_saving_throw(self, target_id: int, target_type: str, 
                         save_type: str, dc: int, 
                         advantage: bool = False, disadvantage: bool = False) -> Tuple[bool, str]:
        """
        Совершает спасбросок для цели.
        
        Args:
            target_id: ID цели
            target_type: Тип цели ('character' или 'enemy')
            save_type: Тип спасброска (Сила, Ловкость, Телосложение, Интеллект, Мудрость, Харизма)
            dc: Сложность спасброска
            advantage: Преимущество на бросок
            disadvantage: Помеха на бросок
            
        Returns:
            (успех, текст_результата)
        """
        if not self.db.connection or not self.db.connection.is_connected():
            self.db.connect()
        
        # Получаем характеристики цели
        if target_type == 'character':
            stats = self._get_character_stats(target_id)
            proficiency_bonus = self._get_character_proficiency(target_id, save_type)
        else:  # enemy
            stats = self._get_enemy_stats(target_id)
            proficiency_bonus = 0  # Враги пока не имеют владения спасбросками
        
        if not stats:
            logger.error(f"Цель {target_type} {target_id} не найдена")
            return False, "Цель не найдена"
        
        # Определяем характеристику для спасброска
        stat_field = self.stat_mapping.get(save_type, 'constitution')
        stat_value = stats.get(stat_field, 10)
        
        # Вычисляем модификатор
        stat_modifier = calculate_modifier(stat_value)
        total_modifier = stat_modifier + proficiency_bonus
        
        # Совершаем бросок
        if advantage and not disadvantage:
            # Бросаем дважды, берем лучший результат
            roll1, _ = roll_d20(total_modifier)
            roll2, _ = roll_d20(total_modifier)
            roll_result = max(roll1, roll2)
            raw_roll = roll_result - total_modifier
            breakdown = f"d20({raw_roll} с преим.) + {total_modifier}"
        elif disadvantage and not advantage:
            # Бросаем дважды, берем худший результат
            roll1, _ = roll_d20(total_modifier)
            roll2, _ = roll_d20(total_modifier)
            roll_result = min(roll1, roll2)
            raw_roll = roll_result - total_modifier
            breakdown = f"d20({raw_roll} с пом.) + {total_modifier}"
        else:
            # Обычный бросок
            roll_result, breakdown = roll_d20(total_modifier)
            raw_roll = roll_result - total_modifier
        
        # Проверяем результат
        success = roll_result >= dc
        
        # Натуральная 20 - всегда успех, натуральная 1 - всегда провал
        if raw_roll == 20:
            success = True
            result_text = f"🎲 Спасбросок {save_type}: {breakdown} = {roll_result} vs DC {dc} - ✨ КРИТ. УСПЕХ!"
        elif raw_roll == 1:
            success = False
            result_text = f"🎲 Спасбросок {save_type}: {breakdown} = {roll_result} vs DC {dc} - 💀 КРИТ. ПРОВАЛ!"
        else:
            if success:
                result_text = f"🎲 Спасбросок {save_type}: {breakdown} = {roll_result} vs DC {dc} - ✅ УСПЕХ"
            else:
                result_text = f"🎲 Спасбросок {save_type}: {breakdown} = {roll_result} vs DC {dc} - ❌ ПРОВАЛ"
        
        logger.info(f"{target_type} {target_id}: {result_text}")
        
        return success, result_text
    
    def _get_character_stats(self, character_id: int) -> Optional[Dict]:
        """Получает характеристики персонажа."""
        query = """
            SELECT name, strength, dexterity, constitution, 
                   intelligence, wisdom, charisma
            FROM characters
            WHERE id = %s
        """
        
        result = self.db.execute_query(query, (character_id,))
        return result[0] if result else None
    
    def _get_enemy_stats(self, enemy_id: int) -> Optional[Dict]:
        """Получает характеристики врага."""
        query = """
            SELECT name, strength, dexterity, constitution,
                   intelligence, wisdom, charisma
            FROM enemies
            WHERE id = %s
        """
        
        result = self.db.execute_query(query, (enemy_id,))
        if result:
            enemy = result[0]
            # Если характеристики не заданы, используем значения по умолчанию
            return {
                'name': enemy.get('name', 'Неизвестный'),
                'strength': enemy.get('strength', 10),
                'dexterity': enemy.get('dexterity', 10),
                'constitution': enemy.get('constitution', 10),
                'intelligence': enemy.get('intelligence', 10),
                'wisdom': enemy.get('wisdom', 10),
                'charisma': enemy.get('charisma', 10)
            }
        return None
    
    def _get_character_proficiency(self, character_id: int, save_type: str) -> int:
        """
        Проверяет, владеет ли персонаж данным типом спасброска.
        Возвращает бонус мастерства если владеет, иначе 0.
        """
        query = """
            SELECT c.level, cl.saving_throw_proficiencies
            FROM characters c
            JOIN classes cl ON c.class_id = cl.id
            WHERE c.id = %s
        """
        
        result = self.db.execute_query(query, (character_id,))
        
        if not result:
            return 0
        
        char_data = result[0]
        proficiencies_json = char_data.get('saving_throw_proficiencies')
        
        if not proficiencies_json:
            return 0
        
        try:
            proficiencies = json.loads(proficiencies_json)
            if save_type in proficiencies:
                # Персонаж владеет этим спасброском
                proficiency_bonus = 2 + (char_data['level'] - 1) // 4
                return proficiency_bonus
        except json.JSONDecodeError:
            logger.error(f"Ошибка парсинга JSON спасбросков для персонажа {character_id}")
        
        return 0
    
    def process_spell_saving_throw(self, spell_id: int, caster_id: int, 
                                  target_id: int, target_type: str = 'enemy') -> Tuple[bool, str]:
        """
        Обрабатывает спасбросок от заклинания.
        
        Returns:
            (успех_спасброска, текст_результата)
        """
        if not self.db.connection or not self.db.connection.is_connected():
            self.db.connect()
        
        # Получаем информацию о заклинании
        spell_query = """
            SELECT name, saving_throw
            FROM spells
            WHERE id = %s
        """
        
        spell_result = self.db.execute_query(spell_query, (spell_id,))
        
        if not spell_result:
            logger.error(f"Заклинание {spell_id} не найдено")
            return False, "Заклинание не найдено"
        
        spell = spell_result[0]
        save_type = spell.get('saving_throw')
        
        if not save_type:
            logger.warning(f"Заклинание {spell['name']} не требует спасброска")
            return False, ""
        
        # Вычисляем DC спасброска
        dc = self.calculate_spell_save_dc(caster_id)
        
        # Совершаем спасбросок
        success, result_text = self.make_saving_throw(
            target_id, target_type, save_type, dc
        )
        
        return success, result_text
    
    def process_aoe_saving_throws(self, spell_id: int, caster_id: int, 
                                 targets: list) -> Dict[int, Tuple[bool, str]]:
        """
        Обрабатывает спасброски для AoE заклинания.
        
        Args:
            spell_id: ID заклинания
            caster_id: ID заклинателя
            targets: Список словарей с информацией о целях
                    [{'id': enemy_id, 'type': 'enemy'}, ...]
        
        Returns:
            Словарь {target_id: (успех, текст_результата)}
        """
        results = {}
        
        # Вычисляем DC один раз для всех целей
        dc = self.calculate_spell_save_dc(caster_id)
        
        # Получаем тип спасброска
        spell_query = "SELECT saving_throw FROM spells WHERE id = %s"
        spell_result = self.db.execute_query(spell_query, (spell_id,))
        
        if not spell_result or not spell_result[0].get('saving_throw'):
            # Заклинание не требует спасброска
            for target in targets:
                results[target['id']] = (False, "")
            return results
        
        save_type = spell_result[0]['saving_throw']
        
        # Каждая цель делает отдельный спасбросок
        for target in targets:
            success, result_text = self.make_saving_throw(
                target['id'], target.get('type', 'enemy'), save_type, dc
            )
            results[target['id']] = (success, result_text)
        
        return results

# Глобальный экземпляр менеджера спасбросков
saving_throw_manager = SavingThrowManager()
