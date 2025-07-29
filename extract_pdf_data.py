import PyPDF2
import json
import re
from database import get_db

def extract_weapons_from_pdf():
    """Извлекает данные об оружии из PDF"""
    try:
        with open("Docs/Оружие.pdf", 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            text = ""
            for page in pdf_reader.pages:
                text += page.extract_text()
        
        # Выводим текст для анализа
        print("=== ОРУЖИЕ ===")
        print(text[:2000])  # Первые 2000 символов
        print("=" * 50)
        
    except Exception as e:
        print(f"Ошибка при чтении оружия: {e}")

def extract_origins_from_pdf():
    """Извлекает данные о происхождениях из PDF"""
    try:
        with open("Docs/Происхождения.pdf", 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            text = ""
            for page in pdf_reader.pages:
                text += page.extract_text()
        
        print("=== ПРОИСХОЖДЕНИЯ ===")
        print(text[:3000])  # Первые 3000 символов
        print("=" * 50)
        
    except Exception as e:
        print(f"Ошибка при чтении происхождений: {e}")

def extract_classes_from_pdf():
    """Извлекает данные о классах из PDF файлов"""
    import os
    
    classes_dir = "Docs/Классы"
    if not os.path.exists(classes_dir):
        print("Папка с классами не найдена")
        return
    
    for filename in os.listdir(classes_dir):
        if filename.endswith('.pdf'):
            class_name = filename.replace('.pdf', '')
            print(f"\n=== КЛАСС: {class_name} ===")
            
            try:
                with open(os.path.join(classes_dir, filename), 'rb') as file:
                    pdf_reader = PyPDF2.PdfReader(file)
                    text = ""
                    for page in pdf_reader.pages:
                        text += page.extract_text()
                
                # Ищем секцию "Стартовое снаряжение"
                start_gear_match = re.search(r'Стартовое снаряжение.*?(?=\n[А-Я]|\n\d+|\Z)', text, re.DOTALL | re.IGNORECASE)
                if start_gear_match:
                    print("Стартовое снаряжение:")
                    print(start_gear_match.group(0)[:800])
                else:
                    print("Секция 'Стартовое снаряжение' не найдена")
                    print("Первые 1000 символов:")
                    print(text[:1000])
                
                print("-" * 30)
                
            except Exception as e:
                print(f"Ошибка при чтении {filename}: {e}")

if __name__ == "__main__":
    print("Извлечение данных из PDF файлов D&D...")
    extract_weapons_from_pdf()
    extract_origins_from_pdf()
    extract_classes_from_pdf()
