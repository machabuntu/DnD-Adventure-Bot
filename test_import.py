#!/usr/bin/env python3
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

print("=== Тестируем импорт функций из bot.py ===")

try:
    from bot import start, help_command, version_command, show_character, show_party, delete_character, join_adventure, leave_adventure, unknown_command
    print("✅ Успешно импортированы все функции:")
    print("  - start")
    print("  - help_command") 
    print("  - version_command")
    print("  - show_character")
    print("  - show_party")
    print("  - delete_character")
    print("  - join_adventure")
    print("  - leave_adventure")
    print("  - unknown_command")
    
    # Проверяем, что это функции
    functions = [start, help_command, version_command, show_character, show_party, 
                delete_character, join_adventure, leave_adventure, unknown_command]
    
    for func in functions:
        if not callable(func):
            print(f"❌ {func.__name__} не является функцией")
        else:
            print(f"✅ {func.__name__} - OK")
            
except ImportError as e:
    print(f"❌ Ошибка импорта: {e}")
except Exception as e:
    print(f"❌ Общая ошибка: {e}")
    import traceback
    traceback.print_exc()

print("\n=== Проверяем содержимое start_bot.py ===")
try:
    with open('start_bot.py', 'r', encoding='utf-8') as f:
        content = f.read()
        
    if 'show_character' in content:
        print("✅ show_character найдена в start_bot.py")
    else:
        print("❌ show_character НЕ найдена в start_bot.py")
        
    if 'show_party' in content:
        print("✅ show_party найдена в start_bot.py")
    else:
        print("❌ show_party НЕ найдена в start_bot.py")
        
    if 'version_command' in content:
        print("✅ version_command найдена в start_bot.py")
    else:
        print("❌ version_command НЕ найдена в start_bot.py")

except Exception as e:
    print(f"❌ Ошибка чтения start_bot.py: {e}")

print("\nТест завершен.")
