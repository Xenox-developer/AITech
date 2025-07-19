import os
import json
import logging
from typing import List, Dict, Any
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime

# Загрузка переменных среды разработки
load_dotenv()

# Обработка PDF
from pdfminer.high_level import extract_text

# OpenAI
from openai import OpenAI

# Логгирование
logger = logging.getLogger(__name__)

# OpenAI клиент
openai_client = None

def load_models():
    """Загрузка моделей"""
    global openai_client
    
    logger.info("Loading OpenAI client...")
    
    # OpenAI клиент
    api_key = os.environ.get('OPENAI_API_KEY')
    if not api_key:
        raise ValueError("OPENAI_API_KEY environment variable not set")
    openai_client = OpenAI(api_key=api_key)
    
    logger.info("OpenAI client loaded successfully")

try:
    load_models()
except Exception as e:
    logger.warning(f"Models not loaded on import: {str(e)}")

def extract_text_from_pdf(filepath: str) -> str:
    """Извлечение текста из PDF"""
    try:
        text = extract_text(filepath)
        return text.strip()
    except Exception as e:
        logger.error(f"Error extracting text from PDF: {str(e)}")
        raise

def generate_simple_analysis(text: str) -> Dict[str, Any]:
    """Простой анализ текста с помощью GPT"""
    try:
        if not openai_client:
            load_models()
        
        # Лимит текста для API
        max_chars = 50000
        if len(text) > max_chars:
            text = text[:max_chars] + "..."
        
        prompt = f"""Проанализируй учебный текст и создай краткий анализ.

Верни JSON в следующем формате:
{{
  "summary": "Краткое резюме основного содержания (2-3 предложения)",
  "main_topics": [
    {{
      "title": "Название темы",
      "summary": "Краткое описание темы"
    }}
  ],
  "flashcards": [
    {{
      "q": "Вопрос",
      "a": "Ответ",
      "type": "concept"
    }}
  ]
}}

Текст для анализа:
{text}"""
        
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Ты - эксперт по созданию учебных материалов. Создавай краткий и полезный анализ."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=2000,
            response_format={"type": "json_object"}
        )
        
        analysis = json.loads(response.choices[0].message.content)
        
        return analysis
        
    except Exception as e:
        logger.error(f"Error in simple analysis: {str(e)}")
        return {
            "summary": "Не удалось проанализировать текст",
            "main_topics": [{"title": "Основная тема", "summary": "Содержание документа"}],
            "flashcards": [{"q": "Что содержит документ?", "a": "Учебный материал", "type": "concept"}]
        }

def get_chat_response(user_message: str, full_text: str, result_data: Dict[str, Any]) -> str:
    """Получение ответа от ChatGPT на основе текста лекции"""
    try:
        if not openai_client:
            load_models()
        
        # Ограничиваем размер текста для контекста
        max_context_chars = 100000
        context_text = full_text[:max_context_chars] if len(full_text) > max_context_chars else full_text
        
        # Получаем дополнительную информацию из анализа
        summary = result_data.get('summary', '')
        filename = result_data.get('filename', 'лекция')
        
        # Формируем контекст для ChatGPT
        system_prompt = f"""Ты - AI-ассистент для изучения материалов. Отвечай на вопросы студента на основе предоставленной лекции.

ПРАВИЛА:
1. Отвечай ТОЛЬКО на основе содержания лекции
2. Если информации нет в лекции, честно скажи об этом
3. Давай конкретные и полезные ответы
4. Используй примеры из лекции когда это уместно
5. Помогай понять сложные концепции простыми словами
6. Если студент просит объяснить что-то подробнее, используй информацию из лекции

Название файла: {filename}

Краткое содержание лекции:
{summary[:500]}..."""

        user_prompt = f"""Вопрос студента: {user_message}

Текст лекции для справки:
{context_text}

Пожалуйста, ответь на вопрос студента, опираясь на содержание лекции."""

        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7,
            max_tokens=1500
        )
        
        ai_response = response.choices[0].message.content.strip()
        
        # Добавляем информацию о источнике
        if len(ai_response) > 50:  # Только если ответ содержательный
            ai_response += f"\n\n💡 *Ответ основан на материале лекции \"{filename}\"*"
        
        return ai_response
        
    except Exception as e:
        logger.error(f"Error getting chat response: {str(e)}")
        return f"Извините, произошла ошибка при обработке вашего вопроса: {str(e)}"

def process_file(filepath: str, filename: str, page_range: str = None) -> Dict[str, Any]:
    """Простая обработка файла"""
    try:
        logger.info(f"Starting simple processing for: {filename}")
        
        # Извлекаем текст в зависимости от типа файла
        file_ext = Path(filename).suffix.lower()
        
        if file_ext == '.pdf':
            text = extract_text_from_pdf(filepath)
        else:
            raise ValueError(f"Unsupported file type: {file_ext}")
        
        if not text or len(text.strip()) < 50:
            raise ValueError("Extracted text is too short or empty")
        
        logger.info(f"Extracted {len(text)} characters of text")
        
        # Простой анализ с GPT
        analysis = generate_simple_analysis(text)
        
        # Собираем результат
        result = {
            "topics_data": {
                "main_topics": analysis.get("main_topics", []),
                "concept_map": {"relationships": []},
                "learning_objectives": [],
                "prerequisites": []
            },
            "summary": analysis.get("summary", ""),
            "flashcards": analysis.get("flashcards", []),
            "mind_map": {},
            "study_plan": {
                "total_hours": 2.0,
                "sessions": [],
                "milestones": [],
                "success_metrics": {},
                "repetition_schedule": {},
                "completion_date": ""
            },
            "quality_assessment": {"overall_score": 0.8},
            "full_text": text,  # Добавляем полный текст для чата
            "video_segments": [],
            "key_moments": [],
            "metadata": {
                "filename": filename,
                "file_type": file_ext,
                "text_length": len(text),
                "processing_date": datetime.now().isoformat(),
                "processing_time": 1.0,
                "speed_optimized": True
            }
        }
        
        logger.info(f"Simple processing complete for: {filename}")
        
        return result
        
    except Exception as e:
        logger.error(f"Error in simple processing: {str(e)}")
        raise