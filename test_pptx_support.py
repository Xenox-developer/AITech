#!/usr/bin/env python3
"""
Тест поддержки PPTX файлов для разных планов подписки
Проверяет, что PPTX доступен только для BASIC и PRO планов
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from subscription_manager import SubscriptionManager, SUBSCRIPTION_PLANS
import sqlite3
from datetime import datetime, timedelta

def test_pptx_support():
    """Тестирует поддержку PPTX файлов для разных планов"""
    print("📄 Запуск тестов поддержки PPTX файлов")
    print("=" * 50)
    
    # Инициализация менеджера подписок
    manager = SubscriptionManager()
    
    # Создаем тестового пользователя
    conn = sqlite3.connect('ai_study.db')
    cursor = conn.cursor()
    
    # Очищаем тестовые данные
    cursor.execute("DELETE FROM users WHERE email = 'pptx_test@example.com'")
    conn.commit()
    
    # Создаем пользователя
    cursor.execute("""
        INSERT INTO users (email, password_hash, subscription_type, subscription_status,
                          monthly_analyses_used, monthly_pdf_pages_used, monthly_video_uploads_used,
                          ai_chat_messages_used, subscription_start_date, subscription_end_date)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        'pptx_test@example.com',
        'test_hash',
        'freemium',
        'active',
        0, 0, 0, 0,
        datetime.now().isoformat(),
        (datetime.now() + timedelta(days=30)).isoformat()
    ))
    
    user_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    print(f"✅ Создан тестовый пользователь ID: {user_id}")
    
    # Тест 1: Проверка поддержки PPTX для всех планов
    print("\n=== Тест 1: Проверка поддержки PPTX для всех планов ===")
    
    plans_to_test = ['freemium', 'starter', 'basic', 'pro']
    expected_support = {
        'freemium': False,
        'starter': False,
        'basic': True,
        'pro': True
    }
    
    for plan in plans_to_test:
        # Обновляем план пользователя
        manager.upgrade_subscription(user_id, plan)
        subscription = manager.get_user_subscription(user_id)
        limits = subscription['limits']
        
        expected = expected_support[plan]
        
        assert limits.pptx_support == expected, f"План {plan} должен иметь pptx_support={expected}"
        
        status = "✅ поддерживает" if expected else "❌ не поддерживает"
        print(f"✅ {plan.upper()}: {status} PPTX")
    
    # Тест 2: Проверка функции check_pptx_support
    print("\n=== Тест 2: Проверка функции check_pptx_support ===")
    
    # Тестируем FREEMIUM план (PPTX недоступен)
    manager.upgrade_subscription(user_id, 'freemium')
    
    can_upload, message = manager.check_pptx_support(user_id)
    assert can_upload == False, "FREEMIUM план не должен поддерживать PPTX"
    assert "BASIC и PRO" in message, "Сообщение должно упоминать планы BASIC и PRO"
    print("✅ FREEMIUM: PPTX заблокирован")
    print(f"   Сообщение: {message}")
    
    # Тестируем STARTER план (PPTX недоступен)
    manager.upgrade_subscription(user_id, 'starter')
    
    can_upload, message = manager.check_pptx_support(user_id)
    assert can_upload == False, "STARTER план не должен поддерживать PPTX"
    assert "BASIC и PRO" in message, "Сообщение должно упоминать планы BASIC и PRO"
    print("✅ STARTER: PPTX заблокирован")
    
    # Тестируем BASIC план (PPTX доступен)
    manager.upgrade_subscription(user_id, 'basic')
    
    can_upload, message = manager.check_pptx_support(user_id)
    assert can_upload == True, "BASIC план должен поддерживать PPTX"
    assert message == "", "Для разрешенного плана сообщение должно быть пустым"
    print("✅ BASIC: PPTX разрешен")
    
    # Тестируем PRO план (PPTX доступен)
    manager.upgrade_subscription(user_id, 'pro')
    
    can_upload, message = manager.check_pptx_support(user_id)
    assert can_upload == True, "PRO план должен поддерживать PPTX"
    assert message == "", "Для разрешенного плана сообщение должно быть пустым"
    print("✅ PRO: PPTX разрешен")
    
    # Тест 3: Проверка конфигурации планов
    print("\n=== Тест 3: Проверка конфигурации планов ===")
    
    # Проверяем конфигурацию напрямую
    freemium_limits = SUBSCRIPTION_PLANS['freemium']
    starter_limits = SUBSCRIPTION_PLANS['starter']
    basic_limits = SUBSCRIPTION_PLANS['basic']
    pro_limits = SUBSCRIPTION_PLANS['pro']
    
    assert freemium_limits.pptx_support == False, "FREEMIUM должен иметь pptx_support=False"
    assert starter_limits.pptx_support == False, "STARTER должен иметь pptx_support=False"
    assert basic_limits.pptx_support == True, "BASIC должен иметь pptx_support=True"
    assert pro_limits.pptx_support == True, "PRO должен иметь pptx_support=True"
    
    print("✅ Конфигурация планов корректна:")
    print(f"   FREEMIUM: pptx_support={freemium_limits.pptx_support}")
    print(f"   STARTER: pptx_support={starter_limits.pptx_support}")
    print(f"   BASIC: pptx_support={basic_limits.pptx_support}")
    print(f"   PRO: pptx_support={pro_limits.pptx_support}")
    
    # Тест 4: Проверка обновления плана для доступа к PPTX
    print("\n=== Тест 4: Обновление плана для доступа к PPTX ===")
    
    # Начинаем с FREEMIUM (PPTX недоступен)
    manager.upgrade_subscription(user_id, 'freemium')
    can_upload_before, _ = manager.check_pptx_support(user_id)
    assert can_upload_before == False, "FREEMIUM не должен поддерживать PPTX"
    
    # Обновляемся до BASIC (PPTX становится доступен)
    manager.upgrade_subscription(user_id, 'basic')
    can_upload_after, _ = manager.check_pptx_support(user_id)
    assert can_upload_after == True, "BASIC должен поддерживать PPTX"
    
    print("✅ Обновление FREEMIUM → BASIC: PPTX стал доступен")
    
    # Проверяем обновление STARTER → PRO
    manager.upgrade_subscription(user_id, 'starter')
    can_upload_starter, _ = manager.check_pptx_support(user_id)
    assert can_upload_starter == False, "STARTER не должен поддерживать PPTX"
    
    manager.upgrade_subscription(user_id, 'pro')
    can_upload_pro, _ = manager.check_pptx_support(user_id)
    assert can_upload_pro == True, "PRO должен поддерживать PPTX"
    
    print("✅ Обновление STARTER → PRO: PPTX стал доступен")
    
    # Очистка тестовых данных
    conn = sqlite3.connect('ai_study.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE email = 'pptx_test@example.com'")
    conn.commit()
    conn.close()
    
    print("\n" + "=" * 50)
    print("🎉 Все тесты поддержки PPTX пройдены успешно!")
    print("\n📊 Результаты тестирования:")
    print("✅ Поддержка PPTX корректно настроена для всех планов")
    print("✅ Функция проверки поддержки работает правильно")
    print("✅ Конфигурация планов соответствует требованиям")
    print("✅ Обновление планов корректно изменяет доступ к PPTX")
    
    print("\n🚀 Система ограничений PPTX готова к продакшену!")
    
    return True

def test_pptx_edge_cases():
    """Тестирует граничные случаи для поддержки PPTX"""
    print("\n🔍 Тестирование граничных случаев PPTX")
    print("-" * 40)
    
    manager = SubscriptionManager()
    
    # Тест с несуществующим пользователем
    can_upload, message = manager.check_pptx_support(99999)
    assert can_upload == False, "Несуществующий пользователь не должен иметь доступ"
    assert "не найдена" in message, "Должно быть сообщение о том, что подписка не найдена"
    print("✅ Несуществующий пользователь корректно обработан")
    
    print("✅ Граничные случаи обработаны корректно")

if __name__ == "__main__":
    try:
        # Основные тесты поддержки PPTX
        test_pptx_support()
        
        # Тесты граничных случаев
        test_pptx_edge_cases()
        
        print("\n" + "📄" * 20)
        print("🎉 ВСЕ ТЕСТЫ ПОДДЕРЖКИ PPTX ПРОЙДЕНЫ УСПЕШНО!")
        print("🚀 Система готова к использованию в продакшене!")
        print("📄" * 20)
        
    except Exception as e:
        print(f"\n❌ Ошибка в тестах: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)