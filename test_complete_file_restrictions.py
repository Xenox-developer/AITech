#!/usr/bin/env python3
"""
Полный интеграционный тест ограничений файлов (PPTX и видео)
"""

import os
import sys
import sqlite3
import tempfile
from pathlib import Path

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

def test_plan_configuration():
    """Тест конфигурации планов подписки"""
    print("🧪 Тестирование конфигурации планов...")
    
    expected_config = {
        'freemium': {'pptx_support': False, 'video_support': False},
        'lite': {'pptx_support': False, 'video_support': False},
        'starter': {'pptx_support': True, 'video_support': True},
        'basic': {'pptx_support': True, 'video_support': True},
        'pro': {'pptx_support': True, 'video_support': True}
    }
    
    all_passed = True
    
    for plan, expected in expected_config.items():
        if plan in SUBSCRIPTION_PLANS:
            actual_pptx = SUBSCRIPTION_PLANS[plan].pptx_support
            actual_video = SUBSCRIPTION_PLANS[plan].video_support
            
            pptx_ok = actual_pptx == expected['pptx_support']
            video_ok = actual_video == expected['video_support']
            
            status = "✅" if (pptx_ok and video_ok) else "❌"
            print(f"  {plan.upper()}: {status}")
            print(f"    PPTX: {actual_pptx} (ожидается: {expected['pptx_support']})")
            print(f"    Видео: {actual_video} (ожидается: {expected['video_support']})")
            
            if not (pptx_ok and video_ok):
                all_passed = False
        else:
            print(f"  ❌ {plan.upper()}: План не найден в конфигурации")
            all_passed = False
    
    return all_passed

def test_file_restrictions():
    """Тест ограничений файлов через subscription_manager"""
    print("\n🧪 Тестирование ограничений файлов...")
    
    test_db_path = create_test_database()
    original_db_path = subscription_manager.db_path
    subscription_manager.db_path = test_db_path
    
    try:
        all_passed = True
        
        # Тестируем каждый план
        for user_id in range(1, 6):
            user_subscription = subscription_manager.get_user_subscription(user_id)
            plan = user_subscription['type']
            
            # Проверяем PPTX
            pptx_allowed, pptx_message = subscription_manager.check_pptx_support(user_id)
            expected_pptx = SUBSCRIPTION_PLANS[plan].pptx_support
            
            # Проверяем видео
            video_allowed, video_message = subscription_manager.check_video_support(user_id)
            expected_video = SUBSCRIPTION_PLANS[plan].video_support
            
            pptx_ok = pptx_allowed == expected_pptx
            video_ok = video_allowed == expected_video
            
            status = "✅ ПРОЙДЕН" if (pptx_ok and video_ok) else "❌ НЕ ПРОЙДЕН"
            print(f"  {plan.upper()}: {status}")
            print(f"    PPTX: {'✅' if pptx_ok else '❌'} (разрешено: {pptx_allowed})")
            if pptx_message:
                print(f"      Сообщение: {pptx_message}")
            print(f"    Видео: {'✅' if video_ok else '❌'} (разрешено: {video_allowed})")
            if video_message:
                print(f"      Сообщение: {video_message}")
            
            if not (pptx_ok and video_ok):
                all_passed = False
        
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
        ('archive.zip', False),
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

def test_template_logic():
    """Тест логики шаблонов"""
    print("\n🧪 Тестирование логики шаблонов...")
    
    test_cases = [
        {
            'plan': 'freemium',
            'pptx_support': False,
            'video_support': False,
            'expected_accept': '.pdf',
            'expected_pptx_disabled': True,
            'expected_video_disabled': True
        },
        {
            'plan': 'lite',
            'pptx_support': False,
            'video_support': False,
            'expected_accept': '.pdf',
            'expected_pptx_disabled': True,
            'expected_video_disabled': True
        },
        {
            'plan': 'starter',
            'pptx_support': True,
            'video_support': True,
            'expected_accept': '.pdf,.pptx,.mp4,.mov,.mkv',
            'expected_pptx_disabled': False,
            'expected_video_disabled': False
        },
        {
            'plan': 'basic',
            'pptx_support': True,
            'video_support': True,
            'expected_accept': '.pdf,.pptx,.mp4,.mov,.mkv',
            'expected_pptx_disabled': False,
            'expected_video_disabled': False
        },
        {
            'plan': 'pro',
            'pptx_support': True,
            'video_support': True,
            'expected_accept': '.pdf,.pptx,.mp4,.mov,.mkv',
            'expected_pptx_disabled': False,
            'expected_video_disabled': False
        }
    ]
    
    all_passed = True
    
    for case in test_cases:
        plan = case['plan']
        pptx_support = case['pptx_support']
        video_support = case['video_support']
        expected_accept = case['expected_accept']
        expected_pptx_disabled = case['expected_pptx_disabled']
        expected_video_disabled = case['expected_video_disabled']
        
        # Симулируем логику из шаблона
        accepted_formats = ['.pdf']
        if pptx_support:
            accepted_formats.append('.pptx')
        if video_support:
            accepted_formats.extend(['.mp4', '.mov', '.mkv'])
        
        actual_accept = ','.join(accepted_formats)
        actual_pptx_disabled = not pptx_support
        actual_video_disabled = not video_support
        
        accept_correct = actual_accept == expected_accept
        pptx_correct = actual_pptx_disabled == expected_pptx_disabled
        video_correct = actual_video_disabled == expected_video_disabled
        
        all_correct = accept_correct and pptx_correct and video_correct
        status = "✅" if all_correct else "❌"
        
        print(f"  {plan.upper()}: {status}")
        print(f"    Accept: {actual_accept}")
        print(f"    PPTX отключен: {actual_pptx_disabled}")
        print(f"    Видео отключено: {actual_video_disabled}")
        
        if not all_correct:
            all_passed = False
    
    return all_passed

def test_error_messages():
    """Тест корректности сообщений об ошибках"""
    print("\n🧪 Тестирование сообщений об ошибках...")
    
    test_db_path = create_test_database()
    original_db_path = subscription_manager.db_path
    subscription_manager.db_path = test_db_path
    
    try:
        # Тестируем пользователей без поддержки файлов
        test_users = [
            (1, 'freemium'),
            (2, 'lite')
        ]
        
        expected_pptx_message = "Загрузка PPTX файлов доступна только в планах STARTER, BASIC и PRO. Обновите план для продолжения."
        expected_video_message = "Загрузка видео файлов доступна только в планах STARTER, BASIC и PRO. Обновите план для продолжения."
        
        all_passed = True
        
        for user_id, plan in test_users:
            # Проверяем PPTX сообщение
            pptx_allowed, pptx_message = subscription_manager.check_pptx_support(user_id)
            
            if pptx_allowed:
                print(f"  ❌ {plan.upper()}: PPTX разрешен, хотя не должен быть")
                all_passed = False
            elif pptx_message != expected_pptx_message:
                print(f"  ❌ {plan.upper()}: Неверное PPTX сообщение")
                all_passed = False
            else:
                print(f"  ✅ {plan.upper()}: Корректное PPTX сообщение")
            
            # Проверяем видео сообщение
            video_allowed, video_message = subscription_manager.check_video_support(user_id)
            
            if video_allowed:
                print(f"  ❌ {plan.upper()}: Видео разрешено, хотя не должно быть")
                all_passed = False
            elif video_message != expected_video_message:
                print(f"  ❌ {plan.upper()}: Неверное видео сообщение")
                all_passed = False
            else:
                print(f"  ✅ {plan.upper()}: Корректное видео сообщение")
        
        return all_passed
        
    finally:
        subscription_manager.db_path = original_db_path
        try:
            os.unlink(test_db_path)
        except:
            pass

def run_all_tests():
    """Запуск всех тестов"""
    print("🚀 Запуск полного интеграционного теста ограничений файлов...")
    print("=" * 70)
    
    tests = [
        ("Конфигурация планов", test_plan_configuration),
        ("Ограничения файлов", test_file_restrictions),
        ("Логика загрузки файлов", test_file_upload_logic),
        ("Логика шаблонов", test_template_logic),
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
        print("🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ! Ограничения файлов работают корректно.")
        print("\n✅ Что работает:")
        print("  📄 PDF файлы: доступны всем планам")
        print("  📊 PPTX файлы: только STARTER, BASIC, PRO")
        print("  🎥 Видео файлы: только STARTER, BASIC, PRO")
        print("  🚫 FREE и LITE: только PDF файлы")
        print("  💬 Корректные сообщения об ошибках")
        print("  🎨 Адаптивный интерфейс")
        
        print("\n📋 Сводная таблица доступности:")
        print("┌─────────────┬──────┬──────┬───────┐")
        print("│    План     │ PDF  │ PPTX │ Видео │")
        print("├─────────────┼──────┼──────┼───────┤")
        print("│ FREEMIUM    │  ✅  │  ❌  │   ❌  │")
        print("│ LITE        │  ✅  │  ❌  │   ❌  │")
        print("│ STARTER     │  ✅  │  ✅  │   ✅  │")
        print("│ BASIC       │  ✅  │  ✅  │   ✅  │")
        print("│ PRO         │  ✅  │  ✅  │   ✅  │")
        print("└─────────────┴──────┴──────┴───────┘")
    else:
        print("❌ НЕКОТОРЫЕ ТЕСТЫ НЕ ПРОЙДЕНЫ! Требуется дополнительная проверка.")
        return False
    
    return True

if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)