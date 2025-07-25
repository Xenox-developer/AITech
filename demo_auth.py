#!/usr/bin/env python3
"""
Демонстрация системы аутентификации
"""
import sqlite3
import hashlib
import secrets
from datetime import datetime

def generate_password_hash(password):
    """Генерация хеша пароля"""
    salt = secrets.token_hex(16)
    password_hash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), 100000)
    return salt + password_hash.hex()

def create_demo_users():
    """Создание демонстрационных пользователей"""
    print("👥 Создание демонстрационных пользователей...")
    
    demo_users = [
        {
            'email': 'admin@ai-konspekt.ru',
            'username': 'Администратор',
            'password': 'admin123',
            'subscription_type': 'premium'
        },
        {
            'email': 'student@example.com',
            'username': 'Студент',
            'password': 'student123',
            'subscription_type': 'free'
        },
        {
            'email': 'teacher@university.edu',
            'username': 'Преподаватель',
            'password': 'teacher123',
            'subscription_type': 'premium'
        }
    ]
    
    conn = sqlite3.connect('ai_study.db')
    c = conn.cursor()
    
    for user_data in demo_users:
        # Удаляем если существует
        c.execute('DELETE FROM users WHERE email = ?', (user_data['email'],))
        
        # Создаем пользователя
        password_hash = generate_password_hash(user_data['password'])
        
        try:
            c.execute('''
                INSERT INTO users (email, username, password_hash, created_at, is_active, subscription_type)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                user_data['email'],
                user_data['username'],
                password_hash,
                datetime.now(),
                True,
                user_data['subscription_type']
            ))
            
            print(f"   ✅ {user_data['username']} ({user_data['email']})")
            print(f"      Пароль: {user_data['password']}")
            print(f"      Подписка: {user_data['subscription_type']}")
            print()
            
        except sqlite3.IntegrityError as e:
            print(f"   ❌ Ошибка создания {user_data['email']}: {e}")
    
    conn.commit()
    conn.close()

def show_users_table():
    """Показать таблицу пользователей"""
    print("📋 Таблица пользователей:")
    
    conn = sqlite3.connect('ai_study.db')
    c = conn.cursor()
    
    c.execute('''
        SELECT id, email, username, created_at, is_active, subscription_type
        FROM users
        ORDER BY created_at DESC
    ''')
    
    users = c.fetchall()
    
    if users:
        print(f"{'ID':<3} {'Email':<25} {'Имя':<15} {'Дата':<19} {'Активен':<7} {'Подписка':<10}")
        print("-" * 85)
        
        for user in users:
            user_id, email, username, created_at, is_active, subscription = user
            created_date = created_at[:19] if created_at else 'Неизвестно'
            active_status = 'Да' if is_active else 'Нет'
            
            print(f"{user_id:<3} {email:<25} {username:<15} {created_date:<19} {active_status:<7} {subscription:<10}")
    else:
        print("   Пользователи не найдены")
    
    conn.close()

def create_demo_results():
    """Создание демонстрационных результатов"""
    print("\n📄 Создание демонстрационных результатов...")
    
    conn = sqlite3.connect('ai_study.db')
    c = conn.cursor()
    
    # Получаем ID пользователей
    c.execute('SELECT id, username FROM users')
    users = c.fetchall()
    
    if not users:
        print("   ❌ Сначала создайте пользователей")
        conn.close()
        return
    
    demo_results = [
        {
            'filename': 'Математический_анализ_лекция_1.pdf',
            'file_type': '.pdf',
            'summary': 'Введение в математический анализ. Основные понятия пределов и непрерывности функций.',
            'topics': ['Пределы функций', 'Непрерывность', 'Производные'],
            'flashcards': [
                {'question': 'Что такое предел функции?', 'answer': 'Значение, к которому стремится функция при приближении аргумента к определенной точке.'},
                {'question': 'Определение непрерывности функции', 'answer': 'Функция непрерывна в точке, если предел функции в этой точке равен значению функции.'}
            ]
        },
        {
            'filename': 'Python_основы_видео.mp4',
            'file_type': '.mp4',
            'summary': 'Основы программирования на Python. Переменные, типы данных, условные операторы.',
            'topics': ['Переменные', 'Типы данных', 'Условные операторы'],
            'flashcards': [
                {'question': 'Как объявить переменную в Python?', 'answer': 'Просто присвоить значение: x = 10'},
                {'question': 'Основные типы данных в Python', 'answer': 'int, float, str, bool, list, dict, tuple'}
            ]
        }
    ]
    
    for i, result_data in enumerate(demo_results):
        user_id = users[i % len(users)][0]  # Распределяем результаты между пользователями
        
        try:
            c.execute('''
                INSERT INTO result (
                    filename, file_type, topics_json, summary, flashcards_json,
                    mind_map_json, study_plan_json, quality_json,
                    video_segments_json, key_moments_json, full_text, user_id, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                result_data['filename'],
                result_data['file_type'],
                str(result_data['topics']),
                result_data['summary'],
                str(result_data['flashcards']),
                '{}', '{}', '{}', '[]', '[]', '',
                user_id,
                datetime.now()
            ))
            
            print(f"   ✅ {result_data['filename']} (пользователь: {users[i % len(users)][1]})")
            
        except Exception as e:
            print(f"   ❌ Ошибка создания результата: {e}")
    
    conn.commit()
    conn.close()

def show_statistics():
    """Показать статистику системы"""
    print("\n📊 Статистика системы:")
    
    conn = sqlite3.connect('ai_study.db')
    c = conn.cursor()
    
    # Общая статистика
    c.execute('SELECT COUNT(*) FROM users')
    users_count = c.fetchone()[0]
    
    c.execute('SELECT COUNT(*) FROM result')
    results_count = c.fetchone()[0]
    
    c.execute('SELECT COUNT(*) FROM users WHERE subscription_type = "premium"')
    premium_users = c.fetchone()[0]
    
    print(f"   👥 Всего пользователей: {users_count}")
    print(f"   📄 Всего результатов: {results_count}")
    print(f"   👑 Premium пользователей: {premium_users}")
    
    # Статистика по пользователям
    c.execute('''
        SELECT u.username, COUNT(r.id) as results_count
        FROM users u
        LEFT JOIN result r ON u.id = r.user_id
        GROUP BY u.id, u.username
        ORDER BY results_count DESC
    ''')
    
    user_stats = c.fetchall()
    
    if user_stats:
        print("\n   📈 Результаты по пользователям:")
        for username, count in user_stats:
            print(f"      • {username}: {count} результатов")
    
    conn.close()

def main():
    """Главная функция демонстрации"""
    print("🚀 Демонстрация системы аутентификации AI-конспект")
    print("=" * 60)
    
    # Создаем демо пользователей
    create_demo_users()
    
    # Показываем таблицу пользователей
    show_users_table()
    
    # Создаем демо результаты
    create_demo_results()
    
    # Показываем статистику
    show_statistics()
    
    print("\n" + "=" * 60)
    print("✅ Демонстрация завершена!")
    print("\n🌐 Для тестирования откройте браузер и перейдите на:")
    print("   http://localhost:5000")
    print("\n🔑 Тестовые аккаунты:")
    print("   admin@ai-konspekt.ru / admin123")
    print("   student@example.com / student123")
    print("   teacher@university.edu / teacher123")
    print("\n🚀 Запустите приложение командой:")
    print("   python app.py")

if __name__ == '__main__':
    main()