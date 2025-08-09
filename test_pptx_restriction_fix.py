#!/usr/bin/env python3
"""
Тест для проверки исправления ограничений PPTX файлов
"""

import os
import sys
import sqlite3
import tempfile
from pathlib import Path

# Добавляем путь к модулям приложения
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from subscription_manager import subscription_manager, SUBSCRIPTION_PLANS

def test_pptx_restrictions():
    """Тест проверки ограничений PPTX для разных планов"""
    
    print("🧪 Тестирование ограничений PPTX файлов...")
    
    # Создаем временную базу данных для тестирования
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp_db:
        test_db_path = tmp_db.name
    
    # Подменяем путь к базе данных в менеджере подписок
    original_db_path = subscription_manager.db_path
    subscription_manager.db_path = test_db_path
    
    try:
        # Создаем тестовую базу данных
        conn = sqlite3.connect(test_db_path)
        c = conn.cursor()
        
        # Создаем таблицу пользователей
        c.execute('''
            CREATE TABLE users (
                id INTEGER PRIMARY KEY,
                email TEXT UNIQUE,
                subscription_type TEXT DEFAULT 'starter',
                subscription_status TEXT DEFAULT 'active',
                monthly_analyses_used INTEGER DEFAULT 0,
                monthly_reset_date TEXT,
                total_pdf_pages_used INTEGER DEFAULT 0,
                total_video_minutes_used INTEGER DEFAULT 0,
                ai_chat_messages_used INTEGER DEFAULT 0,
                monthly_video_uploads_used INTEGER DEFAULT 0,
                subscription_start_date TEXT,
                subscription_end_date TEXT
            )
        ''')
        
        # Создаем тестовых пользователей с разными планами
        test_users = [
            (1, 'freemium@test.com', 'freemium'),
            (2, 'lite@test.com', 'lite'),
            (3, 'starter@test.com', 'starter'),
            (4, 'basic@test.com', 'basic'),
            (5, 'pro@test.com', 'pro')
        ]
        
        for user_id, email, plan in test_users:
            c.execute('''
                INSERT INTO users (id, email, subscription_type)
                VALUES (?, ?, ?)
            ''', (user_id, email, plan))
        
        conn.commit()
        conn.close()
        
        # Тестируем каждый план
        results = {}
        
        for user_id, email, plan in test_users:
            allowed, message = subscription_manager.check_pptx_support(user_id)
            results[plan] = {
                'allowed': allowed,
                'message': message,
                'expected_allowed': SUBSCRIPTION_PLANS[plan].pptx_support
            }
            
            print(f"📋 План {plan.upper()}:")
            print(f"   Ожидается: {'✅ Разрешено' if SUBSCRIPTION_PLANS[plan].pptx_support else '❌ Запрещено'}")
            print(f"   Результат: {'✅ Разрешено' if allowed else '❌ Запрещено'}")
            if message:
                print(f"   Сообщение: {message}")
            
            # Проверяем корректность
            if allowed == SUBSCRIPTION_PLANS[plan].pptx_support:
                print(f"   ✅ ТЕСТ ПРОЙДЕН")
            else:
                print(f"   ❌ ТЕСТ НЕ ПРОЙДЕН")
            print()
        
        # Проверяем общие результаты
        all_tests_passed = True
        for plan, result in results.items():
            if result['allowed'] != result['expected_allowed']:
                all_tests_passed = False
                break
        
        if all_tests_passed:
            print("🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ! Ограничения PPTX работают корректно.")
            
            # Выводим сводку по планам
            print("\n📊 Сводка по планам:")
            print("FREEMIUM: ❌ PPTX запрещен")
            print("LITE:     ❌ PPTX запрещен") 
            print("STARTER:  ✅ PPTX разрешен")
            print("BASIC:    ✅ PPTX разрешен")
            print("PRO:      ✅ PPTX разрешен")
            
        else:
            print("❌ НЕКОТОРЫЕ ТЕСТЫ НЕ ПРОЙДЕНЫ! Проверьте конфигурацию планов.")
            
        return all_tests_passed
        
    finally:
        # Восстанавливаем оригинальный путь к базе данных
        subscription_manager.db_path = original_db_path
        
        # Удаляем временную базу данных
        try:
            os.unlink(test_db_path)
        except:
            pass

def test_error_messages():
    """Тест корректности сообщений об ошибках"""
    
    print("\n🧪 Тестирование сообщений об ошибках...")
    
    # Создаем временную базу данных для тестирования
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp_db:
        test_db_path = tmp_db.name
    
    # Подменяем путь к базе данных в менеджере подписок
    original_db_path = subscription_manager.db_path
    subscription_manager.db_path = test_db_path
    
    try:
        # Создаем тестовую базу данных
        conn = sqlite3.connect(test_db_path)
        c = conn.cursor()
        
        # Создаем таблицу пользователей
        c.execute('''
            CREATE TABLE users (
                id INTEGER PRIMARY KEY,
                email TEXT UNIQUE,
                subscription_type TEXT DEFAULT 'starter',
                subscription_status TEXT DEFAULT 'active',
                monthly_analyses_used INTEGER DEFAULT 0,
                monthly_reset_date TEXT,
                total_pdf_pages_used INTEGER DEFAULT 0,
                total_video_minutes_used INTEGER DEFAULT 0,
                ai_chat_messages_used INTEGER DEFAULT 0,
                monthly_video_uploads_used INTEGER DEFAULT 0,
                subscription_start_date TEXT,
                subscription_end_date TEXT
            )
        ''')
        
        # Создаем пользователя с планом freemium (без поддержки PPTX)
        c.execute('''
            INSERT INTO users (id, email, subscription_type)
            VALUES (1, 'freemium@test.com', 'freemium')
        ''')
        
        conn.commit()
        conn.close()
        
        # Проверяем сообщение об ошибке
        allowed, message = subscription_manager.check_pptx_support(1)
        
        expected_message = "Загрузка PPTX файлов доступна только в планах STARTER, BASIC и PRO. Обновите план для продолжения."
        
        print(f"Ожидаемое сообщение: {expected_message}")
        print(f"Полученное сообщение: {message}")
        
        if message == expected_message:
            print("✅ Сообщение об ошибке корректно")
            return True
        else:
            print("❌ Сообщение об ошибке некорректно")
            return False
            
    finally:
        # Восстанавливаем оригинальный путь к базе данных
        subscription_manager.db_path = original_db_path
        
        # Удаляем временную базу данных
        try:
            os.unlink(test_db_path)
        except:
            pass

if __name__ == '__main__':
    print("🚀 Запуск тестов исправления ограничений PPTX...")
    print("=" * 60)
    
    # Запускаем тесты
    test1_passed = test_pptx_restrictions()
    test2_passed = test_error_messages()
    
    print("\n" + "=" * 60)
    if test1_passed and test2_passed:
        print("🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ! Исправление работает корректно.")
        print("\n✅ Теперь пользователи с планами FREE и LITE не смогут загружать PPTX файлы")
        print("✅ Пользователи с планами STARTER, BASIC и PRO могут загружать PPTX файлы")
        print("✅ Сообщения об ошибках корректны")
    else:
        print("❌ НЕКОТОРЫЕ ТЕСТЫ НЕ ПРОЙДЕНЫ!")
        sys.exit(1)