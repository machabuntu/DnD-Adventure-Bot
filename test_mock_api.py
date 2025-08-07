#!/usr/bin/env python3
"""
Простой тест для проверки mock Grok API
"""

import requests
import json

def test_mock_api():
    """Тестирует mock API"""
    
    # Тестируем health endpoint
    try:
        print("Testing health endpoint...")
        response = requests.get("http://localhost:5001/health")
        print(f"Health response: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"Health test failed: {e}")
    
    # Тестируем главный endpoint
    try:
        print("\nTesting chat completions endpoint...")
        data = {
            "model": "mock-grok",
            "messages": [
                {"role": "user", "content": "Действия игроков:\n- Игрок: атаковать врага"}
            ],
            "temperature": 0.7
        }
        
        response = requests.post("http://localhost:5001/v1/chat/completions", 
                               json=data,
                               headers={"Content-Type": "application/json"})
        print(f"Chat completions response: {response.status_code}")
        print(f"Response content: {response.text[:500]}...")
        
        if response.status_code == 200:
            result = response.json()
            print(f"Mock response content: {result['choices'][0]['message']['content'][:200]}...")
            
    except Exception as e:
        print(f"Chat completions test failed: {e}")
    
    # Тестируем responses endpoint
    try:
        print("\nTesting responses list endpoint...")
        response = requests.get("http://localhost:5001/responses")
        print(f"Responses response: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"Responses test failed: {e}")

if __name__ == "__main__":
    test_mock_api()
