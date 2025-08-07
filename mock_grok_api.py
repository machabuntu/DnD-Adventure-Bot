#!/usr/bin/env python3
"""
Mock Grok API Server for debugging DnD Bot
Запуск: python mock_grok_api.py
"""

from flask import Flask, request, jsonify
import json
import os
import logging

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Путь к файлам с ответами
RESPONSES_DIR = "mock_responses"

def load_response_file(filename):
    """Загружает ответ из файла"""
    file_path = os.path.join(RESPONSES_DIR, filename)
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read().strip()
    return None

def get_mock_response(request_data):
    """Определяет какой файл использовать для ответа на основе запроса"""
    
    # Получаем последнее сообщение пользователя
    messages = request_data.get('messages', [])
    if not messages:
        return load_response_file('default.txt')
    
    last_message = messages[-1].get('content', '').lower()
    
    # Определяем тип запроса и возвращаем соответствующий ответ
    if 'создай захватывающее вступление' in last_message:
        return load_response_file('adventure_intro.txt')
    elif 'действия игроков' in last_message:
        # Проверяем есть ли в действиях что-то связанное с боем
        if any(word in last_message for word in ['атака', 'напада', 'сражени', 'бой', 'враг', 'монстр']):
            return load_response_file('combat_start.txt')
        else:
            return load_response_file('continue_adventure.txt')
    elif 'сражение завершено' in last_message:
        return load_response_file('combat_end.txt')
    else:
        return load_response_file('default.txt')

@app.route('/v1/chat/completions', methods=['POST', 'OPTIONS'])
def chat_completions():
    """Эндпоинт, совместимый с OpenAI API"""
    # Handle CORS preflight
    if request.method == 'OPTIONS':
        return jsonify({"status": "ok"})
        
    try:
        request_data = request.get_json()
        
        if not request_data:
            logger.error("No JSON data received")
            return jsonify({"error": "No JSON data provided"}), 400
        
        logger.info(f"Received request with {len(request_data.get('messages', []))} messages")
        logger.info(f"Request data keys: {list(request_data.keys())}")
        
        # Получаем подходящий ответ
        response_content = get_mock_response(request_data)
        
        if response_content is None:
            response_content = "Произошла ошибка при загрузке mock ответа. Проверьте файлы в папке mock_responses."
        
        logger.info(f"Selected response file, returning response with {len(response_content)} characters")
        
        # Формируем ответ в формате OpenAI API
        response = {
            "id": "mock-response-123",
            "object": "chat.completion", 
            "created": 1234567890,
            "model": "mock-grok",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": response_content
                    },
                    "finish_reason": "stop"
                }
            ],
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": len(response_content.split()),
                "total_tokens": 100 + len(response_content.split())
            }
        }
        
        return jsonify(response), 200
        
    except Exception as e:
        logger.error(f"Error processing request: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({"error": str(e)}), 500

@app.route('/health', methods=['GET'])
def health():
    """Проверка здоровья сервера"""
    return jsonify({"status": "ok", "service": "mock-grok-api"})

@app.route('/responses', methods=['GET'])
def list_responses():
    """Список available response files"""
    if not os.path.exists(RESPONSES_DIR):
        return jsonify({"error": "responses directory not found"})
    
    files = [f for f in os.listdir(RESPONSES_DIR) if f.endswith('.txt')]
    return jsonify({"available_responses": files})

@app.route('/', methods=['GET'])
def root():
    """Корневая страница"""
    return jsonify({
        "service": "Mock Grok API",
        "status": "running",
        "endpoints": {
            "POST /v1/chat/completions": "Main API endpoint",
            "GET /health": "Health check", 
            "GET /responses": "List response files"
        }
    })

@app.errorhandler(404)
def not_found(error):
    """Обработчик 404 ошибок"""
    logger.warning(f"404 Not Found: {request.method} {request.path}")
    return jsonify({
        "status": "error",
        "message": "Not found",
        "path": request.path,
        "method": request.method,
        "available_endpoints": [
            "POST /v1/chat/completions",
            "GET /health",
            "GET /responses",
            "GET /"
        ]
    }), 404

@app.before_request
def log_request_info():
    """Логируем все входящие запросы"""
    logger.info(f"Incoming request: {request.method} {request.path} from {request.remote_addr}")
    if request.is_json:
        logger.info(f"Request has JSON data: {bool(request.get_json())}")

if __name__ == '__main__':
    # Создаем папку для ответов если её нет
    if not os.path.exists(RESPONSES_DIR):
        os.makedirs(RESPONSES_DIR)
        logger.info(f"Created {RESPONSES_DIR} directory")
    
    # Проверяем наличие файлов ответов
    logger.info(f"Checking responses directory: {os.path.abspath(RESPONSES_DIR)}")
    if os.path.exists(RESPONSES_DIR):
        files = [f for f in os.listdir(RESPONSES_DIR) if f.endswith('.txt')]
        logger.info(f"Found response files: {files}")
    else:
        logger.warning(f"Responses directory does not exist: {RESPONSES_DIR}")
    
    # Показываем зарегистрированные маршруты
    logger.info("Registered routes:")
    for rule in app.url_map.iter_rules():
        logger.info(f"  {rule.methods} {rule.rule}")
    
    port = 5001  # Используем другой порт для теста
    logger.info(f"Starting Mock Grok API server on http://localhost:{port}")
    logger.info(f"Responses directory: {RESPONSES_DIR}")
    logger.info("Available endpoints:")
    logger.info("  POST /v1/chat/completions - Main API endpoint")
    logger.info("  GET /health - Health check")
    logger.info("  GET /responses - List available response files")
    logger.info("  GET / - Root endpoint")
    
    app.run(host='0.0.0.0', port=port, debug=True)
