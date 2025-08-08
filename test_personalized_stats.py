#!/usr/bin/env python3
"""
Тестовый скрипт для проверки персонализированной статистики обучения
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import sqlite3
from app import get_user_learning_stats

def test_personalized_stats():
    """Тестирование персонализированной статистики"""
    print("📊 Тестирование персонализированной статистики обучения...")
    
    # Получаем список пользователей
    conn = sqlite3.connect('ai_study.db')
    c = conn.cursor()
    
    c.execute('SELECT id, username, email FROM users ORDER BY id')
    users = c.fetchall()
    
    print(f"\n👥 Найдено пользователей: {len(users)}")
    
    for user_id, username, email in users:
        print(f"\n📈 Статистика для пользователя: {username} ({email})")
        
        try:
            # Получаем персональную статистику
            stats = get_user_learning_stats(user_id)
            
            print(f"  📁 Обработанных файлов: {stats['total_results']}")
            print(f"  🎯 Изученных карточек: {stats['mastered_cards']}")
            print(f"  📚 Всего карточек изучено: {stats['total_cards_studied']}")
            print(f"  ⏰ К повторению сегодня: {stats['cards_due_today']}")
            print(f"  📊 Общий прогресс обучения: {stats['learning_progress']}%")
            
            # Показываем контрольные точки
            print(f"  🏁 Контрольные точки:")
            for i, checkpoint in enumerate(stats['checkpoints'], 1):
                status_emoji = "✅" if checkpoint['status'] == 'completed' else ("🔄" if checkpoint['status'] == 'current' else "⏳")
                print(f"    {i}. {status_emoji} {checkpoint['title']}: {checkpoint['progress']}% ({checkpoint['target']})")
            
            # Показываем целевые показатели
            print(f"  🎯 Целевые показатели:")
            for target in stats['targets']:
                color_emoji = "🟢" if target['color'] == 'success' else ("🟡" if target['color'] == 'warning' else "🔴")
                print(f"    {color_emoji} {target['label']}: {target['value']}")
            
            # Показываем персональные учебные сессии
            print(f"  📚 Учебные сессии:")
            for session in stats['study_sessions']:
                phase_emoji = "🟦" if session['phase'] == 'ОСНОВЫ' else ("🟩" if session['phase'] == 'РАЗВИТИЕ' else ("🟨" if session['phase'] == 'МАСТЕРСТВО' else ("🟪" if session['phase'] == 'НАЧАЛО' else "🔄")))
                print(f"    {phase_emoji} {session['title']} ({session['phase']})")
                print(f"       📅 {session['date']} | ⏱️ {session['duration']} | 📊 {session['difficulty']}")
            
            # Показываем типы файлов
            if stats['file_types']:
                print(f"  📄 Типы файлов:")
                for file_type, count in stats['file_types'].items():
                    print(f"    {file_type}: {count} файлов")
            
        except Exception as e:
            print(f"  ❌ Ошибка получения статистики: {e}")
    
    conn.close()
    
    print("\n✅ Тестирование завершено!")
    print("\nТеперь каждый пользователь увидит свою персональную статистику:")
    print("1. Войдите под разными пользователями")
    print("2. Откройте личный кабинет (/dashboard)")
    print("3. Проверьте, что данные отличаются для каждого пользователя")

if __name__ == '__main__':
    test_personalized_stats()