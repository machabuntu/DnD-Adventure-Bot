@echo off
echo Starting Mock Grok API Server...
echo.
echo Make sure Flask is installed: pip install flask
echo.
echo Server will be available at http://localhost:5000
echo Available endpoints:
echo   POST /v1/chat/completions - Main API endpoint
echo   GET /health - Health check
echo   GET /responses - List available response files
echo.
echo Press Ctrl+C to stop the server
echo.

python mock_grok_api.py
