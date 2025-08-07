import logging
from database import get_db
from dice_utils import calculate_modifier

logger = logging.getLogger(__name__)

def calculate_character_ac(character_id: int) -> int:
    """Calculate the Armor Class for a character including armor and dexterity modifier"""
    logger.info(f"AC CALC: Starting AC calculation for character {character_id}")
    
    try:
        db = get_db()
        if not db.connection or not db.connection.is_connected():
            logger.info(f"AC CALC: Connecting to database")
            db.connect()
        
        # Get character data
        char_query = "SELECT dexterity FROM characters WHERE id = %s"
        logger.info(f"AC CALC: Getting character data with query: {char_query}")
        char_data = db.execute_query(char_query, (character_id,))
        
        if not char_data:
            logger.error(f"AC CALC: Character {character_id} not found for AC calculation")
            return 10  # Default AC
        
        character = char_data[0]
        dex_modifier = calculate_modifier(character.get('dexterity', 10))
        logger.info(f"AC CALC: Character {character_id} DEX modifier: {dex_modifier}")
        
        # Base AC without armor (10 + DEX modifier)
        base_ac = 10 + dex_modifier
        logger.info(f"AC CALC: Base AC (10 + DEX): {base_ac}")
        
        # Check for equipped armor - simplified query with timeout
        armor_query = """
            SELECT a.armor_class, a.name, a.armor_type 
            FROM character_equipment ce
            INNER JOIN armor a ON ce.item_id = a.id
            WHERE ce.character_id = %s AND ce.item_type = 'armor' AND ce.is_equipped = TRUE
            LIMIT 1
        """
        
        logger.info(f"AC CALC: Checking for equipped armor")
        equipped_armor = db.execute_query(armor_query, (character_id,))
        
        if equipped_armor:
            logger.info(f"AC CALC: Found equipped armor: {equipped_armor[0]['name']}")
            armor = equipped_armor[0]
            armor_class_str = str(armor['armor_class'])
            
            # Simplified armor parsing to avoid complex string operations
            try:
                # Try to parse as simple integer first (heavy armor)
                calculated_ac = int(armor_class_str)
                logger.info(f"AC CALC: Heavy armor AC: {calculated_ac}")
                return calculated_ac
            except ValueError:
                # If it's not a simple integer, assume light armor (11 + DEX style)
                if "+" in armor_class_str and not "макс" in armor_class_str:
                    base_ac_value = int(armor_class_str.split()[0])
                    calculated_ac = base_ac_value + dex_modifier
                    logger.info(f"AC CALC: Light armor AC: {base_ac_value} + {dex_modifier} = {calculated_ac}")
                    return calculated_ac
                else:
                    # Fallback to base AC for complex cases
                    logger.warning(f"AC CALC: Complex armor format '{armor_class_str}', using base AC")
                    return base_ac
        else:
            logger.info(f"AC CALC: No armor equipped, returning base AC: {base_ac}")
            return base_ac
            
    except Exception as e:
        logger.error(f"AC CALC: Exception in calculate_character_ac: {e}")
        # Return safe default
        return 10 + max(-5, min(5, (character.get('dexterity', 10) - 10) // 2)) if 'character' in locals() else 10

def update_character_ac(character_id: int):
    """Update the stored armor_class value in the characters table"""
    calculated_ac = calculate_character_ac(character_id)
    
    db = get_db()
    if not db.connection or not db.connection.is_connected():
        db.connect()
    
    db.execute_query("UPDATE characters SET armor_class = %s WHERE id = %s", 
                     (calculated_ac, character_id))
    
    logger.info(f"Updated stored AC for character {character_id}: {calculated_ac}")
    return calculated_ac
