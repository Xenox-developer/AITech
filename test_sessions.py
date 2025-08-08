#!/usr/bin/env python3
"""
Тестовый скрипт для проверки работы учебных сессий
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import get_or_create_user_study_sessions
import sqlite3

def test_study_sessions():
    """Тестирование системы учебных сессий"""
    print("📚 Тестирование системы учебных сессий...")
    
    # Тестируем для пользователя test@test.ru (ID = 1)
    user_id = 1
    
    print(f"\n🔍 Проверяем сессии для пользователя {user_id}...")
    
    # Проверяем, что есть в базе данных
    conn = sqlite3.connect('ai_study.db')
    c = conn.cursor()
    
    c.execute('SELECT COUNT(*) FROM study_sessions WHERE user_id = ?', (user_id,))
    db_count = c.fetchone()[0]
    print(f"📊 В базе данных: {db_count} сессий")
    
    c.execute('''
        SELECT id, title, phase, status 
        FROM study_sessions 
        WHERE user_id = ? 
        ORDER BY created_at
    ''', (user_id,))
    
    db_sessions = c.fetchall()
    print(f"📋 Сессии в базе данных:")
    for session in db_sessions:
        print(f"  ID: {session[0]}, Название: {session[1]}, Фаза: {session[2]}, Статус: {session[3]}")
    
    conn.close()
    
    # Теперь тестируем функцию несколько раз
    print(f"\n🔧 Тестируем многократный вызов функции...")
    
    for i in range(3):
        print(f"\n--- Вызов {i+1} ---")
        try:
            sessions = get_or_create_user_study_sessions(user_id)
            print(f"✅ Функция вернула {len(sessions)} сессий")
            
            # Проверяем, не создались ли новые сессии
            conn = sqlite3.connect('ai_study.db')
            c = conn.cursor()
            c.execute('SELECT COUNT(*) FROM study_sessions WHERE user_id = ?', (user_id,))
            current_count = c.fetchone()[0]
            conn.close()
            
            print(f"📊 В базе данных: {current_count} сессий")
            
            if current_count > db_count:
                print(f"⚠️  ПРОБЛЕМА: Создались новые сессии! Было {db_count}, стало {current_count}")
                db_count = current_count  # Обновляем счетчик для следующей итерации
            else:
                print(f"✅ Хорошо: Новые сессии не создались")
                
        except Exception as e:
            print(f"❌ Ошибка в функции: {e}")
            import traceback
            traceback.print_exc()
    
    # Тестируем полную функцию get_user_learning_stats
    print(f"\n🔧 Тестируем get_user_learning_stats({user_id})...")
    
    try:
        from app import get_user_learning_stats
        learning_stats = get_user_learning_stats(user_id)
        
        print(f"✅ get_user_learning_stats вернула данные")
        print(f"📚 Учебных сессий: {len(learning_stats.get('study_sessions', []))}")
        
        for i, session in enumerate(learning_stats.get('study_sessions', []), 1):
            print(f"  {i}. {session['title']} ({session['phase']}) - {session['status']}")
            
        # Проверяем финальное количество сессий
        conn = sqlite3.connect('ai_study.db')
        c = conn.cursor()
        c.execute('SELECT COUNT(*) FROM study_sessions WHERE user_id = ?', (user_id,))
        final_count = c.fetchone()[0]
        conn.close()
        
        print(f"\n📊 Финальное количество сессий в базе: {final_count}")
        
    except Exception as e:
        print(f"❌ Ошибка в get_user_learning_stats: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    test_study_sessions()