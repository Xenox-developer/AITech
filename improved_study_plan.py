"""
Улучшенная функция генерации плана обучения
"""

import json
from datetime import datetime, timedelta
from typing import List, Dict, Any
import logging

logger = logging.getLogger(__name__)

def generate_enhanced_study_plan(topics: List[Dict], flashcards: List[Dict], text_length: int = 0) -> Dict:
    """
    Генерируем персонализированный план обучения с учетом:
    - Сложности материала
    - Взаимосвязей между темами
    - Оптимального времени изучения
    - Кривой забывания Эббингауза
    - Индивидуального темпа обучения
    """
    try:
        # Анализ материала
        material_analysis = _analyze_material_complexity(topics, flashcards, text_length)
        
        # Определение оптимального расписания
        schedule_config = _calculate_optimal_schedule(material_analysis)
        
        # Создание последовательности изучения
        learning_sequence = _create_learning_sequence(topics, material_analysis)
        
        # Генерация сессий
        sessions = _generate_study_sessions(learning_sequence, flashcards, schedule_config)
        
        # Создание системы повторений
        review_system = _create_spaced_repetition_schedule(sessions, material_analysis)
        
        # Генерация контрольных точек
        milestones = _generate_smart_milestones(topics, sessions, material_analysis)
        
        # Создание адаптивного плана
        adaptive_features = _create_adaptive_features(material_analysis)
        
        return {
            "sessions": sessions,
            "milestones": milestones,
            "review_system": review_system,
            "material_analysis": material_analysis,
            "adaptive_features": adaptive_features,
            "total_hours": schedule_config["total_hours"],
            "estimated_completion": schedule_config["completion_date"],
            "difficulty_level": material_analysis["overall_difficulty"],
            "learning_path": _create_learning_path_visualization(sessions),
            "success_metrics": _define_success_metrics(topics, flashcards)
        }
        
    except Exception as e:
        logger.error(f"Error generating enhanced study plan: {str(e)}")
        return _generate_fallback_plan()

def _analyze_material_complexity(topics: List[Dict], flashcards: List[Dict], text_length: int) -> Dict:
    """Анализ сложности материала"""
    
    # Анализ тем по сложности
    complexity_distribution = {"basic": 0, "intermediate": 0, "advanced": 0}
    topic_depths = []
    
    for topic in topics:
        complexity = topic.get('complexity', 'basic')
        complexity_distribution[complexity] += 1
        
        # Оценка глубины темы
        depth_score = 0
        depth_score += len(topic.get('subtopics', [])) * 0.3
        depth_score += len(topic.get('key_concepts', [])) * 0.2
        depth_score += len(topic.get('examples', [])) * 0.1
        depth_score += len(topic.get('summary', '')) / 100
        
        topic_depths.append(depth_score)
    
    # Анализ флеш-карт
    card_difficulties = [card.get('difficulty', 1) for card in flashcards]
    avg_card_difficulty = sum(card_difficulties) / len(card_difficulties) if card_difficulties else 1
    
    # Анализ объема материала
    volume_factor = min(2.0, text_length / 10000)  # Нормализация по объему
    
    # Общая оценка сложности
    complexity_weights = {"basic": 1, "intermediate": 2, "advanced": 3}
    weighted_complexity = sum(complexity_distribution[k] * v for k, v in complexity_weights.items())
    total_topics = sum(complexity_distribution.values())
    overall_difficulty = weighted_complexity / max(total_topics, 1)
    
    return {
        "complexity_distribution": complexity_distribution,
        "topic_depths": topic_depths,
        "avg_topic_depth": sum(topic_depths) / len(topic_depths) if topic_depths else 1,
        "avg_card_difficulty": avg_card_difficulty,
        "volume_factor": volume_factor,
        "overall_difficulty": overall_difficulty,
        "estimated_study_time": _estimate_study_time(overall_difficulty, len(topics), len(flashcards), text_length)
    }

def _estimate_study_time(difficulty: float, num_topics: int, num_cards: int, text_length: int) -> Dict:
    """Оценка времени изучения на основе научных данных"""
    
    # Базовое время на тему (в минутах)
    base_time_per_topic = {
        1: 15,    # basic
        2: 25,    # intermediate  
        3: 40     # advanced
    }
    
    # Время на флеш-карту
    time_per_card = 2  # минуты на изучение + повторение
    
    # Время на чтение (200 слов в минуту)
    reading_time = (text_length / 5) / 200  # примерно 5 символов на слово
    
    # Расчет общего времени
    topic_time = num_topics * base_time_per_topic.get(int(difficulty), 25)
    card_time = num_cards * time_per_card
    
    total_minutes = reading_time + topic_time + card_time
    
    # Добавляем время на повторения (30% от основного времени)
    total_minutes *= 1.3
    
    return {
        "total_minutes": int(total_minutes),
        "total_hours": round(total_minutes / 60, 1),
        "reading_time": int(reading_time),
        "study_time": int(topic_time + card_time),
        "review_time": int(total_minutes * 0.3)
    }

def _calculate_optimal_schedule(analysis: Dict) -> Dict:
    """Расчет оптимального расписания"""
    
    total_hours = analysis["estimated_study_time"]["total_hours"]
    difficulty = analysis["overall_difficulty"]
    
    # Оптимальная длительность сессии в зависимости от сложности
    if difficulty < 1.5:
        session_duration = 30  # легкий материал
        sessions_per_week = 4
    elif difficulty < 2.5:
        session_duration = 45  # средний материал
        sessions_per_week = 5
    else:
        session_duration = 60  # сложный материал
        sessions_per_week = 6
    
    # Расчет количества сессий
    total_sessions = max(3, int(total_hours * 60 / session_duration))
    
    # Расчет продолжительности курса
    weeks_needed = max(1, total_sessions / sessions_per_week)
    completion_date = datetime.now() + timedelta(weeks=weeks_needed)
    
    return {
        "session_duration": session_duration,
        "total_sessions": total_sessions,
        "sessions_per_week": sessions_per_week,
        "weeks_needed": int(weeks_needed),
        "total_hours": total_hours,
        "completion_date": completion_date.strftime("%d.%m.%Y")
    }

def _create_learning_sequence(topics: List[Dict], analysis: Dict) -> List[Dict]:
    """Создание оптимальной последовательности изучения"""
    
    # Сортировка тем по сложности и зависимостям
    sorted_topics = sorted(topics, key=lambda t: (
        {"basic": 1, "intermediate": 2, "advanced": 3}.get(t.get('complexity', 'basic'), 2),
        -len(t.get('key_concepts', [])),  # больше концепций = изучаем раньше
        len(t.get('title', ''))  # короткие названия обычно базовые
    ))
    
    # Группировка тем по фазам обучения
    total_topics = len(sorted_topics)
    foundation_phase = sorted_topics[:total_topics//3] if total_topics > 3 else sorted_topics[:1]
    development_phase = sorted_topics[total_topics//3:2*total_topics//3] if total_topics > 3 else sorted_topics[1:2]
    mastery_phase = sorted_topics[2*total_topics//3:] if total_topics > 3 else sorted_topics[2:]
    
    return {
        "foundation": foundation_phase,
        "development": development_phase,
        "mastery": mastery_phase,
        "all_topics": sorted_topics
    }

def _generate_study_sessions(sequence: Dict, flashcards: List[Dict], config: Dict) -> List[Dict]:
    """Генерация детальных учебных сессий"""
    
    sessions = []
    all_topics = sequence["all_topics"]
    total_sessions = config["total_sessions"]
    session_duration = config["session_duration"]
    
    # Распределение флеш-карт по сессиям
    cards_per_session = max(3, len(flashcards) // total_sessions)
    
    for session_num in range(1, total_sessions + 1):
        # Определение фазы обучения
        if session_num <= total_sessions // 3:
            phase = "foundation"
            phase_name = "Основы"
            topics_pool = sequence["foundation"]
        elif session_num <= 2 * total_sessions // 3:
            phase = "development"
            phase_name = "Развитие"
            topics_pool = sequence["development"]
        else:
            phase = "mastery"
            phase_name = "Мастерство"
            topics_pool = sequence["mastery"]
        
        # Выбор тем для сессии
        topic_index = (session_num - 1) % len(topics_pool) if topics_pool else 0
        current_topic = topics_pool[topic_index] if topics_pool else {"title": "Общее изучение", "complexity": "basic"}
        
        # Выбор флеш-карт
        start_card = (session_num - 1) * cards_per_session
        end_card = min(start_card + cards_per_session, len(flashcards))
        session_cards = flashcards[start_card:end_card]
        
        # Генерация активностей
        activities = _generate_session_activities(current_topic, session_cards, phase, session_duration)
        
        # Расчет даты сессии
        days_from_start = (session_num - 1) * (7 / config["sessions_per_week"])
        session_date = datetime.now() + timedelta(days=days_from_start)
        
        session = {
            "session_number": session_num,
            "date": session_date.strftime("%d.%m.%Y"),
            "day_of_week": session_date.strftime("%A"),
            "phase": phase,
            "phase_name": phase_name,
            "duration_minutes": session_duration,
            "main_topic": current_topic,
            "topics": [current_topic["title"]],
            "flashcards_count": len(session_cards),
            "flashcard_ids": [i for i in range(start_card, end_card)],
            "activities": activities,
            "learning_objectives": _generate_session_objectives(current_topic, phase),
            "success_criteria": _generate_success_criteria(current_topic, len(session_cards)),
            "estimated_difficulty": current_topic.get("complexity", "basic"),
            "preparation_time": 5,  # минут на подготовку
            "review_time": 10,      # минут на повторение
            "break_time": 5 if session_duration > 30 else 0
        }
        
        sessions.append(session)
    
    return sessions

def _generate_session_activities(topic: Dict, cards: List[Dict], phase: str, duration: int) -> List[Dict]:
    """Генерация активностей для сессии"""
    
    activities = []
    topic_title = topic.get("title", "Изучение материала")
    
    # Разминка (5 минут)
    activities.append({
        "type": "warmup",
        "name": "Активация знаний",
        "duration": 5,
        "description": f"Вспомните, что вы уже знаете о теме '{topic_title}'",
        "icon": "🧠"
    })
    
    # Основное изучение (40-60% времени)
    main_study_time = int(duration * 0.5)
    activities.append({
        "type": "study",
        "name": "Изучение основного материала",
        "duration": main_study_time,
        "description": f"Глубокое изучение темы '{topic_title}' с фокусом на ключевые концепции",
        "icon": "📚",
        "tasks": [
            f"Прочитайте материал по теме '{topic_title}'",
            "Выделите 3-5 ключевых понятий",
            "Создайте краткие заметки своими словами"
        ]
    })
    
    # Работа с флеш-картами (20-30% времени)
    if cards:
        card_time = int(duration * 0.25)
        activities.append({
            "type": "flashcards",
            "name": "Закрепление с флеш-картами",
            "duration": card_time,
            "description": f"Изучение {len(cards)} флеш-карт по теме",
            "icon": "🎴",
            "cards_count": len(cards)
        })
    
    # Практическое применение (15-20% времени)
    practice_time = int(duration * 0.15)
    if practice_time > 5:
        activities.append({
            "type": "practice",
            "name": "Практическое применение",
            "duration": practice_time,
            "description": "Применение изученных концепций на практике",
            "icon": "⚡",
            "tasks": _generate_practice_tasks(topic, phase)
        })
    
    # Рефлексия (5-10 минут)
    reflection_time = max(5, int(duration * 0.1))
    activities.append({
        "type": "reflection",
        "name": "Рефлексия и планирование",
        "duration": reflection_time,
        "description": "Оценка понимания и планирование следующих шагов",
        "icon": "🤔",
        "questions": [
            "Что нового я узнал в этой сессии?",
            "Какие концепции требуют дополнительного изучения?",
            "Как я могу применить эти знания на практике?"
        ]
    })
    
    return activities

def _generate_practice_tasks(topic: Dict, phase: str) -> List[str]:
    """Генерация практических заданий"""
    
    topic_title = topic.get("title", "изученную тему")
    tasks = []
    
    if phase == "foundation":
        tasks = [
            f"Объясните {topic_title} простыми словами",
            f"Приведите 2-3 примера применения концепций из '{topic_title}'",
            f"Нарисуйте простую схему или диаграмму для '{topic_title}'"
        ]
    elif phase == "development":
        tasks = [
            f"Сравните {topic_title} с ранее изученными темами",
            f"Решите практическую задачу, используя знания о '{topic_title}'",
            f"Создайте mind map для '{topic_title}'"
        ]
    else:  # mastery
        tasks = [
            f"Критически оцените применимость '{topic_title}' в различных ситуациях",
            f"Создайте собственный пример или кейс для '{topic_title}'",
            f"Объясните '{topic_title}' так, чтобы понял новичок"
        ]
    
    return tasks

def _generate_session_objectives(topic: Dict, phase: str) -> List[str]:
    """Генерация целей сессии"""
    
    topic_title = topic.get("title", "материал")
    
    if phase == "foundation":
        return [
            f"Понять основные концепции темы '{topic_title}'",
            "Запомнить ключевые определения и термины",
            "Уметь объяснить тему простыми словами"
        ]
    elif phase == "development":
        return [
            f"Углубить понимание '{topic_title}'",
            "Установить связи с другими изученными темами",
            "Применить знания для решения практических задач"
        ]
    else:  # mastery
        return [
            f"Достичь экспертного понимания '{topic_title}'",
            "Критически анализировать и оценивать информацию",
            "Создавать новые примеры и объяснения"
        ]

def _generate_success_criteria(topic: Dict, cards_count: int) -> List[str]:
    """Критерии успешного завершения сессии"""
    
    return [
        f"Правильно ответить на {max(1, int(cards_count * 0.8))} из {cards_count} флеш-карт",
        "Объяснить основные концепции своими словами",
        "Привести минимум 1 практический пример применения",
        "Оценить свое понимание темы на 7+ баллов из 10"
    ]

def _create_spaced_repetition_schedule(sessions: List[Dict], analysis: Dict) -> Dict:
    """Создание системы интервальных повторений"""
    
    # Интервалы повторений по Эббингаузу (дни)
    base_intervals = [1, 3, 7, 14, 30, 60]
    
    # Корректировка интервалов в зависимости от сложности
    difficulty = analysis["overall_difficulty"]
    if difficulty > 2.5:
        intervals = [1, 2, 5, 10, 21, 45]  # чаще для сложного материала
    elif difficulty < 1.5:
        intervals = [2, 5, 10, 21, 45, 90]  # реже для легкого материала
    else:
        intervals = base_intervals
    
    # Создание расписания повторений
    review_schedule = []
    for session in sessions:
        session_date = datetime.strptime(session["date"], "%d.%m.%Y")
        
        for interval in intervals:
            review_date = session_date + timedelta(days=interval)
            review_schedule.append({
                "original_session": session["session_number"],
                "review_date": review_date.strftime("%d.%m.%Y"),
                "interval_days": interval,
                "topics": session["topics"],
                "type": "review"
            })
    
    return {
        "intervals": intervals,
        "schedule": review_schedule,
        "total_reviews": len(review_schedule),
        "review_strategy": "spaced_repetition"
    }

def _generate_smart_milestones(topics: List[Dict], sessions: List[Dict], analysis: Dict) -> List[Dict]:
    """Генерация умных контрольных точек"""
    
    milestones = []
    total_sessions = len(sessions)
    
    # Milestone 1: Завершение основ (25% прогресса)
    foundation_session = max(1, total_sessions // 4)
    milestones.append({
        "session": foundation_session,
        "title": "Освоение основ",
        "description": "Понимание базовых концепций и терминологии",
        "criteria": [
            "Знание всех ключевых определений",
            "Способность объяснить основные концепции",
            "Успешное выполнение 80% базовых флеш-карт"
        ],
        "reward": "🎯 Базовый уровень достигнут!",
        "progress_percent": 25
    })
    
    # Milestone 2: Развитие навыков (50% прогресса)
    development_session = max(2, total_sessions // 2)
    milestones.append({
        "session": development_session,
        "title": "Развитие навыков",
        "description": "Применение знаний и установление связей",
        "criteria": [
            "Решение практических задач",
            "Установление связей между темами",
            "Создание собственных примеров"
        ],
        "reward": "🚀 Продвинутый уровень достигнут!",
        "progress_percent": 50
    })
    
    # Milestone 3: Мастерство (75% прогресса)
    mastery_session = max(3, 3 * total_sessions // 4)
    milestones.append({
        "session": mastery_session,
        "title": "Достижение мастерства",
        "description": "Экспертное понимание и критическое мышление",
        "criteria": [
            "Критический анализ информации",
            "Создание новых решений",
            "Обучение других"
        ],
        "reward": "🏆 Экспертный уровень достигнут!",
        "progress_percent": 75
    })
    
    # Final Milestone: Завершение курса (100% прогресса)
    milestones.append({
        "session": total_sessions,
        "title": "Завершение изучения",
        "description": "Полное освоение материала",
        "criteria": [
            "Успешное прохождение всех флеш-карт",
            "Демонстрация экспертных знаний",
            "Готовность к практическому применению"
        ],
        "reward": "🎓 Курс успешно завершен!",
        "progress_percent": 100
    })
    
    return milestones

def _create_adaptive_features(analysis: Dict) -> Dict:
    """Создание адаптивных функций плана"""
    
    return {
        "difficulty_adjustment": {
            "enabled": True,
            "description": "Автоматическая корректировка сложности на основе прогресса",
            "triggers": [
                "Низкая успеваемость по флеш-картам (<70%)",
                "Слишком быстрое прохождение материала (>95%)",
                "Пропуск сессий"
            ]
        },
        "personalization": {
            "learning_style": "adaptive",
            "pace_adjustment": True,
            "content_recommendations": True
        },
        "progress_tracking": {
            "metrics": ["completion_rate", "accuracy", "time_spent", "retention"],
            "feedback_frequency": "after_each_session",
            "improvement_suggestions": True
        }
    }

def _create_learning_path_visualization(sessions: List[Dict]) -> List[Dict]:
    """Создание визуализации пути обучения"""
    
    path = []
    for i, session in enumerate(sessions):
        path.append({
            "step": i + 1,
            "session_id": session["session_number"],
            "title": session["main_topic"]["title"],
            "phase": session["phase_name"],
            "difficulty": session["estimated_difficulty"],
            "duration": session["duration_minutes"],
            "date": session["date"],
            "prerequisites": path[-1]["title"] if path else None,
            "progress_percent": round((i + 1) / len(sessions) * 100, 1)
        })
    
    return path

def _define_success_metrics(topics: List[Dict], flashcards: List[Dict]) -> Dict:
    """Определение метрик успеха"""
    
    return {
        "knowledge_retention": {
            "target": 85,
            "description": "Процент правильных ответов на флеш-карты через неделю после изучения"
        },
        "concept_understanding": {
            "target": 80,
            "description": "Способность объяснить концепции своими словами"
        },
        "practical_application": {
            "target": 75,
            "description": "Успешное решение практических задач"
        },
        "completion_rate": {
            "target": 90,
            "description": "Процент завершенных учебных сессий"
        },
        "overall_satisfaction": {
            "target": 8,
            "description": "Общая оценка удовлетворенности обучением (из 10)"
        }
    }

def _generate_fallback_plan() -> Dict:
    """Базовый план на случай ошибки"""
    
    return {
        "sessions": [{
            "session_number": 1,
            "date": datetime.now().strftime("%d.%m.%Y"),
            "duration_minutes": 45,
            "topics": ["Изучение материала"],
            "activities": [{"type": "study", "name": "Изучение", "duration": 45}]
        }],
        "milestones": [{"title": "Изучить материал", "progress_percent": 100}],
        "total_hours": 0.75,
        "estimated_completion": (datetime.now() + timedelta(days=7)).strftime("%d.%m.%Y")
    }

# Пример использования
if __name__ == "__main__":
    # Тестовые данные
    test_topics = [
        {"title": "Основы машинного обучения", "complexity": "basic", "key_concepts": ["алгоритм", "данные"]},
        {"title": "Нейронные сети", "complexity": "advanced", "key_concepts": ["нейрон", "веса", "активация"]}
    ]
    
    test_flashcards = [
        {"difficulty": 1, "type": "definition"},
        {"difficulty": 2, "type": "concept"},
        {"difficulty": 3, "type": "application"}
    ]
    
    plan = generate_enhanced_study_plan(test_topics, test_flashcards, 5000)
    print(json.dumps(plan, indent=2, ensure_ascii=False))