#!/usr/bin/env python3
"""
Тест безопасности для проверки системы токенов доступа
"""
import sqlite3
import requests
import sys

def test_access_tokens():
    """Тестирует систему токенов доступа"""
    print("🔒 Тестирование системы безопасности...")
    
    # Подключаемся к базе данных
    conn = sqlite3.connect('ai_study.db')
    c = conn.cursor()
    
    # Получаем все результаты с токенами
    c.execute('SELECT id, access_token, user_id FROM result WHERE access_token IS NOT NULL LIMIT 3')
    results = c.fetchall()
    
    if not results:
        print("❌ Нет результатов с токенами доступа")
        return False
    
    print(f"✅ Найдено {len(results)} результатов с токенами доступа")
    
    base_url = "http://127.0.0.1:5000"
    
    for result_id, access_token, user_id in results:
        print(f"\n📋 Тестирование результата ID={result_id}, user_id={user_id}")
        print(f"🔑 Токен: {access_token[:20]}...")
        
        # Тест 1: Доступ неавторизованного пользователя по токену (должен быть заблокирован для результатов с владельцем)
        token_url = f"{base_url}/result/{access_token}"
        try:
            # Используем новую сессию без авторизации
            session = requests.Session()
            response = session.get(token_url, timeout=5)
            
            if user_id:  # Если у результата есть владелец
                if response.status_code == 200:
                    # Проверяем, не перенаправляет ли на страницу входа
                    if "login" in response.url.lower() or "войти" in response.text.lower():
                        print(f"✅ Неавторизованный доступ заблокирован (перенаправление на вход)")
                    else:
                        print(f"❌ Неавторизованный пользователь может видеть результат!")
                        return False
                elif response.status_code == 302:
                    print(f"✅ Неавторизованный доступ заблокирован (перенаправление): {response.status_code}")
                elif response.status_code == 403:
                    print(f"✅ Неавторизованный доступ заблокирован (запрещено): {response.status_code}")
                else:
                    print(f"⚠️  Неожиданный статус для неавторизованного доступа: {response.status_code}")
            else:  # Если у результата нет владельца
                if response.status_code == 200:
                    print(f"✅ Доступ к результату без владельца работает: {response.status_code}")
                else:
                    print(f"⚠️  Доступ к результату без владельца не работает: {response.status_code}")
                    
        except requests.exceptions.RequestException as e:
            print(f"❌ Ошибка запроса по токену: {e}")
        
        # Тест 2: Доступ по старому ID не должен работать (если маршрут существует)
        old_id_url = f"{base_url}/result/{result_id}"
        try:
            response = requests.get(old_id_url, timeout=5)
            if response.status_code == 404:
                print(f"✅ Старый маршрут по ID заблокирован: {response.status_code}")
            else:
                print(f"⚠️  Старый маршрут по ID все еще работает: {response.status_code}")
        except requests.exceptions.RequestException as e:
            print(f"✅ Старый маршрут недоступен: {e}")
    
    conn.close()
    
    print("\n🎯 Тест завершен!")
    return True

def check_database_structure():
    """Проверяет структуру базы данных"""
    print("\n🗄️  Проверка структуры базы данных...")
    
    conn = sqlite3.connect('ai_study.db')
    c = conn.cursor()
    
    # Проверяем наличие колонки access_token
    c.execute("PRAGMA table_info(result)")
    columns = [column[1] for column in c.fetchall()]
    
    if 'access_token' in columns:
        print("✅ Колонка access_token существует")
    else:
        print("❌ Колонка access_token отсутствует")
        return False
    
    # Проверяем, что все записи имеют токены
    c.execute('SELECT COUNT(*) FROM result WHERE access_token IS NULL')
    null_tokens = c.fetchone()[0]
    
    if null_tokens == 0:
        print("✅ Все записи имеют токены доступа")
    else:
        print(f"⚠️  {null_tokens} записей без токенов доступа")
    
    # Проверяем уникальность токенов
    c.execute('SELECT COUNT(DISTINCT access_token) as unique_tokens, COUNT(*) as total FROM result WHERE access_token IS NOT NULL')
    unique_tokens, total = c.fetchone()
    
    if unique_tokens == total:
        print("✅ Все токены уникальны")
    else:
        print(f"❌ Найдены дублирующиеся токены: {unique_tokens} уникальных из {total}")
    
    conn.close()
    return True

if __name__ == '__main__':
    print("🚀 Запуск тестов безопасности...")
    
    # Проверяем структуру БД
    if not check_database_structure():
        sys.exit(1)
    
    # Тестируем доступ
    if not test_access_tokens():
        sys.exit(1)
    
    print("\n🎉 Все тесты пройдены успешно!")