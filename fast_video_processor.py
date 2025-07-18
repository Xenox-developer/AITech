#!/usr/bin/env python3
"""
ЭКСПРЕСС-ОБРАБОТЧИК ВИДЕО
Цель: обработка 5-минутного видео за 1-2 минуты максимум
"""

import os
import json
import time
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any
from dotenv import load_dotenv
import whisperx
import torch
from openai import OpenAI
from collections import Counter
import re

# Загружаем переменные окружения из .env файла
load_dotenv()

logger = logging.getLogger(__name__)

class FastVideoProcessor:
    def __init__(self):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.compute_type = "float16" if self.device == "cuda" else "int8"
        self.whisper_model = None
        self.openai_client = None
        self._load_models()
    
    def _load_models(self):
        """Загрузка только необходимых моделей"""
        try:
            # Загружаем более быструю модель Whisper
            logger.info("Loading FAST Whisper model...")
            self.whisper_model = whisperx.load_model("base", self.device, compute_type=self.compute_type)
            logger.info("Fast Whisper model loaded")
            
            # OpenAI клиент
            api_key = os.environ.get('OPENAI_API_KEY')
            if api_key:
                self.openai_client = OpenAI(api_key=api_key)
                logger.info("OpenAI client initialized")
            else:
                logger.warning("No OpenAI API key - will use fallback methods")
                
        except Exception as e:
            logger.error(f"Error loading models: {e}")
            raise
    
    def process_video_express(self, filepath: str, filename: str) -> Dict[str, Any]:
        """ЭКСПРЕСС-обработка видео за 1-2 минуты"""
        start_time = time.time()
        logger.info(f"🚀 ЭКСПРЕСС-режим: {filename}")
        
        try:
            # ЭТАП 1: Быстрая транскрипция (30-60 сек)
            logger.info("⚡ Этап 1/4: Быстрая транскрипция...")
            transcription_start = time.time()
            video_data = self._transcribe_express(filepath)
            transcription_time = time.time() - transcription_start
            logger.info(f"✅ Транскрипция за {transcription_time:.1f}с")
            
            text = video_data['full_text']
            if len(text.strip()) < 20:
                raise ValueError("Слишком мало текста для анализа")
            
            # ЭТАП 2: Экспресс-анализ тем (15-30 сек)
            logger.info("⚡ Этап 2/4: Анализ тем...")
            topics_start = time.time()
            topics_data = self._extract_topics_express(text)
            topics_time = time.time() - topics_start
            logger.info(f"✅ Темы за {topics_time:.1f}с")
            
            # ЭТАП 3: Быстрое резюме (10-20 сек)
            logger.info("⚡ Этап 3/4: Резюме...")
            summary_start = time.time()
            summary = self._generate_summary_express(text)
            summary_time = time.time() - summary_start
            logger.info(f"✅ Резюме за {summary_time:.1f}с")
            
            # ЭТАП 4: Экспресс флеш-карты (10-20 сек)
            logger.info("⚡ Этап 4/4: Флеш-карты...")
            cards_start = time.time()
            flashcards = self._generate_flashcards_express(text, topics_data['main_topics'])
            cards_time = time.time() - cards_start
            logger.info(f"✅ Флеш-карты за {cards_time:.1f}с")
            
            # Быстрая генерация остального
            mind_map = self._generate_mind_map_simple(topics_data['main_topics'])
            study_plan = self._generate_study_plan_simple(topics_data['main_topics'], len(flashcards))
            quality = self._assess_quality_simple(text, topics_data['main_topics'])
            
            total_time = time.time() - start_time
            
            result = {
                "topics_data": topics_data,
                "summary": summary,
                "flashcards": flashcards,
                "mind_map": mind_map,
                "study_plan": study_plan,
                "quality_assessment": quality,
                "video_segments": video_data.get('segments', []),
                "key_moments": video_data.get('key_moments', []),
                "metadata": {
                    "filename": filename,
                    "file_type": ".mp4",
                    "text_length": len(text),
                    "processing_date": datetime.now().isoformat(),
                    "processing_time": round(total_time, 1),
                    "express_mode": True,
                    "timing": {
                        "transcription": round(transcription_time, 1),
                        "topics": round(topics_time, 1),
                        "summary": round(summary_time, 1),
                        "flashcards": round(cards_time, 1),
                        "total": round(total_time, 1)
                    }
                }
            }
            
            logger.info(f"🎉 ЭКСПРЕСС-обработка завершена за {total_time:.1f}с!")
            return result
            
        except Exception as e:
            logger.error(f"Ошибка экспресс-обработки: {e}")
            raise
    
    def _transcribe_express(self, filepath: str) -> Dict[str, Any]:
        """Быстрая транскрипция ВСЕГО видео с оптимизациями"""
        try:
            # Загружаем аудио
            audio = whisperx.load_audio(filepath)
            duration = len(audio) / 16000
            logger.info(f"🎬 Полное видео: {duration:.1f}с ({duration/60:.1f} мин)")
            
            # НОВАЯ ЛОГИКА: Обрабатываем все видео, но с разными оптимизациями
            if duration > 3600:  # Более 1 часа
                logger.info("📚 Очень длинное видео (>1ч) - используем batch_size=1 для стабильности")
                batch_size = 1
            elif duration > 1800:  # Более 30 минут
                logger.info("📖 Длинное видео (>30мин) - используем batch_size=2")
                batch_size = 2
            elif duration > 600:  # Более 10 минут
                logger.info("📄 Среднее видео (>10мин) - используем batch_size=4")
                batch_size = 4
            else:
                logger.info("📝 Короткое видео (<10мин) - используем batch_size=8")
                batch_size = 8
            
            # Транскрипция ВСЕГО видео с оптимизированным batch_size
            logger.info(f"🎤 Транскрибируем все {duration:.0f}с с batch_size={batch_size}")
            result = self.whisper_model.transcribe(audio, batch_size=batch_size)
            
            # Простая обработка без выравнивания
            segments = []
            full_text = ""
            
            for segment in result.get("segments", []):
                text = segment.get("text", "").strip()
                if text:
                    full_text += text + " "
                    segments.append({
                        "start": round(segment.get("start", 0)),
                        "end": round(segment.get("end", 0)),
                        "text": text,
                        "importance": 0.5
                    })
            
            # Простые ключевые моменты
            key_moments = []
            if segments:
                # Берем первый, средний и последний сегмент
                indices = [0, len(segments)//2, -1] if len(segments) > 2 else [0]
                for i in indices:
                    if i < len(segments):
                        seg = segments[i]
                        key_moments.append({
                            "time": seg["start"],
                            "description": seg["text"][:80] + "...",
                            "importance": 0.7
                        })
            
            return {
                "full_text": full_text.strip(),
                "segments": segments,
                "key_moments": key_moments,
                "language": result.get("language", "unknown"),
                "total_duration": duration
            }
            
        except Exception as e:
            logger.error(f"Ошибка быстрой транскрипции: {e}")
            raise
    
    def _extract_topics_express(self, text: str) -> Dict[str, Any]:
        """Экспресс-извлечение тем"""
        try:
            if self.openai_client and len(text) > 100:
                return self._extract_topics_with_api(text)
            else:
                return self._extract_topics_local(text)
        except Exception as e:
            logger.warning(f"Ошибка извлечения тем: {e}")
            return self._extract_topics_local(text)
    
    def _extract_topics_with_api(self, text: str) -> Dict[str, Any]:
        """Умное извлечение тем через API с обработкой длинных текстов"""
        original_length = len(text)
        logger.info(f"📝 Анализируем текст: {original_length} символов")
        
        # Умная обработка длинных текстов
        if original_length > 80000:  # Очень длинный текст (>1.5 часа видео)
            logger.info("📚 Очень длинный текст - используем сегментацию")
            text = self._smart_text_segmentation(text, 60000)
        elif original_length > 40000:  # Длинный текст (>45 мин видео)
            logger.info("📖 Длинный текст - берем ключевые части")
            text = self._extract_key_parts(text, 35000)
        elif original_length > 20000:  # Средний текст (>20 мин видео)
            logger.info("📄 Средний текст - легкое сокращение")
            text = text[:18000] + "\n\n[...часть пропущена...]\n\n" + text[-2000:]
        
        logger.info(f"✂️ Оптимизированный текст: {len(text)} символов")
        
        prompt = f"""Проанализируй учебный материал и извлеки структурированную информацию.

Верни JSON в следующем формате:
{{
  "main_topics": [
    {{
      "title": "Краткое, понятное название темы",
      "summary": "Объяснение темы своими словами (2-3 предложения)",
      "subtopics": ["Подтема 1", "Подтема 2"],
      "key_concepts": ["Ключевое понятие 1", "Ключевое понятие 2"],
      "complexity": "basic/intermediate/advanced",
      "examples": ["Конкретный пример применения"],
      "why_important": "Почему эта тема важна для понимания материала"
    }}
  ],
  "concept_map": {{
    "relationships": [
      {{
        "from": "Тема 1",
        "to": "Тема 2", 
        "type": "causes/requires/similar/contrast/part_of",
        "description": "Краткое описание связи"
      }}
    ]
  }},
  "learning_objectives": ["Что студент должен понять после изучения"],
  "prerequisites": ["Что нужно знать до изучения этого материала"]
}}

ВАЖНО:
1. НЕ копируй текст дословно! Переформулируй своими словами
2. Создай осмысленные названия тем
3. Извлеки 5-8 главных тем
4. Каждая тема должна быть логически завершенной
5. Примеры должны быть конкретными и практичными

Текст для анализа: {text}"""
        
        response = self.openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Ты - эксперт по созданию учебных материалов. Извлекай осмысленные темы, а не копируй текст."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=2000,  # Увеличено с 800
            timeout=30,  # Увеличено с 20
            response_format={"type": "json_object"}
        )
        
        data = json.loads(response.choices[0].message.content)
        
        # Добавляем недостающие поля
        for topic in data.get("main_topics", []):
            topic.setdefault("subtopics", [])
            topic.setdefault("examples", [])
            topic.setdefault("why_important", "Важная тема")
        
        data.setdefault("learning_objectives", ["Изучить основные темы"])
        data.setdefault("concept_map", {"relationships": []})
        data.setdefault("prerequisites", [])
        
        return data
    
    def _smart_text_segmentation(self, text: str, target_length: int) -> str:
        """Умная сегментация длинного текста с сохранением контекста"""
        try:
            # Разбиваем на предложения
            sentences = text.split('. ')
            
            # Берем начало (40%), середину (30%) и конец (30%)
            total_sentences = len(sentences)
            
            start_count = int(total_sentences * 0.4)
            middle_start = int(total_sentences * 0.35)
            middle_count = int(total_sentences * 0.3)
            end_start = int(total_sentences * 0.7)
            
            # Собираем ключевые части
            start_part = '. '.join(sentences[:start_count])
            middle_part = '. '.join(sentences[middle_start:middle_start + middle_count])
            end_part = '. '.join(sentences[end_start:])
            
            # Объединяем с разделителями
            segmented_text = (
                start_part + 
                "\n\n[...переход к середине лекции...]\n\n" + 
                middle_part + 
                "\n\n[...переход к заключению...]\n\n" + 
                end_part
            )
            
            # Если все еще слишком длинно, обрезаем
            if len(segmented_text) > target_length:
                segmented_text = segmented_text[:target_length] + "\n\n[...текст обрезан...]"
            
            logger.info(f"📚 Сегментация: {len(text)} → {len(segmented_text)} символов")
            return segmented_text
            
        except Exception as e:
            logger.warning(f"Ошибка сегментации: {e}")
            # Fallback к простому обрезанию
            return text[:target_length] + "..."
    
    def _extract_key_parts(self, text: str, target_length: int) -> str:
        """Извлечение ключевых частей текста"""
        try:
            # Ищем ключевые слова и фразы
            key_indicators = [
                'важно', 'главное', 'основное', 'ключевое', 'заключение', 
                'итак', 'таким образом', 'в результате', 'следовательно',
                'например', 'к примеру', 'рассмотрим', 'определение',
                'first', 'second', 'third', 'finally', 'conclusion',
                'important', 'key', 'main', 'essential', 'summary'
            ]
            
            sentences = text.split('. ')
            key_sentences = []
            regular_sentences = []
            
            # Разделяем на ключевые и обычные предложения
            for sentence in sentences:
                sentence_lower = sentence.lower()
                if any(indicator in sentence_lower for indicator in key_indicators):
                    key_sentences.append(sentence)
                else:
                    regular_sentences.append(sentence)
            
            # Начинаем с ключевых предложений
            result_text = '. '.join(key_sentences)
            
            # Добавляем обычные предложения до достижения лимита
            if len(result_text) < target_length:
                remaining_length = target_length - len(result_text)
                
                # Берем начало и конец обычных предложений
                if regular_sentences:
                    start_count = len(regular_sentences) // 3
                    end_count = len(regular_sentences) // 3
                    
                    additional_text = (
                        '. '.join(regular_sentences[:start_count]) + 
                        "\n\n[...основная часть...]\n\n" +
                        '. '.join(regular_sentences[-end_count:])
                    )
                    
                    if len(additional_text) <= remaining_length:
                        result_text += "\n\n" + additional_text
                    else:
                        result_text += "\n\n" + additional_text[:remaining_length]
            
            logger.info(f"📖 Извлечение ключевых частей: {len(text)} → {len(result_text)} символов")
            return result_text
            
        except Exception as e:
            logger.warning(f"Ошибка извлечения ключевых частей: {e}")
            # Fallback к простому обрезанию
            return text[:target_length] + "..."
    
    def _extract_topics_local(self, text: str) -> Dict[str, Any]:
        """Локальное извлечение тем без API"""
        # Простой анализ частотности слов
        words = re.findall(r'\b[а-яё]{4,}\b', text.lower())
        word_freq = Counter(words)
        
        topics = []
        for word, freq in word_freq.most_common(5):
            if freq > 2:
                topics.append({
                    "title": word.capitalize(),
                    "summary": f"Тема связанная с {word}",
                    "subtopics": [],
                    "key_concepts": [word],
                    "complexity": "basic",
                    "examples": [],
                    "why_important": f"Часто упоминается ({freq} раз)"
                })
        
        if not topics:
            topics = [{
                "title": "Основная тема видео",
                "summary": "Содержание видео",
                "subtopics": [],
                "key_concepts": [],
                "complexity": "basic",
                "examples": [],
                "why_important": "Основное содержание"
            }]
        
        return {
            "main_topics": topics,
            "learning_objectives": ["Изучить основные темы"],
            "concept_map": {"relationships": []},
            "prerequisites": []
        }
    
    def _generate_summary_express(self, text: str) -> str:
        """Экспресс-резюме"""
        try:
            if self.openai_client and len(text) > 100:
                # Ограничиваем текст
                if len(text) > 15000:
                    text = text[:15000] + "..."
                
                response = self.openai_client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{
                        "role": "user", 
                        "content": f"Создай краткое резюме (максимум 150 слов):\n\n{text}"
                    }],
                    temperature=0.3,
                    max_tokens=300,
                    timeout=15
                )
                
                return response.choices[0].message.content.strip()
            else:
                # Простое резюме
                sentences = text.split('.')[:5]  # Первые 5 предложений
                return "## Краткое содержание\n" + ". ".join(sentences) + "."
                
        except Exception as e:
            logger.warning(f"Ошибка резюме: {e}")
            return "## Краткое содержание\nВидео содержит важную информацию для изучения."
    
    def _generate_flashcards_express(self, text: str, topics: List[Dict]) -> List[Dict]:
        """Экспресс флеш-карты"""
        try:
            if self.openai_client and len(text) > 100:
                # Ограничиваем текст
                if len(text) > 12000:
                    text = text[:12000] + "..."
                
                response = self.openai_client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{
                        "role": "user",
                        "content": f"""Создай 5 простых флеш-карт по тексту в JSON:
[{{"q": "Вопрос", "a": "Ответ", "type": "definition", "difficulty": 1}}]

Текст: {text}"""
                    }],
                    temperature=0.2,
                    max_tokens=800,
                    timeout=15,
                    response_format={"type": "json_object"}
                )
                
                content = response.choices[0].message.content
                if content.startswith('['):
                    cards = json.loads(content)
                else:
                    data = json.loads(content)
                    cards = data.get('flashcards', data.get('cards', []))
                
                # Добавляем недостающие поля
                for i, card in enumerate(cards):
                    card.setdefault("hint", "Подсказка")
                    card.setdefault("related_topics", [])
                    card.setdefault("memory_hook", "Запомните")
                    card.setdefault("common_mistakes", "Будьте внимательны")
                    card.setdefault("text_reference", f"Карта {i+1}")
                
                return cards[:5]
            else:
                # Простые карты на основе тем
                cards = []
                for i, topic in enumerate(topics[:5]):
                    cards.append({
                        "type": "definition",
                        "q": f"Что такое {topic['title']}?",
                        "a": topic['summary'],
                        "difficulty": 1,
                        "hint": "Основная тема",
                        "related_topics": [topic['title']],
                        "memory_hook": f"Запомните: {topic['title']}",
                        "common_mistakes": "Внимательно изучите",
                        "text_reference": f"Тема {i+1}"
                    })
                return cards
                
        except Exception as e:
            logger.warning(f"Ошибка флеш-карт: {e}")
            return [{
                "type": "basic",
                "q": "Что изучалось в видео?",
                "a": "Важная информация",
                "difficulty": 1,
                "hint": "Основное содержание",
                "related_topics": ["Видео"],
                "memory_hook": "Изученный материал",
                "common_mistakes": "Внимательно изучите",
                "text_reference": "Основное содержание"
            }]
    
    def _generate_mind_map_simple(self, topics: List[Dict]) -> Dict:
        """Простая ментальная карта"""
        branches = []
        colors = ["#FF6B6B", "#4ECDC4", "#45B7D1", "#96CEB4", "#FECA57"]
        
        for i, topic in enumerate(topics[:5]):
            branches.append({
                "name": topic['title'][:30],
                "importance": 0.9 - (i * 0.1),
                "color": colors[i % len(colors)],
                "children": [{"name": concept[:20], "importance": 0.5, "color": colors[i % len(colors)]} 
                           for concept in topic.get('key_concepts', [])[:3]]
            })
        
        return {
            "central_topic": topics[0]['title'] if topics else "Видео",
            "branches": branches
        }
    
    def _generate_study_plan_simple(self, topics: List[Dict], flashcard_count: int) -> Dict:
        """Простой план обучения с совместимостью"""
        main_topic = topics[0] if topics else {"title": "Видео", "complexity": "basic"}
        
        return {
            "sessions": [{
                "session_number": 1,
                "date": datetime.now().strftime("%d.%m.%Y"),
                "duration_minutes": 30,
                "topics": [topic['title'] for topic in topics[:3]],
                "focus": "Изучение основных тем",
                "exercises": ["Просмотр видео", "Изучение флеш-карт", "Повторение"],
                "flashcards_count": flashcard_count,
                "main_topic": main_topic,  # Добавляем для совместимости с шаблоном
                "phase_name": "Основы",
                "activities": []
            }],
            "milestones": [{
                "title": "Изучить видео",
                "progress_percent": 100,
                "session": 1,
                "description": "Основное изучение"
            }],
            "review_schedule": [1, 3, 7],
            "total_hours": 0.5,
            "completion_date": (datetime.now() + timedelta(days=3)).strftime("%d.%m.%Y"),
            "difficulty_level": 1.2,  # Добавляем для совместимости с шаблоном
            "material_analysis": {
                "overall_difficulty": 1.5,
                "estimated_study_time": {
                    "total_hours": 0.5,
                    "study_time": 20,
                    "review_time": 10,
                    "reading_time": 0
                }
            },
            "adaptive_features": {
                "difficulty_adjustment": False,
                "personalized_pace": True,
                "progress_tracking": True
            },
            "success_metrics": {
                "target_retention": 80,
                "target_completion": 85,
                "target_satisfaction": 8
            }
        }
    
    def _assess_quality_simple(self, text: str, topics: List[Dict]) -> Dict:
        """Простая оценка качества"""
        return {
            "depth_score": min(0.8, len(topics) / 5),
            "coverage_score": min(0.8, len(text) / 1000),
            "practical_score": 0.6,
            "clarity_score": 0.7,
            "overall_score": 0.7,
            "suggestions": ["Материал обработан в экспресс-режиме"]
        }

# Функция для интеграции с основным приложением
def process_video_fast(filepath: str, filename: str) -> Dict[str, Any]:
    """Быстрая обработка видео - основная функция"""
    processor = FastVideoProcessor()
    return processor.process_video_express(filepath, filename)

if __name__ == "__main__":
    # Тест
    import sys
    if len(sys.argv) > 1:
        test_file = sys.argv[1]
        if os.path.exists(test_file):
            result = process_video_fast(test_file, os.path.basename(test_file))
            print(f"Обработка завершена за {result['metadata']['processing_time']}с")
            print(f"Найдено тем: {len(result['topics_data']['main_topics'])}")
            print(f"Создано карт: {len(result['flashcards'])}")
        else:
            print(f"Файл не найден: {test_file}")
    else:
        print("Использование: python fast_video_processor.py <путь_к_видео>")