#!/usr/bin/env python3
"""
Тестовый скрипт для создания данных для статистики пользователей
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from analytics import element_analytics
from auth import User, generate_password_hash
import uuid
from datetime import datetime, timedelta
import random
import sqlite3

def create_test_users():
    """Создание тестовых пользователей"""
    print("👥 Создаем тестовых пользователей...")
    
    conn = sqlite3.connect('ai_study.db')
    c = conn.cursor()
    
    test_users = [
        ('alice@example.com', 'Alice Johnson', 'password123'),
        ('bob@example.com', 'Bob Smith', 'password123'),
        ('charlie@example.com', 'Charlie Brown', 'password123'),
        ('diana@example.com', 'Diana Prince', 'password123'),
        ('eve@example.com', 'Eve Wilson', 'password123'),
    ]
    
    user_ids = []
    
    for email, username, password in test_users:
        try:
            # Проверяем, существует ли пользователь
            c.execute('SELECT id FROM users WHERE email = ?', (email,))
            existing = c.fetchone()
            
            if existing:
                user_ids.append(existing[0])
                print(f"  ✅ Пользователь {username} уже существует (ID: {existing[0]})")
            else:
                # Создаем нового пользователя
                password_hash = generate_password_hash(password)
                c.execute('''
                    INSERT INTO users (email, username, password_hash, created_at)
                    VALUES (?, ?, ?, ?)
                ''', (email, username, password_hash, datetime.now() - timedelta(days=random.randint(1, 30))))
                
                user_id = c.lastrowid
                user_ids.append(user_id)
                print(f"  ✅ Создан пользователь {username} (ID: {user_id})")
                
        except Exception as e:
            print(f"  ❌ Ошибка создания пользователя {username}: {e}")
    
    conn.commit()
    conn.close()
    
    return user_ids

def generate_user_interactions(user_ids):
    """Генерация взаимодействий для пользователей"""
    print("📊 Генерируем взаимодействия пользователей...")
    
    # Различные элементы для взаимодействия
    interactions_templates = [
        ('button', 'upload-btn', 'click', '/', 'Главная страница'),
        ('button', 'analyze-btn', 'click', '/result/123', 'Результат анализа'),
        ('button', 'next-card', 'click', '/result/123', 'Результат анализа'),
        ('button', 'prev-card', 'click', '/result/123', 'Результат анализа'),
        ('link', 'dashboard-link', 'click', '/', 'Главная страница'),
        ('link', 'profile-link', 'click', '/dashboard', 'Личный кабинет'),
        ('form', 'upload-form', 'submit', '/', 'Главная страница'),
        ('input', 'search-input', 'focus', '/dashboard', 'Личный кабинет'),
        ('select', 'filter-select', 'change', '/my-results', 'Мои результаты'),
        ('navigation', 'main-menu', 'click', '/dashboard', 'Личный кабинет'),
        ('content', 'flashcard-1', 'view', '/result/123', 'Результат анализа'),
        ('page', 'body', 'scroll', '/result/123', 'Результат анализа'),
    ]
    
    # Генерируем разное количество активности для каждого пользователя
    activity_levels = [
        (user_ids[0], 50, 5),  # Alice - очень активная
        (user_ids[1], 25, 3),  # Bob - средняя активность
        (user_ids[2], 10, 2),  # Charlie - низкая активность
        (user_ids[3], 5, 1),   # Diana - очень низкая активность
        (user_ids[4], 0, 0),   # Eve - неактивная
    ]
    
    for user_id, interaction_count, session_count in activity_levels:
        if interaction_count == 0:
            continue
            
        print(f"  👤 Генерируем {interaction_count} взаимодействий для пользователя {user_id}")
        
        # Создаем сессии для пользователя
        for session_num in range(session_count):
            session_id = str(uuid.uuid4())
            
            # Случайная дата в последние 30 дней
            session_date = datetime.now() - timedelta(days=random.randint(0, 30))
            
            # Начинаем сессию
            element_analytics.start_session(
                session_id=session_id,
                user_id=user_id,
                user_agent=f"TestBrowser/{random.randint(1, 5)}.0",
                ip_address=f"192.168.1.{random.randint(1, 255)}"
            )
            
            # Генерируем взаимодействия для этой сессии
            interactions_in_session = interaction_count // session_count
            if session_num == 0:  # В первой сессии добавляем остаток
                interactions_in_session += interaction_count % session_count
            
            for _ in range(interactions_in_session):
                element_type, element_id, action_type, page_url, page_title = random.choice(interactions_templates)
                
                metadata = {
                    'test_data': True,
                    'user_agent': f"TestBrowser/{random.randint(1, 5)}.0",
                    'session_number': session_num + 1
                }
                
                # Записываем взаимодействие
                element_analytics.record_interaction(
                    user_id=user_id,
                    session_id=session_id,
                    element_type=element_type,
                    element_id=element_id,
                    action_type=action_type,
                    page_url=page_url,
                    page_title=page_title,
                    metadata=metadata
                )
            
            # Завершаем сессию
            element_analytics.end_session(session_id)
    
    print("  ✅ Взаимодействия сгенерированы")

def test_user_analytics():
    """Тестирование аналитики пользователей"""
    print("🧪 Тестирование системы аналитики пользователей...")
    
    # Создаем тестовых пользователей
    user_ids = create_test_users()
    
    if len(user_ids) < 5:
        print("❌ Не удалось создать достаточно пользователей для тестирования")
        return
    
    # Генерируем взаимодействия
    generate_user_interactions(user_ids)
    
    # Получаем статистику
    print("\n📈 Получаем статистику пользователей...")
    
    # Детальная статистика пользователей
    user_stats = element_analytics.get_detailed_user_stats(days=30)
    print(f"\n👥 Общая статистика:")
    print(f"  Всего пользователей: {user_stats['overview']['total_users']}")
    print(f"  Активных пользователей: {user_stats['overview']['active_users']}")
    print(f"  Новых пользователей: {user_stats['overview']['new_users']}")
    
    print(f"\n🏆 Топ активных пользователей:")
    for i, user in enumerate(user_stats['user_stats'][:5], 1):
        print(f"  {i}. {user['username']} ({user['email']})")
        print(f"     Взаимодействий: {user['total_interactions']}, Сессий: {user['unique_sessions']}")
        print(f"     Активных дней: {user['active_days']}, Страниц: {user['pages_visited']}")
    
    # Метрики вовлеченности
    engagement = element_analytics.get_user_engagement_metrics(days=30)
    print(f"\n📊 Сегментация по активности:")
    for segment in engagement['activity_segments']:
        print(f"  {segment['segment']}: {segment['user_count']} пользователей")
    
    print(f"\n⏱️ Последние сессии:")
    for session in engagement['recent_sessions'][:5]:
        duration = f"{session['duration_minutes']} мин" if session['duration_minutes'] else "В процессе"
        print(f"  {session['username']}: {session['total_interactions']} взаимодействий, {duration}")
    
    print(f"\n📈 Средние показатели:")
    avg = engagement['averages']
    print(f"  Взаимодействий на пользователя: {avg['interactions_per_user']}")
    print(f"  Сессий на пользователя: {avg['sessions_per_user']}")
    print(f"  Страниц на пользователя: {avg['pages_per_user']}")
    
    print("\n✅ Тестирование аналитики пользователей завершено успешно!")

if __name__ == '__main__':
    test_user_analytics()