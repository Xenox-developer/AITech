#!/usr/bin/env python3
"""
Тест лимита AI чата для плана STARTER (5 сообщений)
"""
import sys
import os

# Добавляем путь к модулям
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from subscription_manager import subscription_manager
from auth import User

def test_starter_ai_chat_limit():
    """Тестирование лимита AI чата для плана STARTER"""
    print("🧪 Тест лимита AI чата для плана STARTER")
    print("=" * 50)
    
    # Создаем тестового пользователя
    test_user = User.create("starter_chat_test@example.com", "Starter Chat Test", "password123")
    if not test_user:
        test_user = User.get_by_email("starter_chat_test@example.com")
    
    user_id = test_user.id
    print(f"👤 Тестовый пользователь: {test_user.email} (ID: {user_id})")
    
    # Устанавливаем план STARTER
    success = subscription_manager.upgrade_subscription(user_id, 'starter')
    print(f"✅ План STARTER установлен: {success}")
    
    # Получаем информацию о подписке
    subscription = subscription_manager.get_user_subscription(user_id)
    print(f"📊 Текущий план: {subscription['type']}")
    print(f"🔢 Лимит AI чата: {subscription['limits'].ai_chat_messages}")
    
    # Тестируем лимит AI чата (должно быть 5 сообщений)
    print(f"\n💬 Тестирование лимита AI чата (5 сообщений):")
    print("-" * 40)
    
    # Отправляем 5 сообщений (должны пройти)
    for i in range(1, 6):
        allowed, message = subscription_manager.check_ai_chat_limit(user_id)
        if allowed:
            subscription_manager.record_usage(user_id, 'ai_chat', 1, f'test_message_{i}')
            print(f"✅ Сообщение {i}/5: разрешено")
        else:
            print(f"❌ Сообщение {i}/5: запрещено - {message}")
    
    # Получаем статистику использования
    usage_stats = subscription_manager.get_usage_stats(user_id)
    print(f"\n📊 Статистика использования:")
    print(f"   Использовано: {usage_stats['ai_chat']['used']}")
    print(f"   Лимит: {usage_stats['ai_chat']['limit']}")
    print(f"   Безлимитно: {usage_stats['ai_chat']['unlimited']}")
    
    # Пытаемся отправить 6-е сообщение (должно быть запрещено)
    print(f"\n🚫 Тестирование превышения лимита:")
    print("-" * 40)
    
    allowed, message = subscription_manager.check_ai_chat_limit(user_id)
    if allowed:
        print(f"❌ 6-е сообщение: неожиданно разрешено!")
    else:
        print(f"✅ 6-е сообщение: корректно запрещено")
        print(f"   Сообщение: {message}")
    
    # Сравниваем с другими планами
    print(f"\n📋 Сравнение лимитов AI чата по планам:")
    print("-" * 40)
    
    from subscription_manager import SUBSCRIPTION_PLANS
    for plan_name, limits in SUBSCRIPTION_PLANS.items():
        chat_limit = "безлимитно" if limits.ai_chat_messages == -1 else f"{limits.ai_chat_messages} сообщений"
        print(f"   {plan_name.upper()}: {chat_limit}")
    
    print(f"\n🎉 Тест завершен успешно!")
    return user_id

def cleanup_starter_test(user_id):
    """Очистка тестовых данных"""
    import sqlite3
    
    print("\n🧹 Очистка тестовых данных...")
    
    conn = sqlite3.connect('ai_study.db')
    c = conn.cursor()
    
    try:
        # Удаляем тестовые данные
        c.execute('DELETE FROM subscription_usage WHERE user_id = ?', (user_id,))
        c.execute('DELETE FROM subscription_history WHERE user_id = ?', (user_id,))
        c.execute('DELETE FROM users WHERE id = ?', (user_id,))
        
        conn.commit()
        print("✅ Тестовые данные очищены")
        
    except Exception as e:
        print(f"❌ Ошибка при очистке: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == '__main__':
    try:
        user_id = test_starter_ai_chat_limit()
        
        # Спрашиваем пользователя о очистке данных
        cleanup = input("\nОчистить тестовые данные? (y/n): ").lower().strip()
        if cleanup in ['y', 'yes', 'да']:
            cleanup_starter_test(user_id)
        
    except Exception as e:
        print(f"❌ Ошибка при тестировании: {e}")
        import traceback
        traceback.print_exc()