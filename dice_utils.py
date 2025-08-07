import random
import re
import logging

logger = logging.getLogger(__name__)

def roll_dice(dice_notation: str) -> tuple[int, str]:
    """
    Roll dice based on D&D dice notation (e.g., '1d6+3', '2d8', '1d20')
    Returns tuple of (total_result, detailed_breakdown)
    """
    if not dice_notation:
        return 0, "No dice specified"
    
    # Clean the notation
    dice_notation = dice_notation.strip().lower().replace(' ', '')
    
    # Parse dice notation like "1d6+3", "2d8", "1d20-1"
    pattern = r'(\d*)d(\d+)([+-]\d+)?'
    match = re.match(pattern, dice_notation)
    
    if not match:
        logger.error(f"Invalid dice notation: {dice_notation}")
        return 0, f"Invalid dice: {dice_notation}"
    
    num_dice = int(match.group(1)) if match.group(1) else 1
    die_size = int(match.group(2))
    modifier = int(match.group(3)) if match.group(3) else 0
    
    # Roll the dice
    rolls = [random.randint(1, die_size) for _ in range(num_dice)]
    total = sum(rolls) + modifier
    
    # Create breakdown string
    if len(rolls) == 1:
        if modifier != 0:
            breakdown = f"{rolls[0]} + {modifier} = {total}" if modifier > 0 else f"{rolls[0]} {modifier} = {total}"
        else:
            breakdown = f"{rolls[0]} = {total}"
    else:
        rolls_str = " + ".join(map(str, rolls))
        if modifier != 0:
            breakdown = f"{rolls_str} + {modifier} = {total}" if modifier > 0 else f"{rolls_str} {modifier} = {total}"
        else:
            breakdown = f"{rolls_str} = {total}"
    
    return total, breakdown

def roll_dice_detailed(dice_notation: str) -> tuple[int, list[int], int, str]:
    """
    Roll dice and return detailed information for damage calculations
    Returns tuple of (total_result, individual_rolls, modifier, detailed_breakdown)
    """
    if not dice_notation:
        return 0, [], 0, "No dice specified"
    
    # Clean the notation
    dice_notation = dice_notation.strip().lower().replace(' ', '')
    
    # Parse dice notation like "1d6+3", "2d8", "1d20-1"
    pattern = r'(\d*)d(\d+)([+-]\d+)?'
    match = re.match(pattern, dice_notation)
    
    if not match:
        logger.error(f"Invalid dice notation: {dice_notation}")
        return 0, [], 0, f"Invalid dice: {dice_notation}"
    
    num_dice = int(match.group(1)) if match.group(1) else 1
    die_size = int(match.group(2))
    modifier = int(match.group(3)) if match.group(3) else 0
    
    # Roll the dice
    rolls = [random.randint(1, die_size) for _ in range(num_dice)]
    total = sum(rolls) + modifier
    
    # Create breakdown string
    if len(rolls) == 1:
        if modifier != 0:
            breakdown = f"{rolls[0]} + {modifier} = {total}" if modifier > 0 else f"{rolls[0]} {modifier} = {total}"
        else:
            breakdown = f"{rolls[0]} = {total}"
    else:
        rolls_str = " + ".join(map(str, rolls))
        if modifier != 0:
            breakdown = f"{rolls_str} + {modifier} = {total}" if modifier > 0 else f"{rolls_str} {modifier} = {total}"
        else:
            breakdown = f"{rolls_str} = {total}"
    
    return total, rolls, modifier, breakdown

def roll_d20(modifier: int = 0) -> tuple[int, str]:
    """
    Roll a d20 with modifier (for attack rolls, saving throws, etc.)
    Returns tuple of (total_result, detailed_breakdown)
    """
    roll = random.randint(1, 20)
    total = roll + modifier
    
    if modifier > 0:
        breakdown = f"{roll}+{modifier} = {total}"
    elif modifier < 0:
        breakdown = f"{roll}{modifier} = {total}"
    else:
        breakdown = f"{roll}"
    
    return total, breakdown

def calculate_modifier(ability_score: int) -> int:
    """Calculate D&D 5e ability modifier from ability score"""
    return (ability_score - 10) // 2

def is_critical_hit(attack_roll: int) -> bool:
    """Check if the attack roll (raw d20) is a critical hit (natural 20)"""
    return attack_roll == 20

def is_critical_miss(attack_roll: int) -> bool:
    """Check if the attack roll (raw d20) is a critical miss (natural 1)"""
    return attack_roll == 1
