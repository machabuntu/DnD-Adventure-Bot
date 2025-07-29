from character_generation import CharacterGenerator
import json

def test_weapon_proficiency():
    gen = CharacterGenerator()
    gen.db.connect()
    
    # Данные плута
    rogue_prof = ['простое', 'воинское со свойством фехтовальное или легкое']
    
    # Тестируем различные виды оружия
    weapons_to_test = [
        ('Короткий меч', 'Воинское', '["Фехтовальное", "Лёгкое"]'),
        ('Рапира', 'Воинское', '["Фехтовальное"]'),
        ('Скимитар', 'Воинское', '["Фехтовальное", "Лёгкое"]'),
        ('Длинный меч', 'Воинское', '["Универсальное (1d10)"]'),
        ('Кинжал', 'Простое', '["Фехтовальное", "Лёгкое", "Метательное"]')
    ]
    
    print('Тестирование владения оружием для плута:')
    for name, wtype, props in weapons_to_test:
        can_use = gen.can_use_weapon(name, wtype, props, rogue_prof)
        print(f'{name} ({wtype}): {can_use} - {props}')

if __name__ == "__main__":
    test_weapon_proficiency()
