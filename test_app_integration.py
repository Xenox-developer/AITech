#!/usr/bin/env python3
"""
Интеграционный тест системы ограничений в приложении
"""
import sys
import os
from flask import Flask
from flask_login import login_user

# Добавляем путь к модулям
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_app_integration():
    """Тестирование интеграции системы ограничений с приложением"""
    print("🧪 Интеграционный тест системы ограничений")
    print("=" * 50)
    
    try:
        # Импортируем приложение
        from app import app, init_db
        from auth import User
        from subscription_manager import subscription_manager
        
        print("✅ Приложение успешно импортировано")
        
        # Инициализируем базу данных
        init_db()
        print("✅ База данных инициализирована")
        
        # Создаем тестового пользователя
        test_user = User.create("integration_test@example.com", "Integration Test", "password123")
        if not test_user:
            test_user = User.get_by_email("integration_test@example.com")
        
        print(f"✅ Тестовый пользователь создан: {test_user.email}")
        
        # Тестируем контекст приложения
        with app.test_client() as client:
            with app.test_request_context():
                print("✅ Контекст приложения создан")
                
                # Тестируем доступ к странице планов
                response = client.get('/pricing')
                print(f"✅ Страница планов доступна: {response.status_code == 200}")
                
                # Тестируем API статуса подписки (без авторизации)
                response = client.get('/subscription_status')
                print(f"✅ API требует авторизацию: {response.status_code == 302}")  # Редирект на логин
                
                # Тестируем менеджер подписок
                subscription = subscription_manager.get_user_subscription(test_user.id)
                print(f"✅ Подписка пользователя получена: {subscription['type'] if subscription else 'None'}")
                
                # Тестируем проверку лимитов
                allowed, message = subscription_manager.check_analysis_limit(test_user.id)
                print(f"✅ Проверка лимита анализов: {allowed}")
                
                # Тестируем запись использования
                subscription_manager.record_usage(test_user.id, 'analysis', 1, 'test_integration.pdf')
                print("✅ Использование записано")
                
                # Тестируем статистику
                usage_stats = subscription_manager.get_usage_stats(test_user.id)
                print(f"✅ Статистика получена: план {usage_stats['plan'] if usage_stats else 'None'}")
        
        print("\n🎉 Все интеграционные тесты прошли успешно!")
        return True
        
    except Exception as e:
        print(f"\n❌ Ошибка в интеграционном тесте: {e}")
        import traceback
        traceback.print_exc()
        return False

def cleanup_integration_test():
    """Очистка данных интеграционного теста"""
    try:
        import sqlite3
        conn = sqlite3.connect('ai_study.db')
        c = conn.cursor()
        
        # Удаляем тестовые данные
        c.execute('DELETE FROM subscription_usage WHERE user_id IN (SELECT id FROM users WHERE email = ?)', 
                 ('integration_test@example.com',))
        c.execute('DELETE FROM users WHERE email = ?', ('integration_test@example.com',))
        
        conn.commit()
        conn.close()
        print("✅ Тестовые данные очищены")
        
    except Exception as e:
        print(f"❌ Ошибка при очистке: {e}")

if __name__ == '__main__':
    success = test_app_integration()
    
    if success:
        cleanup = input("\nОчистить тестовые данные? (y/n): ").lower().strip()
        if cleanup in ['y', 'yes', 'да']:
            cleanup_integration_test()
    
    sys.exit(0 if success else 1)