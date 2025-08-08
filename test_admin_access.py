#!/usr/bin/env python3
"""
Тестовый скрипт для проверки ограничений доступа к аналитике
"""

import requests
import sys

def test_admin_access():
    """Тестирование доступа к аналитике"""
    base_url = "http://localhost:5000"
    
    print("🔒 Тестирование ограничений доступа к аналитике...")
    
    # Тестируем доступ без авторизации
    print("\n1. Тест доступа без авторизации:")
    
    analytics_urls = [
        "/analytics",
        "/analytics/users", 
        "/analytics/demo",
        "/api/analytics/popular_elements",
        "/api/analytics/user_stats"
    ]
    
    for url in analytics_urls:
        try:
            response = requests.get(f"{base_url}{url}", allow_redirects=False)
            if response.status_code == 302:  # Перенаправление на логин
                print(f"  ✅ {url} - корректно перенаправляет на логин (302)")
            elif response.status_code == 401:  # Неавторизован
                print(f"  ✅ {url} - корректно возвращает 401 (Unauthorized)")
            else:
                print(f"  ❌ {url} - неожиданный код: {response.status_code}")
        except Exception as e:
            print(f"  ❌ {url} - ошибка: {e}")
    
    print("\n✅ Тестирование завершено!")
    print("\nДля полного тестирования:")
    print("1. Войдите как обычный пользователь (alice@example.com) - не должно быть кнопок аналитики")
    print("2. Войдите как администратор (test@test.ru) - должны быть кнопки аналитики")
    print("3. Попробуйте прямые ссылки на аналитику под разными пользователями")

if __name__ == '__main__':
    test_admin_access()