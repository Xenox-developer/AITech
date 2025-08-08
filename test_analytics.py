#!/usr/bin/env python3
"""
Тестовый скрипт для проверки работы системы аналитики
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from analytics import element_analytics
import uuid
from datetime import datetime, timedelta
import random

def test_analytics():
    """Тестирование системы аналитики"""
    print("🧪 Тестирование системы аналитики...")
    
    # Создаем тестовую сессию
    session_id = str(uuid.uuid4())
    user_id = 1  # Предполагаем, что пользователь с ID 1 существует
    
    print(f"📱 Создаем сессию: {session_id}")
    element_analytics.start_session(
        session_id=session_id,
        user_id=user_id,
        user_agent="Test Browser 1.0",
        ip_address="127.0.0.1"
    )
    
    # Генерируем тестовые взаимодействия
    test_interactions = [
        ('button', 'upload-btn', 'click', '/', 'Главная страница'),
        ('link', 'dashboard-link', 'click', '/', 'Главная страница'),
        ('form', 'upload-form', 'submit', '/', 'Главная страница'),
        ('button', 'analyze-btn', 'click', '/result/123', 'Результат анализа'),
        ('content', 'flashcard-1', 'view', '/result/123', 'Результат анализа'),
        ('button', 'next-card', 'click', '/result/123', 'Результат анализа'),
        ('button', 'prev-card', 'click', '/result/123', 'Результат анализа'),
        ('link', 'download-link', 'click', '/result/123', 'Результат анализа'),
        ('navigation', 'main-menu', 'click', '/dashboard', 'Личный кабинет'),
        ('button', 'filter-pdf', 'click', '/my-results', 'Мои результаты'),
    ]
    
    print("📊 Записываем тестовые взаимодействия...")
    for element_type, element_id, action_type, page_url, page_title in test_interactions:
        metadata = {
            'test_data': True,
            'timestamp': datetime.now().isoformat()
        }
        
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
        print(f"  ✅ {element_type}.{element_id} - {action_type}")
    
    # Завершаем сессию
    element_analytics.end_session(session_id)
    print(f"🏁 Сессия завершена: {session_id}")
    
    # Получаем статистику
    print("\n📈 Получаем статистику...")
    
    # Популярные элементы
    popular = element_analytics.get_popular_elements(limit=5, days=1)
    print(f"\n🔥 Популярные элементы (топ-5):")
    for i, elem in enumerate(popular, 1):
        print(f"  {i}. {elem['element_type']}.{elem['element_id']} - {elem['action_type']}")
        print(f"     Взаимодействий: {elem['total_interactions']}, Пользователей: {elem['unique_users']}")
    
    # Общая статистика
    stats = element_analytics.get_element_usage_stats(days=1)
    print(f"\n📊 Общая статистика за день:")
    print(f"  Всего взаимодействий: {stats['total_interactions']}")
    print(f"  Уникальных пользователей: {stats['unique_users']}")
    print(f"  Уникальных сессий: {stats['unique_sessions']}")
    print(f"  Активных дней: {stats['active_days']}")
    
    # Статистика по типам действий
    print(f"\n🎯 Статистика по типам действий:")
    for action in stats['action_stats']:
        print(f"  {action['action_type']}: {action['interactions']} взаимодействий, {action['unique_users']} пользователей")
    
    # Статистика по элементам
    print(f"\n🎛️ Статистика по элементам (топ-5):")
    for elem in stats['element_stats'][:5]:
        print(f"  {elem['element_type']}.{elem['element_id']}: {elem['interactions']} взаимодействий")
    
    # Паттерны поведения
    behavior = element_analytics.get_user_behavior_patterns(user_id=user_id, days=1)
    print(f"\n👤 Активные пользователи:")
    for user in behavior['active_users'][:3]:
        print(f"  Пользователь {user['user_id']}: {user['total_interactions']} взаимодействий")
    
    # Аналитика по страницам
    page_stats = element_analytics.get_page_analytics(days=1)
    print(f"\n📄 Статистика по страницам:")
    for page in page_stats['page_stats'][:5]:
        print(f"  {page['page_url']}: {page['total_interactions']} взаимодействий, {page['unique_users']} пользователей")
    
    print("\n✅ Тестирование завершено успешно!")

if __name__ == '__main__':
    test_analytics()