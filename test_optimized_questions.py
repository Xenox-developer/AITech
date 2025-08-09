#!/usr/bin/env python3
"""
Тест оптимизированной генерации тестовых вопросов
"""

import time
import json
import os
from datetime import datetime

# Добавляем путь к модулям
import sys
sys.path.append('.')

def test_optimized_question_generation():
    """Тестирует оптимизированную генерацию вопросов"""
    
    # Импортируем функцию из app.py
    from app import generate_test_questions
    
    # Тестовые данные (имитируем результат анализа)
    test_data = {
        'filename': 'test_video.mp4',
        'full_text': '''
        В этом видео мы изучаем основы машинного обучения. 
        Машинное обучение - это раздел искусственного интеллекта, который позволяет компьютерам обучаться на данных.
        Существует три основных типа машинного обучения:
        1. Обучение с учителем (supervised learning) - когда у нас есть правильные ответы
        2. Обучение без учителя (unsupervised learning) - когда мы ищем скрытые закономерности
        3. Обучение с подкреплением (reinforcement learning) - когда система учится через награды и наказания
        
        Важные концепции:
        - Переобучение (overfitting) - когда модель слишком хорошо запоминает обучающие данные
        - Недообучение (underfitting) - когда модель слишком простая
        - Валидация - процесс проверки качества модели на новых данных
        
        Популярные алгоритмы:
        - Линейная регрессия для предсказания числовых значений
        - Логистическая регрессия для классификации
        - Деревья решений для интерпретируемых моделей
        - Нейронные сети для сложных задач
        ''',
        'summary': 'Видео об основах машинного обучения, типах обучения и популярных алгоритмах',
        'topics_data': {
            'Основы машинного обучения': {
                'subtopics': ['Определение', 'Применение', 'История']
            },
            'Типы обучения': {
                'subtopics': ['С учителем', 'Без учителя', 'С подкреплением']
            },
            'Проблемы обучения': {
                'subtopics': ['Переобучение', 'Недообучение', 'Валидация']
            },
            'Алгоритмы': {
                'subtopics': ['Регрессия', 'Классификация', 'Нейронные сети']
            }
        }
    }
    
    print("🚀 Тестирование оптимизированной генерации вопросов...")
    print(f"📊 Размер текста: {len(test_data['full_text'])} символов")
    print(f"📚 Количество тем: {len(test_data['topics_data'])}")
    
    # Засекаем время
    start_time = time.time()
    
    try:
        # Генерируем вопросы
        questions = generate_test_questions(test_data)
        
        # Засекаем время окончания
        end_time = time.time()
        generation_time = end_time - start_time
        
        print(f"⏱️ Время генерации: {generation_time:.2f} секунд")
        print(f"❓ Количество вопросов: {len(questions)}")
        
        # Анализируем результаты
        if questions:
            difficulties = {}
            topics = set()
            
            for q in questions:
                diff = q.get('difficulty', 'unknown')
                difficulties[diff] = difficulties.get(diff, 0) + 1
                topics.add(q.get('topic', 'unknown'))
            
            print(f"📈 Распределение по сложности: {difficulties}")
            print(f"🎯 Уникальных тем: {len(topics)}")
            
            # Показываем примеры вопросов
            print("\n📝 Примеры сгенерированных вопросов:")
            for i, q in enumerate(questions[:3], 1):
                print(f"\n{i}. {q.get('question', 'Нет вопроса')}")
                print(f"   Сложность: {q.get('difficulty', 'unknown')}")
                print(f"   Тема: {q.get('topic', 'unknown')}")
                print(f"   Правильный ответ: {q.get('correct_answer', 'unknown')}")
            
            # Проверяем качество
            quality_issues = []
            
            for i, q in enumerate(questions, 1):
                if not q.get('question'):
                    quality_issues.append(f"Вопрос {i}: отсутствует текст вопроса")
                
                if not q.get('options') or len(q.get('options', {})) != 4:
                    quality_issues.append(f"Вопрос {i}: неправильное количество вариантов ответа")
                
                if not q.get('correct_answer'):
                    quality_issues.append(f"Вопрос {i}: отсутствует правильный ответ")
                
                if not q.get('explanation'):
                    quality_issues.append(f"Вопрос {i}: отсутствует объяснение")
            
            if quality_issues:
                print(f"\n⚠️ Проблемы качества ({len(quality_issues)}):")
                for issue in quality_issues[:5]:  # Показываем первые 5
                    print(f"   - {issue}")
            else:
                print("\n✅ Все вопросы прошли проверку качества!")
            
            # Оценка производительности
            if generation_time < 30:
                print(f"🚀 ОТЛИЧНО: Генерация заняла {generation_time:.1f}с (цель: <30с)")
            elif generation_time < 60:
                print(f"✅ ХОРОШО: Генерация заняла {generation_time:.1f}с (цель: <30с)")
            elif generation_time < 120:
                print(f"⚠️ МЕДЛЕННО: Генерация заняла {generation_time:.1f}с (цель: <30с)")
            else:
                print(f"❌ ОЧЕНЬ МЕДЛЕННО: Генерация заняла {generation_time:.1f}с (цель: <30с)")
            
            return {
                'success': True,
                'generation_time': generation_time,
                'questions_count': len(questions),
                'quality_issues': len(quality_issues),
                'difficulties': difficulties
            }
        
        else:
            print("❌ Не удалось сгенерировать вопросы")
            return {'success': False, 'error': 'No questions generated'}
    
    except Exception as e:
        end_time = time.time()
        generation_time = end_time - start_time
        
        print(f"❌ Ошибка генерации: {str(e)}")
        print(f"⏱️ Время до ошибки: {generation_time:.2f} секунд")
        
        return {
            'success': False,
            'error': str(e),
            'generation_time': generation_time
        }

def test_multiple_runs():
    """Тестирует несколько запусков для оценки стабильности"""
    print("\n" + "="*60)
    print("🔄 Тестирование стабильности (3 запуска)")
    print("="*60)
    
    results = []
    
    for i in range(3):
        print(f"\n--- Запуск {i+1}/3 ---")
        result = test_optimized_question_generation()
        results.append(result)
        
        if i < 2:  # Пауза между запусками
            time.sleep(2)
    
    # Анализ результатов
    successful_runs = [r for r in results if r.get('success')]
    
    if successful_runs:
        avg_time = sum(r['generation_time'] for r in successful_runs) / len(successful_runs)
        avg_questions = sum(r['questions_count'] for r in successful_runs) / len(successful_runs)
        
        print(f"\n📊 ИТОГОВАЯ СТАТИСТИКА:")
        print(f"✅ Успешных запусков: {len(successful_runs)}/3")
        print(f"⏱️ Среднее время: {avg_time:.2f} секунд")
        print(f"❓ Среднее количество вопросов: {avg_questions:.1f}")
        
        if avg_time < 30:
            print("🎉 ЦЕЛЬ ДОСТИГНУТА: Среднее время < 30 секунд!")
        else:
            print(f"⚠️ Нужна дополнительная оптимизация (цель: <30с, факт: {avg_time:.1f}с)")
    
    else:
        print("❌ Все запуски завершились ошибкой")

if __name__ == "__main__":
    # Загружаем переменные из .env файла
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        # Если python-dotenv не установлен, пробуем загрузить вручную
        try:
            with open('.env', 'r') as f:
                for line in f:
                    if line.strip() and not line.startswith('#'):
                        key, value = line.strip().split('=', 1)
                        os.environ[key] = value
        except FileNotFoundError:
            pass
    
    # Проверяем наличие API ключа
    if not os.environ.get('OPENAI_API_KEY'):
        print("❌ Ошибка: Не установлен OPENAI_API_KEY")
        print("Проверьте файл .env или установите переменную окружения")
        exit(1)
    
    print("🧪 ТЕСТ ОПТИМИЗИРОВАННОЙ ГЕНЕРАЦИИ ВОПРОСОВ")
    print("=" * 60)
    print(f"🕐 Время начала: {datetime.now().strftime('%H:%M:%S')}")
    
    # Одиночный тест
    test_optimized_question_generation()
    
    # Тест стабильности
    test_multiple_runs()
    
    print(f"\n🕐 Время окончания: {datetime.now().strftime('%H:%M:%S')}")
    print("✅ Тестирование завершено!")