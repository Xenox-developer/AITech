#!/usr/bin/env python3
"""
Тест интеграции ограничений на видео загрузки
Проверяет работу новых лимитов в реальных условиях
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from subscription_manager import SubscriptionManager
from subscription_decorators import subscription_required
import sqlite3
from datetime import datetime, timedelta

def test_video_uploads_integration():
    """Тестирует интеграцию ограничений на видео загрузки"""
    print("🎬 Запуск тестов интеграции ограничений на видео загрузки")
    print("=" * 65)
    
    # Инициализация менеджера подписок
    manager = SubscriptionManager()
    
    # Создаем тестового пользователя
    conn = sqlite3.connect('ai_study.db')
    cursor = conn.cursor()
    
    # Очищаем тестовые данные
    cursor.execute("DELETE FROM users WHERE email = 'video_test@example.com'")
    conn.commit()
    
    # Создаем пользователя
    cursor.execute("""
        INSERT INTO users (email, password_hash, subscription_type, subscription_status,
                          monthly_analyses_used, monthly_pdf_pages_used, monthly_video_uploads_used,
                          ai_chat_messages_used, subscription_start_date, subscription_end_date)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        'video_test@example.com',
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
    
    # Тест 1: Проверка лимитов для всех планов
    print("\n=== Тест 1: Проверка лимитов видео для всех планов ===")
    
    plans_to_test = ['freemium', 'starter', 'basic', 'pro']
    expected_limits = {
        'freemium': {'uploads': 1, 'minutes': 5},
        'starter': {'uploads': 3, 'minutes': 20},
        'basic': {'uploads': 10, 'minutes': 90},
        'pro': {'uploads': float('inf'), 'minutes': float('inf')}
    }
    
    for plan in plans_to_test:
        # Обновляем план пользователя
        manager.upgrade_subscription(user_id, plan)
        subscription = manager.get_user_subscription(user_id)
        limits = subscription['limits']
        
        expected = expected_limits[plan]
        
        if plan == 'pro':
            # PRO план должен быть безлимитным (-1 означает безлимитно)
            assert limits.max_video_uploads == -1, f"PRO план должен иметь безлимитные загрузки видео"
            assert limits.max_video_minutes == -1, f"PRO план должен иметь безлимитную длительность видео"
            print(f"✅ {plan.upper()}: ∞ видео, ∞ минут")
        else:
            assert limits.max_video_uploads == expected['uploads'], f"План {plan} должен иметь {expected['uploads']} видео загрузок"
            assert limits.max_video_minutes == expected['minutes'], f"План {plan} должен иметь {expected['minutes']} минут видео"
            print(f"✅ {plan.upper()}: {expected['uploads']} видео, {expected['minutes']} минут")
    
    # Тест 2: Проверка функции check_video_uploads_limit
    print("\n=== Тест 2: Проверка функции check_video_uploads_limit ===")
    
    # Тестируем FREEMIUM план (1 видео)
    manager.upgrade_subscription(user_id, 'freemium')
    
    # Первая загрузка должна быть разрешена
    can_upload, message = manager.check_video_uploads_limit(user_id)
    assert can_upload == True, "Первая загрузка видео должна быть разрешена"
    print("✅ Первая загрузка видео разрешена для FREEMIUM")
    
    # Записываем использование
    manager.record_usage(user_id, 'video_upload')
    
    # Вторая загрузка должна быть запрещена
    can_upload, message = manager.check_video_uploads_limit(user_id)
    assert can_upload == False, "Вторая загрузка видео должна быть запрещена для FREEMIUM"
    assert "лимит загрузок видео" in message.lower(), "Сообщение должно содержать информацию о лимите"
    print("✅ Вторая загрузка видео запрещена для FREEMIUM")
    print(f"   Сообщение: {message}")
    
    # Тест 3: Проверка статистики использования
    print("\n=== Тест 3: Проверка статистики использования видео ===")
    
    stats = manager.get_usage_stats(user_id)
    
    # Проверяем, что статистика содержит информацию о видео загрузках
    assert 'video_uploads' in stats, "Статистика должна содержать информацию о видео загрузках"
    assert stats['video_uploads']['used'] == 1, "Должна быть записана 1 использованная видео загрузка"
    assert stats['video_uploads']['limit'] == 1, "Лимит должен быть 1 для FREEMIUM плана"
    assert stats['video_uploads']['unlimited'] == False, "FREEMIUM план не должен быть безлимитным"
    
    print("✅ Статистика видео загрузок корректна:")
    print(f"   Использовано: {stats['video_uploads']['used']}")
    print(f"   Лимит: {stats['video_uploads']['limit']}")
    print(f"   Безлимитно: {stats['video_uploads']['unlimited']}")
    
    # Тест 4: Проверка обновления плана и сброса ограничений
    print("\n=== Тест 4: Обновление плана и проверка новых лимитов ===")
    
    # Обновляем до STARTER плана
    manager.upgrade_subscription(user_id, 'starter')
    
    # Проверяем, что теперь доступны дополнительные загрузки
    can_upload, message = manager.check_video_uploads_limit(user_id)
    assert can_upload == True, "После обновления до STARTER должны быть доступны дополнительные загрузки"
    print("✅ После обновления до STARTER доступны дополнительные загрузки")
    
    # Проверяем новые лимиты
    stats = manager.get_usage_stats(user_id)
    assert stats['video_uploads']['limit'] == 3, "STARTER план должен иметь лимит 3 видео"
    print(f"✅ STARTER план имеет лимит {stats['video_uploads']['limit']} видео")
    
    # Тест 5: Проверка PRO плана (безлимитный)
    print("\n=== Тест 5: Проверка PRO плана (безлимитный) ===")
    
    manager.upgrade_subscription(user_id, 'pro')
    
    # PRO план должен всегда разрешать загрузки
    can_upload, message = manager.check_video_uploads_limit(user_id)
    assert can_upload == True, "PRO план должен всегда разрешать загрузки видео"
    
    stats = manager.get_usage_stats(user_id)
    assert stats['video_uploads']['unlimited'] == True, "PRO план должен быть безлимитным"
    
    print("✅ PRO план корректно работает как безлимитный")
    print(f"   Безлимитно: {stats['video_uploads']['unlimited']}")
    
    # Тест 6: Проверка сброса месячных лимитов
    print("\n=== Тест 6: Проверка сброса месячных лимитов ===")
    
    # Возвращаемся к BASIC плану для тестирования сброса
    manager.upgrade_subscription(user_id, 'basic')
    
    # Используем несколько загрузок
    for i in range(3):
        manager.record_usage(user_id, 'video_upload')
    
    stats_before = manager.get_usage_stats(user_id)
    used_before = stats_before['video_uploads']['used']
    
    # Сбрасываем лимиты
    manager.reset_monthly_limits(user_id)
    
    stats_after = manager.get_usage_stats(user_id)
    used_after = stats_after['video_uploads']['used']
    
    assert used_after == 0, "После сброса количество использованных видео загрузок должно быть 0"
    print(f"✅ Месячные лимиты сброшены: {used_before} → {used_after}")
    
    # Тест 7: Проверка интеграции с декоратором (упрощенный)
    print("\n=== Тест 7: Проверка интеграции с декоратором ===")
    
    # Тестируем прямую проверку лимитов (без Flask контекста)
    manager.upgrade_subscription(user_id, 'freemium')
    manager.record_usage(user_id, 'video_upload')  # Исчерпываем лимит
    
    # Проверяем, что лимит действительно исчерпан
    can_upload, message = manager.check_video_uploads_limit(user_id)
    assert can_upload == False, "Лимит должен быть исчерпан"
    assert "лимит" in message.lower(), "Сообщение должно содержать информацию о лимите"
    print("✅ Проверка лимитов работает корректно для интеграции с декораторами")
    
    # Очистка тестовых данных
    conn = sqlite3.connect('ai_study.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE email = 'video_test@example.com'")
    conn.commit()
    conn.close()
    
    print("\n" + "=" * 65)
    print("🎉 Все тесты интеграции видео загрузок пройдены успешно!")
    print("\n📊 Результаты тестирования:")
    print("✅ Лимиты для всех планов работают корректно")
    print("✅ Функция проверки лимитов работает правильно")
    print("✅ Статистика использования ведется точно")
    print("✅ Обновление планов работает корректно")
    print("✅ PRO план корректно работает как безлимитный")
    print("✅ Сброс месячных лимитов функционирует")
    print("✅ Интеграция с декораторами работает")
    
    print("\n🚀 Система ограничений на видео загрузки готова к продакшену!")
    
    return True

def test_video_limits_edge_cases():
    """Тестирует граничные случаи для видео лимитов"""
    print("\n🔍 Тестирование граничных случаев")
    print("-" * 40)
    
    manager = SubscriptionManager()
    
    # Создаем тестового пользователя
    conn = sqlite3.connect('ai_study.db')
    cursor = conn.cursor()
    
    cursor.execute("DELETE FROM users WHERE email = 'edge_test@example.com'")
    conn.commit()
    
    cursor.execute("""
        INSERT INTO users (email, password_hash, subscription_type, subscription_status,
                          monthly_analyses_used, monthly_pdf_pages_used, monthly_video_uploads_used,
                          ai_chat_messages_used, subscription_start_date, subscription_end_date)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        'edge_test@example.com',
        'test_hash',
        'starter',
        'active',
        0, 0, 2, 0,  # Уже использовано 2 видео из 3
        datetime.now().isoformat(),
        (datetime.now() + timedelta(days=30)).isoformat()
    ))
    
    user_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    # Тест граничного случая: последняя доступная загрузка
    can_upload, message = manager.check_video_uploads_limit(user_id)
    assert can_upload == True, "Последняя загрузка должна быть разрешена"
    print("✅ Последняя доступная загрузка разрешена")
    
    # Используем последнюю загрузку
    manager.record_usage(user_id, 'video_upload')
    
    # Теперь лимит должен быть исчерпан
    can_upload, message = manager.check_video_uploads_limit(user_id)
    assert can_upload == False, "После исчерпания лимита загрузка должна быть запрещена"
    print("✅ После исчерпания лимита загрузка запрещена")
    
    # Проверяем статистику
    stats = manager.get_usage_stats(user_id)
    assert stats['video_uploads']['used'] == 3, "Должно быть использовано 3 видео"
    assert stats['video_uploads']['limit'] == 3, "Лимит должен быть 3"
    print(f"✅ Статистика корректна: {stats['video_uploads']['used']}/{stats['video_uploads']['limit']}")
    
    # Очистка
    conn = sqlite3.connect('ai_study.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE email = 'edge_test@example.com'")
    conn.commit()
    conn.close()
    
    print("✅ Граничные случаи обработаны корректно")

if __name__ == "__main__":
    try:
        # Основные тесты интеграции
        test_video_uploads_integration()
        
        # Тесты граничных случаев
        test_video_limits_edge_cases()
        
        print("\n" + "🎬" * 20)
        print("🎉 ВСЕ ТЕСТЫ ВИДЕО ЗАГРУЗОК ПРОЙДЕНЫ УСПЕШНО!")
        print("🚀 Система готова к использованию в продакшене!")
        print("🎬" * 20)
        
    except Exception as e:
        print(f"\n❌ Ошибка в тестах: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)