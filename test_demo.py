#!/usr/bin/env python3
import requests
import json

def test_demo_functionality():
    """Тестирует основную функциональность режима теста"""
    base_url = "http://localhost:5001"
    
    print("🧪 Тестирование режима теста...")
    
    # Тест 1: Проверяем доступность страницы результатов
    try:
        response = requests.get(f"{base_url}/result/4")
        if response.status_code == 200:
            print("✅ Страница результатов доступна")
        else:
            print(f"❌ Ошибка доступа к результатам: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Ошибка подключения: {e}")
        return False
    
    # Тест 2: Проверяем доступность режима теста
    try:
        response = requests.get(f"{base_url}/test/4")
        if response.status_code == 200:
            print("✅ Режим теста доступен")
            # Проверяем, что в ответе есть флеш-карточки
            if "flashcard-test" in response.text:
                print("✅ Интерфейс тестирования загружен")
            else:
                print("⚠️ Интерфейс тестирования может быть неполным")
        else:
            print(f"❌ Ошибка доступа к режиму теста: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Ошибка подключения к режиму теста: {e}")
        return False
    
    # Тест 3: Проверяем API статистики (без авторизации)
    try:
        response = requests.get(f"{base_url}/test/4/stats")
        if response.status_code == 401:
            print("✅ API статистики правильно требует авторизацию")
        else:
            print(f"⚠️ Неожиданный ответ API статистики: {response.status_code}")
    except Exception as e:
        print(f"❌ Ошибка тестирования API статистики: {e}")
    
    print("\n🎉 Базовое тестирование завершено!")
    print(f"📱 Откройте браузер и перейдите по адресу: {base_url}/result/4")
    print("🧠 Нажмите кнопку 'Режим теста' во вкладке 'Флеш-карты'")
    
    return True

if __name__ == '__main__':
    test_demo_functionality()