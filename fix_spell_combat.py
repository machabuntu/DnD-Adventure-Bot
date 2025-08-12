#!/usr/bin/env python3
"""Fix non-printable characters in spell_combat.py"""

with open('spell_combat.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Конкретные строки, которые нужно исправить
fixes = {
    188: "            WHERE cp.adventure_id = %s AND cp.participant_type = 'enemy' AND e.hit_points > 0\n",
    310: "                    if dealt > 0:\n",
    319: "                if new_hp <= 0:\n",
    329: "            elif attack_roll_result >= target_ac:\n",
    343: "                if new_hp <= 0:\n",
    360: "                if new_hp <= 0:\n",
    366: '        alive_enemies_query = "SELECT COUNT(*) as count FROM enemies WHERE adventure_id = %s AND hit_points > 0"\n',
    384: "            WHERE cp.adventure_id = %s AND cp.participant_type = 'enemy' AND e.hit_points > 0\n",
    414: "            if dealt > 0:\n",
    417: "            if new_hp <= 0:\n",
    422: "            if total_dealt > 0:\n",
    435: "                    if count >= 5:\n",
    438: "                    elif count >= 3:\n",
    447: '        alive_enemies_query = "SELECT COUNT(*) as count FROM enemies WHERE adventure_id = %s AND hit_points > 0"\n',
    476: "    def _roll_spell_damage(self, damage_dice: str, critical: bool = False) -> dict:\n"
}

for line_num, new_content in fixes.items():
    lines[line_num] = new_content

with open('spell_combat.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)
    
print('Fixed specific lines in spell_combat.py')
