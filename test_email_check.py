#!/usr/bin/env python3
"""
Тестовый скрипт для проверки API проверки email
"""
import requests
import json

def test_email_check():
    """Тестирование API проверки email"""
    base_url = "http://localhost:5000"
    
    # Тестовые случаи
    test_cases = [
        {
            "email": "test@test.ru",
            "expected": "exists",
            "description": "Существующий email"
        },
        {
            "email": "newuser@example.com", 
            "expected": "available",
            "description": "Новый доступный email"
        },
        {
            "email": "invalid-email",
            "expected": "invalid",
            "description": "Неверный формат email"
        },
        {
            "email": "",
            "expected": "error",
            "description": "Пустой email"
        }
    ]
    
    print("🧪 Тестирование API проверки email...\n")
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"Тест {i}: {test_case['description']}")
        print(f"Email: '{test_case['email']}'")
        
        try:
            response = requests.post(
                f"{base_url}/api/check_email",
                json={"email": test_case["email"]},
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                data = response.json()
                print(f"Ответ: {json.dumps(data, ensure_ascii=False, indent=2)}")
                
                # Анализ результата
                if test_case["expected"] == "exists" and data.get("exists"):
                    print("✅ ПРОЙДЕН: Email существует")
                elif test_case["expected"] == "available" and not data.get("exists") and data.get("valid"):
                    print("✅ ПРОЙДЕН: Email доступен")
                elif test_case["expected"] == "invalid" and not data.get("valid"):
                    print("✅ ПРОЙДЕН: Неверный формат обнаружен")
                else:
                    print("❌ НЕ ПРОЙДЕН: Неожиданный результат")
            else:
                print(f"❌ НЕ ПРОЙДЕН: HTTP {response.status_code}")
                if test_case["expected"] == "error":
                    print("✅ Но это ожидаемая ошибка")
                    
        except requests.exceptions.ConnectionError:
            print("❌ ОШИБКА: Не удается подключиться к серверу")
            print("Убедитесь, что приложение запущено на http://localhost:5000")
            break
        except Exception as e:
            print(f"❌ ОШИБКА: {e}")
        
        print("-" * 50)

if __name__ == "__main__":
    test_email_check()