#!/usr/bin/env python3
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import ALLOWED_CHAT_ID

print(f"ALLOWED_CHAT_ID из конфига: {ALLOWED_CHAT_ID}")
print(f"Тип: {type(ALLOWED_CHAT_ID)}")

# Тестируем сравнение с разными значениями
test_chat_ids = [-4855352038, 4855352038, "-4855352038", "4855352038"]

for test_id in test_chat_ids:
    result = test_id == ALLOWED_CHAT_ID
    print(f"Сравнение {test_id} ({type(test_id)}) == {ALLOWED_CHAT_ID}: {result}")
