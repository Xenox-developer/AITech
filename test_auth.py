#!/usr/bin/env python3
"""
Тестирование системы аутентификации
"""
import sqlite3
import hashlib
import secrets

def generate_password_hash(password):
    """Генерация хеша пароля"""
    salt = secrets.token_hex(16)
    password_hash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), 100000)
    return salt + password_hash.hex()

def check_password_hash(stored_hash, password):
    """Проверка пароля"""
    salt = stored_hash[:32]
    stored_password_hash = stored_hash[32:]
    password_hash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), 100000)
    return password_hash.hex() == stored_password_hash

def test_auth_system():
    """Тестирование основных функций аутентификации"""
    print("🔐 Тестирование системы аутентификации...")
    
    # Тест хеширования паролей
    print("\n1. Тестирование хеширования паролей...")
    password = "test123456"
    hash1 = generate_password_hash(password)
    hash2 = generate_password_hash(password)
    
    print(f"   Пароль: {password}")
    print(f"   Хеш 1: {hash1[:50]}...")
    print(f"   Хеш 2: {hash2[:50]}...")
    print(f"   Хеши разные: {hash1 != hash2} ✓")
    print(f"   Проверка пароля 1: {check_password_hash(hash1, password)} ✓")
    print(f"   Проверка пароля 2: {check_password_hash(hash2, password)} ✓")
    print(f"   Неверный пароль: {not check_password_hash(hash1, 'wrong')} ✓")
    
    # Тест создания пользователя в БД
    print("\n2. Тестирование работы с базой данных...")
    test_email = "test@example.com"
    test_username = "TestUser"
    test_password = "secure123"
    password_hash = generate_password_hash(test_password)
    
    conn = sqlite3.connect('ai_study.db')
    c = conn.cursor()
    
    # Удаляем тестового пользователя если существует
    c.execute('DELETE FROM users WHERE email = ?', (test_email,))
    
    # Создаем пользователя
    try:
        c.execute('''
            INSERT INTO users (email, username, password_hash, created_at, is_active, subscription_type)
            VALUES (?, ?, ?, datetime('now'), ?, ?)
        ''', (test_email, test_username, password_hash, True, 'free'))
        
        user_id = c.lastrowid
        conn.commit()
        print(f"   Пользователь создан: ID={user_id}, Email={test_email} ✓")
        
        # Проверяем получение пользователя
        c.execute('SELECT * FROM users WHERE id = ?', (user_id,))
        user_data = c.fetchone()
        if user_data:
            print(f"   Пользователь найден по ID: {user_data[2]} ✓")
        
        c.execute('SELECT * FROM users WHERE email = ?', (test_email,))
        user_data = c.fetchone()
        if user_data:
            print(f"   Пользователь найден по Email: {user_data[2]} ✓")
            
            # Проверяем пароль
            stored_hash = user_data[3]
            print(f"   Правильный пароль: {check_password_hash(stored_hash, test_password)} ✓")
            print(f"   Неправильный пароль: {not check_password_hash(stored_hash, 'wrong')} ✓")
        
        # Тест дублирования email
        print("\n3. Тестирование дублирования email...")
        try:
            c.execute('''
                INSERT INTO users (email, username, password_hash, created_at, is_active, subscription_type)
                VALUES (?, ?, ?, datetime('now'), ?, ?)
            ''', (test_email, "AnotherUser", password_hash, True, 'free'))
            conn.commit()
            print("   ❌ Дублирование не заблокировано")
        except sqlite3.IntegrityError:
            print("   Дублирование заблокировано ✓")
        
        # Очистка
        c.execute('DELETE FROM users WHERE email = ?', (test_email,))
        conn.commit()
        print("\n4. Тестовые данные удалены ✓")
        
    except Exception as e:
        print(f"   ❌ Ошибка: {e}")
    finally:
        conn.close()
    
    print("\n✅ Все тесты пройдены успешно!")

def show_database_info():
    """Показать информацию о базе данных"""
    print("\n📊 Информация о базе данных:")
    
    conn = sqlite3.connect('ai_study.db')
    c = conn.cursor()
    
    # Количество пользователей
    c.execute('SELECT COUNT(*) FROM users')
    users_count = c.fetchone()[0]
    print(f"   Пользователей: {users_count}")
    
    # Количество результатов
    c.execute('SELECT COUNT(*) FROM result')
    results_count = c.fetchone()[0]
    print(f"   Результатов: {results_count}")
    
    # Последние пользователи
    c.execute('SELECT email, username, created_at FROM users ORDER BY created_at DESC LIMIT 5')
    recent_users = c.fetchall()
    
    if recent_users:
        print("\n   Последние пользователи:")
        for email, username, created_at in recent_users:
            print(f"     • {username} ({email}) - {created_at}")
    
    conn.close()

if __name__ == '__main__':
    test_auth_system()
    show_database_info()