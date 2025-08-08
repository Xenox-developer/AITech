#!/usr/bin/env python3
"""
Тест исправления проблемы с превышением лимита AI чата
"""
import sys
import os
import json

# Добавляем путь к модулям
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_ai_chat_limit_fix():
    """Тестирование исправления лимита AI чата"""
    print("🧪 Тест исправления лимита AI чата")
    print("=" * 50)
    
    try:
        from app import app
        from auth import User
        from subscription_manager import subscription_manager
        
        # Создаем тестового пользователя
        test_user = User.create("chat_limit_fix@example.com", "Chat Limit Fix", "password123")
        if not test_user:
            test_user = User.get_by_email("chat_limit_fix@example.com")
        
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
        
        # Создаем тестовый результат для чата напрямую в БД
        conn = sqlite3.connect('ai_study.db')
        c = conn.cursor()
        c.execute('''
            INSERT INTO result (filename, file_type, topics_json, summary, flashcards_json, 
                              full_text, user_id, access_token)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', ('test_chat.txt', '.txt', '[]', 'Test summary', '[]', 
              'Это тестовый документ для проверки AI чата.', user_id, 'test_token_123'))
        
        result_id = c.lastrowid
        conn.commit()
        conn.close()
        
        print(f"📄 Тестовый результат создан: ID {result_id}")
        
        # Тестируем API чата с помощью test_client
        with app.test_client() as client:
            with app.test_request_context():
                # Имитируем авторизацию пользователя
                with client.session_transaction() as sess:
                    sess['_user_id'] = str(user_id)
                    sess['_fresh'] = True
                
                print("\n💬 Тестирование лимита AI чата:")
                print("-" * 40)
                
                # Отправляем 5 сообщений (должны пройти)
                for i in range(1, 6):
                    response = client.post(f'/api/chat/{result_id}', 
                                         json={'message': f'Тестовое сообщение {i}'},
                                         content_type='application/json')
                    
                    if response.status_code == 200:
                        print(f"✅ Сообщение {i}/5: разрешено (статус: {response.status_code})")
                    else:
                        data = response.get_json() if response.is_json else {}
                        print(f"❌ Сообщение {i}/5: запрещено (статус: {response.status_code})")
                        print(f"   Ошибка: {data.get('error', 'Неизвестная ошибка')}")
                
                # Проверяем статистику использования
                usage_stats = subscription_manager.get_usage_stats(user_id)
                print(f"\n📊 Статистика после 5 сообщений:")
                print(f"   Использовано: {usage_stats['ai_chat']['used']}")
                print(f"   Лимит: {usage_stats['ai_chat']['limit']}")
                
                # Пытаемся отправить 6-е сообщение (должно быть запрещено)
                print(f"\n🚫 Тестирование превышения лимита:")
                print("-" * 40)
                
                response = client.post(f'/api/chat/{result_id}', 
                                     json={'message': 'Шестое сообщение - должно быть запрещено'},
                                     content_type='application/json')
                
                if response.status_code == 403:
                    data = response.get_json()
                    print(f"✅ 6-е сообщение корректно запрещено (статус: {response.status_code})")
                    print(f"   Сообщение: {data.get('error', 'Нет сообщения')}")
                    print(f"   Лимит превышен: {data.get('limit_exceeded', False)}")
                    print(f"   Требуется обновление: {data.get('upgrade_required', False)}")
                else:
                    print(f"❌ 6-е сообщение неожиданно разрешено (статус: {response.status_code})")
                    if response.is_json:
                        print(f"   Ответ: {response.get_json()}")
                
                # Финальная проверка статистики
                usage_stats = subscription_manager.get_usage_stats(user_id)
                print(f"\n📊 Финальная статистика:")
                print(f"   Использовано: {usage_stats['ai_chat']['used']}")
                print(f"   Лимит: {usage_stats['ai_chat']['limit']}")
                print(f"   Превышен: {usage_stats['ai_chat']['used'] >= usage_stats['ai_chat']['limit']}")
        
        print(f"\n🎉 Тест завершен!")
        return user_id, result_id
        
    except Exception as e:
        print(f"\n❌ Ошибка в тесте: {e}")
        import traceback
        traceback.print_exc()
        return None, None

def cleanup_test_data(user_id, result_id):
    """Очистка тестовых данных"""
    if not user_id:
        return
        
    import sqlite3
    
    print("\n🧹 Очистка тестовых данных...")
    
    conn = sqlite3.connect('ai_study.db')
    c = conn.cursor()
    
    try:
        # Удаляем тестовые данные
        if result_id:
            c.execute('DELETE FROM chat_history WHERE result_id = ?', (result_id,))
            c.execute('DELETE FROM result WHERE id = ?', (result_id,))
        
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
    user_id, result_id = test_ai_chat_limit_fix()
    
    if user_id:
        cleanup = input("\nОчистить тестовые данные? (y/n): ").lower().strip()
        if cleanup in ['y', 'yes', 'да']:
            cleanup_test_data(user_id, result_id)