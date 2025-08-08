#!/usr/bin/env python3
"""
Простой тест лимита AI чата без Flask test client
"""
import sys
import os

# Добавляем путь к модулям
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_simple_ai_chat_limit():
    """Простое тестирование лимита AI чата"""
    print("🧪 Простой тест лимита AI чата")
    print("=" * 50)
    
    try:
        from auth import User
        from subscription_manager import subscription_manager
        
        # Создаем тестового пользователя
        test_user = User.create("simple_chat_test@example.com", "Simple Chat Test", "password123")
        if not test_user:
            test_user = User.get_by_email("simple_chat_test@example.com")
        
        user_id = test_user.id
        print(f"👤 Тестовый пользователь: {test_user.email} (ID: {user_id})")
        
        # Устанавливаем план STARTER (лимит 5 сообщений)
        success = subscription_manager.upgrade_subscription(user_id, 'starter')
        print(f"✅ План STARTER установлен: {success}")
        
        # Сбрасываем счетчик использования AI чата
        import sqlite3
        conn = sqlite3.connect('ai_study.db')
        c = conn.cursor()
        c.execute('UPDATE users SET ai_chat_messages_used = 0 WHERE id = ?', (user_id,))
        conn.commit()
        conn.close()
        print("🔄 Счетчик AI чата сброшен")
        
        print("\n💬 Тестирование лимита AI чата:")
        print("-" * 40)
        
        # Тестируем 5 сообщений (должны пройти)
        for i in range(1, 6):
            allowed, message = subscription_manager.check_ai_chat_limit(user_id)
            if allowed:
                # Записываем использование
                subscription_manager.record_usage(user_id, 'ai_chat', 1, f'test_message_{i}')
                print(f"✅ Сообщение {i}/5: разрешено")
            else:
                print(f"❌ Сообщение {i}/5: запрещено - {message}")
        
        # Получаем статистику использования
        usage_stats = subscription_manager.get_usage_stats(user_id)
        print(f"\n📊 Статистика после 5 сообщений:")
        print(f"   Использовано: {usage_stats['ai_chat']['used']}")
        print(f"   Лимит: {usage_stats['ai_chat']['limit']}")
        
        # Пытаемся отправить 6-е сообщение (должно быть запрещено)
        print(f"\n🚫 Тестирование превышения лимита:")
        print("-" * 40)
        
        allowed, message = subscription_manager.check_ai_chat_limit(user_id)
        if allowed:
            print(f"❌ 6-е сообщение: неожиданно разрешено!")
        else:
            print(f"✅ 6-е сообщение: корректно запрещено")
            print(f"   Сообщение: {message}")
        
        # Финальная проверка статистики
        usage_stats = subscription_manager.get_usage_stats(user_id)
        print(f"\n📊 Финальная статистика:")
        print(f"   Использовано: {usage_stats['ai_chat']['used']}")
        print(f"   Лимит: {usage_stats['ai_chat']['limit']}")
        print(f"   Превышен: {usage_stats['ai_chat']['used'] >= usage_stats['ai_chat']['limit']}")
        
        # Тестируем логику проверки лимита напрямую
        print(f"\n🔍 Прямая проверка логики:")
        print("-" * 40)
        
        subscription = subscription_manager.get_user_subscription(user_id)
        used = subscription['ai_chat_messages_used']
        limit = subscription['limits'].ai_chat_messages
        
        print(f"   Использовано из БД: {used}")
        print(f"   Лимит из конфигурации: {limit}")
        print(f"   Условие used >= limit: {used} >= {limit} = {used >= limit}")
        print(f"   Должно быть запрещено: {used >= limit}")
        
        print(f"\n🎉 Тест завершен!")
        return user_id
        
    except Exception as e:
        print(f"\n❌ Ошибка в тесте: {e}")
        import traceback
        traceback.print_exc()
        return None

def cleanup_simple_test(user_id):
    """Очистка тестовых данных"""
    if not user_id:
        return
        
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
    user_id = test_simple_ai_chat_limit()
    
    if user_id:
        cleanup = input("\nОчистить тестовые данные? (y/n): ").lower().strip()
        if cleanup in ['y', 'yes', 'да']:
            cleanup_simple_test(user_id)