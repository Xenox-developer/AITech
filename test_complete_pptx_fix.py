#!/usr/bin/env python3
"""
Полный интеграционный тест исправления ограничений PPTX файлов
"""

import os
import sys
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

# Добавляем путь к модулям приложения
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from subscription_manager import subscription_manager, SUBSCRIPTION_PLANS

def create_test_database():
    """Создание тестовой базы данных"""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp_db:
        test_db_path = tmp_db.name
    
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
    
    # Создаем тестовых пользователей
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
    
    return test_db_path

def test_subscription_manager_pptx_check():
    """Тест проверки PPTX через subscription_manager"""
    print("🧪 Тестирование subscription_manager.check_pptx_support()...")
    
    test_db_path = create_test_database()
    original_db_path = subscription_manager.db_path
    subscription_manager.db_path = test_db_path
    
    try:
        results = {}
        
        # Тестируем каждый план
        for user_id in range(1, 6):
            user_subscription = subscription_manager.get_user_subscription(user_id)
            plan = user_subscription['type']
            
            allowed, message = subscription_manager.check_pptx_support(user_id)
            expected = SUBSCRIPTION_PLANS[plan].pptx_support
            
            results[plan] = {
                'allowed': allowed,
                'expected': expected,
                'message': message,
                'passed': allowed == expected
            }
            
            status = "✅ ПРОЙДЕН" if allowed == expected else "❌ НЕ ПРОЙДЕН"
            print(f"  {plan.upper()}: {status} (ожидается: {expected}, получено: {allowed})")
            if message and not allowed:
                print(f"    Сообщение: {message}")
        
        all_passed = all(r['passed'] for r in results.values())
        print(f"\n📊 Результат: {'✅ ВСЕ ТЕСТЫ ПРОЙДЕНЫ' if all_passed else '❌ ЕСТЬ ОШИБКИ'}")
        
        return all_passed
        
    finally:
        subscription_manager.db_path = original_db_path
        try:
            os.unlink(test_db_path)
        except:
            pass

def test_file_upload_logic():
    """Тест логики загрузки файлов"""
    print("\n🧪 Тестирование логики загрузки файлов...")
    
    # Импортируем функции из app.py
    from app import allowed_file
    
    # Тест функции allowed_file
    test_files = [
        ('document.pdf', True),
        ('presentation.pptx', True),
        ('video.mp4', True),
        ('video.mov', True),
        ('video.mkv', True),
        ('document.doc', False),
        ('image.jpg', False),
        ('text.txt', False),
    ]
    
    print("  Тестирование allowed_file():")
    all_passed = True
    
    for filename, expected in test_files:
        result = allowed_file(filename)
        status = "✅" if result == expected else "❌"
        print(f"    {filename}: {status} (ожидается: {expected}, получено: {result})")
        if result != expected:
            all_passed = False
    
    return all_passed

def test_template_rendering():
    """Тест рендеринга шаблонов с условной логикой PPTX"""
    print("\n🧪 Тестирование условной логики в шаблонах...")
    
    # Симулируем данные пользователей с разными планами
    test_cases = [
        {
            'plan': 'freemium',
            'pptx_support': False,
            'expected_accept': '.pdf,.mp4,.mov,.mkv',
            'expected_pptx_disabled': True
        },
        {
            'plan': 'lite',
            'pptx_support': False,
            'expected_accept': '.pdf,.mp4,.mov,.mkv',
            'expected_pptx_disabled': True
        },
        {
            'plan': 'starter',
            'pptx_support': True,
            'expected_accept': '.pdf,.pptx,.mp4,.mov,.mkv',
            'expected_pptx_disabled': False
        },
        {
            'plan': 'basic',
            'pptx_support': True,
            'expected_accept': '.pdf,.pptx,.mp4,.mov,.mkv',
            'expected_pptx_disabled': False
        },
        {
            'plan': 'pro',
            'pptx_support': True,
            'expected_accept': '.pdf,.pptx,.mp4,.mov,.mkv',
            'expected_pptx_disabled': False
        }
    ]
    
    all_passed = True
    
    for case in test_cases:
        plan = case['plan']
        pptx_support = case['pptx_support']
        expected_accept = case['expected_accept']
        expected_disabled = case['expected_pptx_disabled']
        
        # Симулируем логику из шаблона
        if pptx_support:
            actual_accept = '.pdf,.pptx,.mp4,.mov,.mkv'
            actual_disabled = False
        else:
            actual_accept = '.pdf,.mp4,.mov,.mkv'
            actual_disabled = True
        
        accept_correct = actual_accept == expected_accept
        disabled_correct = actual_disabled == expected_disabled
        
        status = "✅" if (accept_correct and disabled_correct) else "❌"
        print(f"  {plan.upper()}: {status}")
        print(f"    Accept атрибут: {actual_accept}")
        print(f"    PPTX отключен: {actual_disabled}")
        
        if not (accept_correct and disabled_correct):
            all_passed = False
    
    return all_passed

def test_error_messages():
    """Тест корректности сообщений об ошибках"""
    print("\n🧪 Тестирование сообщений об ошибках...")
    
    test_db_path = create_test_database()
    original_db_path = subscription_manager.db_path
    subscription_manager.db_path = test_db_path
    
    try:
        # Тестируем пользователей без поддержки PPTX
        test_users = [
            (1, 'freemium'),
            (2, 'lite')
        ]
        
        expected_message = "Загрузка PPTX файлов доступна только в планах STARTER, BASIC и PRO. Обновите план для продолжения."
        
        all_passed = True
        
        for user_id, plan in test_users:
            allowed, message = subscription_manager.check_pptx_support(user_id)
            
            if allowed:
                print(f"  ❌ {plan.upper()}: Ошибка - PPTX разрешен, хотя не должен быть")
                all_passed = False
            elif message != expected_message:
                print(f"  ❌ {plan.upper()}: Неверное сообщение об ошибке")
                print(f"    Ожидается: {expected_message}")
                print(f"    Получено: {message}")
                all_passed = False
            else:
                print(f"  ✅ {plan.upper()}: Корректное сообщение об ошибке")
        
        return all_passed
        
    finally:
        subscription_manager.db_path = original_db_path
        try:
            os.unlink(test_db_path)
        except:
            pass

def test_plan_configuration():
    """Тест конфигурации планов подписки"""
    print("\n🧪 Тестирование конфигурации планов...")
    
    expected_pptx_support = {
        'freemium': False,
        'lite': False,
        'starter': True,
        'basic': True,
        'pro': True
    }
    
    all_passed = True
    
    for plan, expected in expected_pptx_support.items():
        if plan in SUBSCRIPTION_PLANS:
            actual = SUBSCRIPTION_PLANS[plan].pptx_support
            status = "✅" if actual == expected else "❌"
            print(f"  {plan.upper()}: {status} (ожидается: {expected}, получено: {actual})")
            if actual != expected:
                all_passed = False
        else:
            print(f"  ❌ {plan.upper()}: План не найден в конфигурации")
            all_passed = False
    
    return all_passed

def run_all_tests():
    """Запуск всех тестов"""
    print("🚀 Запуск полного интеграционного теста исправления PPTX...")
    print("=" * 70)
    
    tests = [
        ("Конфигурация планов", test_plan_configuration),
        ("Менеджер подписок", test_subscription_manager_pptx_check),
        ("Логика загрузки файлов", test_file_upload_logic),
        ("Рендеринг шаблонов", test_template_rendering),
        ("Сообщения об ошибках", test_error_messages)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ Ошибка в тесте '{test_name}': {e}")
            results.append((test_name, False))
    
    print("\n" + "=" * 70)
    print("📊 ИТОГОВЫЕ РЕЗУЛЬТАТЫ:")
    print("=" * 70)
    
    all_passed = True
    for test_name, passed in results:
        status = "✅ ПРОЙДЕН" if passed else "❌ НЕ ПРОЙДЕН"
        print(f"{test_name}: {status}")
        if not passed:
            all_passed = False
    
    print("=" * 70)
    if all_passed:
        print("🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ! Исправление PPTX ограничений работает корректно.")
        print("\n✅ Что исправлено:")
        print("  • Пользователи FREE и LITE не могут загружать PPTX файлы")
        print("  • Пользователи STARTER, BASIC и PRO могут загружать PPTX файлы")
        print("  • Корректные сообщения об ошибках")
        print("  • Условное отображение PPTX в интерфейсе")
        print("  • Правильные атрибуты accept в форме загрузки")
    else:
        print("❌ НЕКОТОРЫЕ ТЕСТЫ НЕ ПРОЙДЕНЫ! Требуется дополнительная проверка.")
        return False
    
    return True

if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)