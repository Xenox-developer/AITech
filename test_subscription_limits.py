#!/usr/bin/env python3
"""
Тестирование системы ограничений подписки
"""
import sqlite3
import sys
import os
from datetime import datetime, timedelta

# Добавляем путь к модулям
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from subscription_manager import subscription_manager, SUBSCRIPTION_PLANS
from auth import User

def test_subscription_limits():
    """Тестирование ограничений подписки"""
    print("🧪 Тестирование системы ограничений подписки")
    print("=" * 50)
    
    # Создаем тестового пользователя
    test_user = User.create("test_limits@example.com", "Test User", "password123")
    if not test_user:
        # Пользователь уже существует, получаем его
        test_user = User.get_by_email("test_limits@example.com")
    
    user_id = test_user.id
    print(f"👤 Тестовый пользователь: {test_user.email} (ID: {user_id})")
    
    # Тестируем планы подписки
    for plan_name, limits in SUBSCRIPTION_PLANS.items():
        print(f"\n📋 Тестирование плана: {plan_name.upper()}")
        print("-" * 30)
        
        # Обновляем план пользователя
        success = subscription_manager.upgrade_subscription(user_id, plan_name)
        print(f"✅ План обновлен: {success}")
        
        # Получаем информацию о подписке
        subscription = subscription_manager.get_user_subscription(user_id)
        print(f"📊 Текущий план: {subscription['type']}")
        
        # Тестируем лимит анализов
        print(f"🔍 Лимит анализов: {limits.monthly_analyses if limits.monthly_analyses != -1 else 'безлимитно'}")
        allowed, message = subscription_manager.check_analysis_limit(user_id)
        print(f"   Разрешен анализ: {allowed}")
        if message:
            print(f"   Сообщение: {message}")
        
        # Тестируем лимит PDF страниц
        test_pages = [5, 20, 50, 100]
        for pages in test_pages:
            allowed, message = subscription_manager.check_pdf_pages_limit(user_id, pages)
            status = "✅" if allowed else "❌"
            print(f"   PDF {pages} страниц: {status}")
        
        # Тестируем лимит видео
        test_minutes = [10, 60, 120, 180]
        for minutes in test_minutes:
            allowed, message = subscription_manager.check_video_duration_limit(user_id, minutes)
            status = "✅" if allowed else "❌"
            print(f"   Видео {minutes} мин: {status}")
        
        # Тестируем лимит AI чата
        allowed, message = subscription_manager.check_ai_chat_limit(user_id)
        print(f"   AI чат разрешен: {'✅' if allowed else '❌'}")
        
        # Тестируем доступ к функциям
        test_features = ['basic_flashcards', 'advanced_flashcards', 'mind_maps', 'interactive_mind_maps', 'api_access']
        print("   Доступные функции:")
        for feature in test_features:
            has_access = subscription_manager.check_feature_access(user_id, feature)
            status = "✅" if has_access else "❌"
            print(f"     {feature}: {status}")
    
    # Тестируем запись использования
    print(f"\n📈 Тестирование записи использования")
    print("-" * 30)
    
    # Записываем использование
    subscription_manager.record_usage(user_id, 'analysis', 1, 'test_file.pdf')
    subscription_manager.record_usage(user_id, 'pdf_pages', 10, 'test_file.pdf')
    subscription_manager.record_usage(user_id, 'ai_chat', 5, 'test_conversation')
    
    # Получаем статистику использования
    usage_stats = subscription_manager.get_usage_stats(user_id)
    print(f"✅ Статистика использования получена")
    print(f"   Анализы: {usage_stats['analyses']['used']}/{usage_stats['analyses']['limit'] if not usage_stats['analyses']['unlimited'] else '∞'}")
    print(f"   AI чат: {usage_stats['ai_chat']['used']}/{usage_stats['ai_chat']['limit'] if not usage_stats['ai_chat']['unlimited'] else '∞'}")
    
    print(f"\n🎉 Тестирование завершено успешно!")

def cleanup_test_data():
    """Очистка тестовых данных"""
    print("\n🧹 Очистка тестовых данных...")
    
    conn = sqlite3.connect('ai_study.db')
    c = conn.cursor()
    
    try:
        # Удаляем тестового пользователя и связанные данные
        c.execute('DELETE FROM subscription_usage WHERE user_id IN (SELECT id FROM users WHERE email = ?)', 
                 ('test_limits@example.com',))
        c.execute('DELETE FROM subscription_history WHERE user_id IN (SELECT id FROM users WHERE email = ?)', 
                 ('test_limits@example.com',))
        c.execute('DELETE FROM users WHERE email = ?', ('test_limits@example.com',))
        
        conn.commit()
        print("✅ Тестовые данные очищены")
        
    except Exception as e:
        print(f"❌ Ошибка при очистке: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == '__main__':
    try:
        test_subscription_limits()
        
        # Спрашиваем пользователя о очистке данных
        cleanup = input("\nОчистить тестовые данные? (y/n): ").lower().strip()
        if cleanup in ['y', 'yes', 'да']:
            cleanup_test_data()
        
    except Exception as e:
        print(f"❌ Ошибка при тестировании: {e}")
        import traceback
        traceback.print_exc()