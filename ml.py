import os
import json
import logging
import re
from typing import List, Dict, Tuple, Any
import numpy as np
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime, timedelta

# Загрузка переменных среды разработки
load_dotenv()

# Обработка PDF
from pdfminer.high_level import extract_text

# Обработка видео/аудио
import whisperx
import torch

# NLP
from sentence_transformers import SentenceTransformer
from sklearn.cluster import HDBSCAN
from sklearn.preprocessing import normalize
import nltk
from nltk.tokenize import sent_tokenize, word_tokenize
from collections import Counter

from openai import OpenAI

try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt')

# Логгирование
logger = logging.getLogger(__name__)

# Инициализация моделей
device = "cuda" if torch.cuda.is_available() else "cpu"
compute_type = "float16" if device == "cuda" else "int8"

# Глобальные переменные для моделей
sentence_model = None
whisper_model = None
openai_client = None

def load_models():
    """Загрузка моделей"""
    global sentence_model, whisper_model, openai_client
    
    logger.info("Loading models...")
    
    # Sentence transformer
    sentence_model = SentenceTransformer("intfloat/e5-large-v2", device=device)
    
    # Whisper для обработки аудио
    try:
        whisper_model = whisperx.load_model("large-v3", device, compute_type=compute_type)
    except Exception as e:
        logger.warning(f"Whisper model not loaded: {str(e)}")
    
    # OpenAI клиент
    api_key = os.environ.get('OPENAI_API_KEY')
    if not api_key:
        raise ValueError("OPENAI_API_KEY environment variable not set")
    openai_client = OpenAI(api_key=api_key)
    
    logger.info("Models loaded successfully")

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

def parse_page_range(page_range: str, max_pages: int = None) -> List[int]:
    """Парсинг диапазона страниц"""
    if not page_range or page_range.lower() in ['все', 'all']:
        if max_pages:
            return list(range(1, min(max_pages + 1, 21)))  # Максимум 20 страниц по умолчанию
        return []
    
    pages = set()
    
    # Разбиваем по запятым
    ranges = [r.strip() for r in page_range.split(',')]
    
    for range_str in ranges:
        if '-' in range_str:
            # Диапазон страниц
            try:
                start, end = map(int, range_str.split('-'))
                if start > end:
                    start, end = end, start
                pages.update(range(start, end + 1))
            except ValueError:
                logger.warning(f"Invalid page range: {range_str}")
                continue
        else:
            # Одна страница
            try:
                page = int(range_str)
                pages.add(page)
            except ValueError:
                logger.warning(f"Invalid page number: {range_str}")
                continue
    
    # Ограничиваем максимальным количеством страниц
    if max_pages:
        pages = {p for p in pages if 1 <= p <= max_pages}
    
    return sorted(list(pages))

def extract_text_from_pdf_with_pages(filepath: str, page_range: str = None) -> str:
    """Извлечение текста из PDF с выбором страниц"""
    try:
        from pdfminer.high_level import extract_text_to_fp
        from pdfminer.layout import LAParams
        from pdfminer.pdfpage import PDFPage
        from pdfminer.pdfinterp import PDFResourceManager, PDFPageInterpreter
        from pdfminer.converter import TextConverter
        import io
        
        if not page_range:
            # Если диапазон не указан, извлекаем весь текст (с ограничением)
            text = extract_text(filepath)
            # Ограничиваем размер текста (примерно 20 страниц)
            max_chars = 128000
            if len(text) > max_chars:
                text = text[:max_chars] + "\n\n[Текст обрезан для оптимизации обработки]"
                logger.info(f"Text truncated to {max_chars} characters")
            return text.strip()
        
        # Получаем общее количество страниц
        with open(filepath, 'rb') as file:
            pages_count = len(list(PDFPage.get_pages(file)))
        
        logger.info(f"PDF has {pages_count} pages")
        
        # Парсим диапазон страниц
        pages_to_extract = parse_page_range(page_range, pages_count)
        
        if not pages_to_extract:
            # Если диапазон пустой, берем первые 20 страниц
            pages_to_extract = list(range(1, min(pages_count + 1, 21)))
        
        logger.info(f"Extracting pages: {pages_to_extract}")
        
        # Извлекаем текст только с выбранных страниц
        output_string = io.StringIO()
        with open(filepath, 'rb') as file:
            rsrcmgr = PDFResourceManager()
            device = TextConverter(rsrcmgr, output_string, laparams=LAParams())
            interpreter = PDFPageInterpreter(rsrcmgr, device)
            
            # Конвертируем номера страниц в 0-based индексы
            page_indices = {p - 1 for p in pages_to_extract}
            
            for page_num, page in enumerate(PDFPage.get_pages(file)):
                if page_num in page_indices:
                    interpreter.process_page(page)
            
            device.close()
        
        text = output_string.getvalue()
        output_string.close()
        
        if not text.strip():
            logger.warning("No text extracted from specified pages, falling back to full extraction")
            return extract_text(filepath).strip()
        
        logger.info(f"Extracted {len(text)} characters from {len(pages_to_extract)} pages")
        return text.strip()
        
    except Exception as e:
        logger.error(f"Error extracting text from PDF pages: {str(e)}")
        # Fallback к обычному извлечению
        logger.info("Falling back to full PDF extraction")
        return extract_text(filepath).strip()

def transcribe_video_with_timestamps(filepath: str) -> Dict[str, Any]:
    """Транскрипция видео/аудио"""
    try:
        logger.info(f"Transcribing video with timestamps: {filepath}")
        
        # Загрузка аудио
        audio = whisperx.load_audio(filepath)
        
        # Транскрипция с временными отметками
        result = whisper_model.transcribe(audio, batch_size=16)
        
        # Сегменты процесса
        segments = []
        key_moments = []
        full_text = ""
        
        for i, segment in enumerate(result["segments"]):
            text = segment["text"].strip()
            start = segment["start"]
            end = segment["end"]
            
            full_text += text + " "
            
            # Анализ важности сегмента (на основе длины и ключевых слов)
            importance = min(1.0, len(text.split()) / 50)
            
            segments.append({
                "start": start,
                "end": end,
                "text": text,
                "importance": importance
            })
            
            # Определение ключевых моментов (более длинных сегментов с высокой важностью)
            if importance > 0.7 and len(text.split()) > 20:
                key_moments.append({
                    "time": start,
                    "description": text[:100] + "..." if len(text) > 100 else text
                })
        
        return {
            "full_text": full_text.strip(),
            "segments": segments,
            "key_moments": key_moments[:10]  # Топ 10 ключевых моментов
        }
        
    except Exception as e:
        logger.error(f"Error transcribing video: {str(e)}")
        return {"full_text": transcribe_video_simple(filepath), "segments": [], "key_moments": []}

def transcribe_video_simple(filepath: str) -> str:
    """Транскрипция видео без временных меток"""
    try:
        audio = whisperx.load_audio(filepath)
        result = whisper_model.transcribe(audio, batch_size=16)
        text = " ".join([segment["text"] for segment in result["segments"]])
        return text.strip()
    except Exception as e:
        logger.error(f"Error in simple transcription: {str(e)}")
        raise

def extract_topics_with_gpt(text: str) -> Dict[str, Any]:
    """Извлечение тематик с GPT"""
    try:
        if not openai_client:
            load_models()
        
        # Лимит текста для API
        max_chars = 128000
        if len(text) > max_chars:
            text = text[:max_chars] + "..."
        
        prompt = """Проанализируй учебный текст и извлеки структурированную информацию.

Верни JSON в следующем формате:
{
  "main_topics": [
    {
      "title": "Краткое, понятное название темы (не копия текста!)",
      "summary": "Объяснение темы своими словами (2-3 предложения)",
      "subtopics": ["Подтема 1", "Подтема 2"],
      "key_concepts": ["Ключевое понятие 1", "Ключевое понятие 2"],
      "complexity": "basic/intermediate/advanced",
      "examples": ["Конкретный пример применения"],
      "why_important": "Почему эта тема важна для понимания материала"
    }
  ],
  "concept_map": {
    "relationships": [
      {
        "from": "Тема 1",
        "to": "Тема 2", 
        "type": "causes/requires/similar/contrast/part_of",
        "description": "Краткое описание связи"
      }
    ]
  },
  "learning_objectives": ["Что студент должен понять после изучения"],
  "prerequisites": ["Что нужно знать до изучения этого материала"]
}

ВАЖНО:
1. НЕ копируй текст дословно! Переформулируй своими словами
2. Создай осмысленные названия тем (например: "Метрики качества классификации", а не "Соответствующий функционал называется...")
3. Извлеки 5-10 главных тем
4. Каждая тема должна быть логически завершенной
5. Примеры должны быть конкретными и практичными

Текст для анализа:"""
        
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Ты - эксперт по созданию учебных материалов. Извлекай осмысленные темы, а не копируй текст."},
                {"role": "user", "content": f"{prompt}\n\n{text}"}
            ],
            temperature=0.3,
            max_tokens=3000,
            response_format={"type": "json_object"}
        )
        
        topics_data = json.loads(response.choices[0].message.content)
        
        # Ensure all required fields
        for topic in topics_data.get("main_topics", []):
            topic.setdefault("why_important", "Важно для понимания материала")
            topic.setdefault("examples", [])
            topic.setdefault("subtopics", [])
            topic.setdefault("key_concepts", [])
        
        return topics_data
        
    except Exception as e:
        logger.error(f"Error extracting topics with GPT: {str(e)}")
        # Fallback to old method
        return extract_topics_fallback(text)

def extract_topics_fallback(text: str) -> Dict[str, Any]:
    """Извлечение тематик без GPT"""
    try:
        # Разбиваем на абзацы вместо предложений для лучшего понимания контекста
        paragraphs = [p.strip() for p in text.split('\n\n') if len(p.strip()) > 50]
        
        if len(paragraphs) < 3:
            # Если абзацев недостаточно, разбиваем их на предложения
            sentences = sent_tokenize(text)
            paragraphs = []
            for i in range(0, len(sentences), 3):
                paragraph = " ".join(sentences[i:i+3])
                if len(paragraph) > 50:
                    paragraphs.append(paragraph)
        
        if len(paragraphs) < 2:
            return {
                "main_topics": [{
                    "title": "Основная тема документа",
                    "summary": "Документ слишком короткий для детального анализа",
                    "subtopics": [],
                    "key_concepts": [],
                    "complexity": "basic",
                    "examples": [],
                    "why_important": "Основное содержание документа"
                }],
                "concept_map": {"relationships": []},
                "learning_objectives": ["Изучить содержание документа"],
                "prerequisites": []
            }
        
        # Генерация эмбеддингов для параграфа
        embeddings = sentence_model.encode(paragraphs, convert_to_tensor=False)
        embeddings = normalize(embeddings)
        
        # Иерархическая кластеризация
        min_cluster_size = max(2, min(5, len(paragraphs) // 5))
        clusterer = HDBSCAN(
            min_cluster_size=min_cluster_size,
            min_samples=1,
            metric='euclidean',
            cluster_selection_method='eom'
        )
        
        cluster_labels = clusterer.fit_predict(embeddings)
        
        # Извлечение тематик из кластеров
        main_topics = []
        unique_labels = set(cluster_labels)
        
        for label in unique_labels:
            if label == -1:
                continue
            
            # Получение абзацев в кластере
            cluster_paragraphs = [paragraphs[i] for i, l in enumerate(cluster_labels) if l == label]
            
            if not cluster_paragraphs:
                continue
            
            # Извлекаем осмысленный заголовок (не только первое предложение).
            title = extract_topic_title(cluster_paragraphs)
            
            # Суммаризация
            summary = create_topic_summary(cluster_paragraphs)
            
            # Основные концепты
            key_concepts = extract_key_concepts(" ".join(cluster_paragraphs))
            
            # Сложность
            complexity = determine_complexity(" ".join(cluster_paragraphs))
            
            # Примеры
            examples = extract_meaningful_examples(cluster_paragraphs)
            
            # Создание топика
            topic = {
                "title": title,
                "summary": summary,
                "subtopics": extract_subtopics_smart(cluster_paragraphs),
                "key_concepts": key_concepts[:5],
                "complexity": complexity,
                "examples": examples[:3],
                "why_important": f"Эта тема помогает понять {title.lower()}"
            }
            
            main_topics.append(topic)
        
        # Сортировка по важности
        main_topics.sort(key=lambda x: len(x["summary"]), reverse=True)
        
        # Извлечение взаимосвязи
        relationships = extract_smart_relationships(main_topics, text)
        
        # Выделение тем обучения
        learning_objectives = extract_learning_objectives(main_topics)
        
        return {
            "main_topics": main_topics[:10],
            "concept_map": {"relationships": relationships},
            "learning_objectives": learning_objectives,
            "prerequisites": []
        }
        
    except Exception as e:
        logger.error(f"Error in fallback topic extraction: {str(e)}")
        return {
            "main_topics": [{
                "title": "Ошибка анализа",
                "summary": "Не удалось извлечь темы из документа",
                "subtopics": [],
                "key_concepts": [],
                "complexity": "basic",
                "examples": [],
                "why_important": "Требуется ручной анализ"
            }],
            "concept_map": {"relationships": []},
            "learning_objectives": ["Изучить документ"],
            "prerequisites": []
        }

def extract_topic_title(paragraphs: List[str]) -> str:
    """Извлечение названий тематик из абзацев"""
    # Ищем заголовки или утверждения
    for para in paragraphs:
        lines = para.split('\n')
        for line in lines:
            if len(line) < 100 and (
                line.strip().startswith('§') or 
                line.strip()[0].isdigit() or
                line.isupper() or
                ':' in line[:50]
            ):
                title = line.strip()
                title = re.sub(r'^[§\d\s.]+', '', title)
                title = title.strip(':').strip()
                if len(title) > 10:
                    return title[:80]
    
    # Если заголовок не найдем, извлекаем фразу
    all_text = " ".join(paragraphs[:2])
    
    # Ищем ключевые концепты
    concept_patterns = [
        r'([А-Я][а-я]+(?:\s+[а-я]+){0,3})\s+(?:—|это|является|представляет)',
        r'(?:Рассмотрим|Изучим|Обсудим)\s+([а-я]+(?:\s+[а-я]+){0,3})',
        r'(?:задач[аи]|метод|алгоритм|функци[яи]|модел[ьи])\s+([а-я]+(?:\s+[а-я]+){0,2})'
    ]
    
    for pattern in concept_patterns:
        match = re.search(pattern, all_text, re.IGNORECASE)
        if match:
            title = match.group(1).strip()
            if len(title) > 10:
                return title.capitalize()
    
    words = word_tokenize(all_text.lower())
    important_words = [w for w in words if len(w) > 4 and w.isalpha()]
    word_freq = Counter(important_words)
    
    if word_freq:
        top_words = [word for word, _ in word_freq.most_common(3)]
        return " ".join(top_words).capitalize()
    
    return "Тема раздела"

def create_topic_summary(paragraphs: List[str]) -> str:
    """Резюмируем абзацы"""
    key_sentences = []
    
    for para in paragraphs:
        sentences = sent_tokenize(para)
        for sent in sentences:
            if any(marker in sent.lower() for marker in [
                'это', 'является', 'представляет', 'означает',
                'позволяет', 'используется', 'применяется',
                'можно', 'следует', 'необходимо'
            ]):
                key_sentences.append(sent)
                if len(key_sentences) >= 2:
                    break
    
    if not key_sentences:
        for para in paragraphs:
            sentences = sent_tokenize(para)
            for sent in sentences:
                if len(sent) > 30:
                    key_sentences.append(sent)
                    break
            if key_sentences:
                break
    
    summary = " ".join(key_sentences[:2])
    summary = re.sub(r'\$[^$]+\$', '[формула]', summary)
    summary = re.sub(r'[^\w\s\[\].,!?;:()-]', '', summary)
    
    return summary[:300]

def extract_subtopics_smart(paragraphs: List[str]) -> List[str]:
    """Извлекаем под-топики"""
    subtopics = []
    
    for para in paragraphs:
        if re.search(r'(?:включает|содержит|состоит из|различают|выделяют):', para, re.IGNORECASE):
            parts = para.split(':')
            if len(parts) > 1:
                items = re.split(r'[;,]', parts[1])
                for item in items[:4]:
                    item = item.strip()
                    if 10 < len(item) < 100:
                        subtopics.append(item)
        
        numbered = re.findall(r'\d+\)\s*([^.]+)\.', para)
        subtopics.extend([item.strip() for item in numbered[:4] if 10 < len(item) < 100])
    
    seen = set()
    unique_subtopics = []
    for topic in subtopics:
        if topic.lower() not in seen:
            seen.add(topic.lower())
            unique_subtopics.append(topic)
    
    return unique_subtopics[:5]

def extract_meaningful_examples(paragraphs: List[str]) -> List[str]:
    """Извлекаем примеры"""
    examples = []
    
    for para in paragraphs:
        sentences = sent_tokenize(para)
        for sent in sentences:
            if any(indicator in sent.lower() for indicator in [
                'например', 'к примеру', 'в частности', 'рассмотрим',
                'пусть', 'допустим', 'представим', 'возьмем'
            ]):
                example = sent.strip()
                for indicator in ['Например,', 'К примеру,', 'В частности,']:
                    example = example.replace(indicator, '').strip()
                
                if len(example) > 20:
                    examples.append(example)
            
            elif re.search(r'\d+\s*(?:%|процент|объект|элемент|класс)', sent) and len(sent) < 200:
                examples.append(sent.strip())
    
    return examples[:5]

def extract_smart_relationships(topics: List[Dict], text: str) -> List[Dict]:
    """Извлекаем связь между топиками"""
    relationships = []
    
    topic_keywords = {}
    for i, topic in enumerate(topics):
        keywords = set()
        keywords.update(word_tokenize(topic['title'].lower()))
        for concept in topic['key_concepts']:
            keywords.update(word_tokenize(concept.lower()))
        topic_keywords[i] = keywords
    
    relationship_patterns = {
        'causes': ['приводит к', 'вызывает', 'влияет на', 'определяет'],
        'requires': ['требует', 'необходим', 'нужен для', 'основан на'],
        'part_of': ['часть', 'включает', 'состоит из', 'содержит'],
        'contrast': ['в отличие от', 'напротив', 'однако', 'но'],
        'similar': ['похож', 'аналогично', 'также как', 'подобно']
    }
    
    sentences = sent_tokenize(text.lower())
    
    for i, topic1 in enumerate(topics):
        for j, topic2 in enumerate(topics):
            if i >= j:
                continue
            
            for sent in sentences:
                t1_found = any(kw in sent for kw in topic_keywords[i])
                t2_found = any(kw in sent for kw in topic_keywords[j])
                
                if t1_found and t2_found:
                    for rel_type, patterns in relationship_patterns.items():
                        if any(pattern in sent for pattern in patterns):
                            relationships.append({
                                "from": topic1['title'],
                                "to": topic2['title'],
                                "type": rel_type,
                                "description": f"{topic1['title']} {rel_type} {topic2['title']}"
                            })
                            break
                    
                    break
    
    return relationships[:10]

def extract_learning_objectives(topics: List[Dict]) -> List[str]:
    """Извлекаем темы для изучения из топиков"""
    objectives = []
    
    objective_verbs = [
        "Понимать", "Объяснять", "Применять", "Анализировать",
        "Различать", "Использовать", "Вычислять", "Определять"
    ]
    
    for topic in topics[:5]:
        verb = objective_verbs[len(objectives) % len(objective_verbs)]
        
        if topic['complexity'] == 'basic':
            objective = f"{verb} основные понятия {topic['title'].lower()}"
        elif topic['complexity'] == 'intermediate':
            objective = f"{verb} и применять {topic['title'].lower()}"
        else:
            objective = f"{verb} и решать сложные задачи по теме {topic['title'].lower()}"
        
        objectives.append(objective)
    
    objectives.extend([
        "Решать практические задачи по изученным темам",
        "Связывать теоретические концепции с практическим применением"
    ])
    
    return objectives[:7]

def extract_key_concepts(text: str) -> List[str]:
    """Извлекаем ключевые концепции"""
    concepts = []
    
    defined_terms = re.findall(
        r'(?:([А-Я][а-я]+(?:\s+[а-я]+){0,2})\s*(?:—|это|называется|является))',
        text
    )
    concepts.extend([term.strip() for term in defined_terms if len(term) > 5])
    
    parenthetical = re.findall(r'\(([A-Za-z]+(?:\s+[A-Za-z]+){0,2})\)', text)
    concepts.extend([term for term in parenthetical if len(term) > 3])
    
    emphasized = re.findall(r'«([^»]+)»', text)
    concepts.extend([term for term in emphasized if 5 < len(term) < 50])
    
    words = word_tokenize(text.lower())
    meaningful_words = [
        w for w in words 
        if len(w) > 4 and w.isalpha() and
        not w in ['можно', 'нужно', 'будет', 'может', 'этого', 'этому']
    ]
    
    word_freq = Counter(meaningful_words)
    
    for word, freq in word_freq.most_common(20):
        if freq > 3 and word not in [c.lower() for c in concepts]:
            if any(pattern in text.lower() for pattern in [
                f'{word} это',
                f'{word} является',
                f'{word} представляет',
                f'используя {word}',
                f'методом {word}'
            ]):
                concepts.append(word.capitalize())
    
    seen = set()
    unique_concepts = []
    for concept in concepts:
        if concept.lower() not in seen:
            seen.add(concept.lower())
            unique_concepts.append(concept)
    
    return unique_concepts[:15]

def determine_complexity(text: str) -> str:
    """Определяем сложность текста"""
    words = word_tokenize(text.lower())
    
    # Индикаторы сложности
    basic_words = ['основной', 'простой', 'базовый', 'элементарный', 'начальный']
    intermediate_words = ['применение', 'использование', 'алгоритм', 'метод', 'анализ']
    advanced_words = ['оптимизация', 'доказательство', 'теорема', 'сложность', 'производная']
    
    basic_count = sum(1 for w in words if w in basic_words)
    intermediate_count = sum(1 for w in words if w in intermediate_words)
    advanced_count = sum(1 for w in words if w in advanced_words)
    
    # Ищем формулы
    formula_count = len(re.findall(r'[∑∫∂∇∈∀∃]|\$[^$]+\$', text))
    
    sentences = sent_tokenize(text)
    avg_sentence_length = np.mean([len(word_tokenize(s)) for s in sentences]) if sentences else 0
    
    if advanced_count > 2 or formula_count > 5 or avg_sentence_length > 25:
        return "advanced"
    elif intermediate_count > 2 or formula_count > 2 or avg_sentence_length > 20:
        return "intermediate"
    else:
        return "basic"

def generate_summary(text: str) -> str:
    """Суммаризация с GPT"""
    try:
        if not openai_client:
            load_models()
        
        max_chars = 128000
        if len(text) > max_chars:
            text = text[:max_chars] + "..."
        
        prompt = """Создай МАКСИМАЛЬНО ИНФОРМАТИВНОЕ и СТРУКТУРИРОВАННОЕ резюме учебного материала.

Формат ответа:

🎯 ГЛАВНАЯ ИДЕЯ:
[2-3 предложения с основной мыслью всего материала. Объясни СУТЬ своими словами, а не пересказывай]

📊 КЛЮЧЕВЫЕ КОНЦЕПЦИИ:
• Концепция 1: определение + зачем нужна + где применяется
• Концепция 2: определение + как работает + примеры
• Концепция 3: определение + связь с другими концепциями
[4-6 самых важных концепций]

🔗 ВЗАИМОСВЯЗИ И ЛОГИКА:
• Как концепция A приводит к концепции B (причинно-следственная связь)
• Почему метод X лучше метода Y в ситуации Z
• Какие условия необходимы для применения концепции C
[3-4 важнейшие логические связи]

💡 ПРАКТИЧЕСКОЕ ПРИМЕНЕНИЕ:
• Конкретная область применения 1: как используется, какие задачи решает
• Конкретная область применения 2: реальные примеры, результаты
• Ограничения и когда НЕ применять
[2-3 практических аспекта]

⚡ КРИТИЧЕСКИ ВАЖНЫЕ ФАКТЫ:
• Ключевой факт 1 (что обязательно нужно понимать)
• Ключевой факт 2 (частая ошибка или заблуждение)
• Ключевой факт 3 (условие успешного применения)
• Ключевой факт 4 (связь с другими темами)

🧮 ФОРМУЛЫ И АЛГОРИТМЫ (если есть):
• Основная формула: что вычисляет, когда применять
• Алгоритм: пошаговое описание, входные/выходные данные
• Параметры: что означают, как выбирать

📈 РЕЗУЛЬТАТЫ И ВЫВОДЫ:
• Что мы получаем в итоге изучения этой темы
• Какие новые возможности открываются
• К каким следующим темам это ведет

Требования:
- МАКСИМУМ ИНФОРМАЦИИ в каждом пункте
- НЕ копируй текст, а ОБЪЯСНЯЙ суть
- Конкретные примеры и числа, если есть
- Указывай причины и следствия
- Максимум 400 слов общий объем
- Каждый раздел должен давать новое понимание
- Фокус на ПОНИМАНИИ связей и применении
- Пиши простым, но точным языком"""
        
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Ты - эксперт по созданию учебных материалов. НЕ копируй текст, а объясняй своими словами."},
                {"role": "user", "content": f"{prompt}\n\nТекст для анализа:\n{text}"}
            ],
            temperature=0.7,
            max_tokens=800
        )
        
        return response.choices[0].message.content.strip()
        
    except Exception as e:
        logger.error(f"Error generating advanced summary: {str(e)}")
        return "## 🎯 Главная идея\nНе удалось создать расширенное резюме из-за технической ошибки."

def generate_flashcards(text: str) -> List[Dict]:
    """Генерируем флеш-карты с GPT"""
    try:
        if not openai_client:
            load_models()
        
        max_chars = 128000
        if len(text) > max_chars:
            text = text[:max_chars] + "..."
        
        prompt = """Создай МНОГОУРОВНЕВЫЕ флеш-карты для эффективного изучения ДАННОГО КОНКРЕТНОГО ТЕКСТА.

КРИТИЧЕСКИ ВАЖНО:
1. ВСЕ ответы должны основываться ТОЛЬКО на информации из предоставленного текста
2. Если информации в тексте нет - пиши "В тексте не указано" или пропусти карточку
3. НЕ добавляй информацию из своих общих знаний
4. Цитируй или перефразируй ТОЛЬКО то, что есть в тексте
5. Если в тексте есть формулы, определения, примеры - используй именно их

Сгенерируй 15 карточек в формате JSON. Структура КАЖДОЙ карточки:
{
  "type": "тип карточки",
  "q": "ОСМЫСЛЕННЫЙ вопрос по содержанию текста",
  "a": "Ответ, основанный СТРОГО на информации из текста (переформулированный, но точный)",
  "hint": "подсказка из текста или указание на раздел",
  "difficulty": число от 1 до 3,
  "related_topics": ["тема из текста 1", "тема из текста 2"],
  "memory_hook": "ассоциация на основе примеров из текста",
  "common_mistakes": "что можно перепутать согласно тексту",
  "text_reference": "краткая ссылка на место в тексте, откуда взята информация"
}

Распределение по типам (с примерами из текста о классификации):
1. "definition" (3 карты) - определения ИЗ ТЕКСТА, difficulty: 1
   Пример: "Как в тексте определяется доля правильных ответов (accuracy)?"
   Ответ должен содержать формулу/определение из текста
   
2. "concept" (4 карты) - понимание концепций ИЗ ТЕКСТА, difficulty: 2
   Пример: "Почему согласно тексту функционал (1.1) нельзя минимизировать градиентными методами?"
   Ответ: то, что написано в тексте об этом
   
3. "application" (3 карты) - применение того, что ОПИСАНО В ТЕКСТЕ, difficulty: 2
   Пример: "Какие примеры функций потерь приводятся в тексте?"
   Ответ: только те примеры, что есть в тексте
   
4. "comparison" (3 карты) - сравнения, УПОМЯНУТЫЕ В ТЕКСТЕ, difficulty: 3
   Пример: "Как согласно тексту связаны точность и полнота?"
   Ответ: только то, что сказано в тексте
   
5. "problem" (2 карты) - задачи/примеры ИЗ ТЕКСТА, difficulty: 3
   Пример: "Решите пример из текста: [если есть конкретный пример]"

ПРОВЕРКА: Перед созданием каждой карточки убедись, что:
- Вопрос касается информации, которая ЕСТЬ в тексте
- Ответ можно найти или вывести из текста
- Ты не добавляешь свои знания о теме

Верни ТОЛЬКО валидный JSON массив."""

        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Ты создаешь флеш-карты СТРОГО по содержанию предоставленного текста. НЕ используй свои общие знания о теме. Если информации нет в тексте - не создавай карточку. Отвечай только валидным JSON."},
                {"role": "user", "content": f"{prompt}\n\nТекст для создания карточек:\n{text}"}
            ],
            temperature=0.3,  # Снизил температуру для более точного следования тексту
            max_tokens=3000
        )
        
        content = response.choices[0].message.content.strip()
        
        # Извлечение JSON
        json_match = re.search(r'\[.*\]', content, re.DOTALL)
        if json_match:
            json_str = json_match.group(0)
        else:
            json_str = content
        
        flashcards = json.loads(json_str)
        
        validated_cards = []
        for card in flashcards:
            if 'q' in card and 'a' in card:
                if 'text_reference' not in card:
                    card['text_reference'] = "См. текст выше"
                
                card['next_review'] = calculate_next_review(card.get('difficulty', 2))
                card['ease_factor'] = 2.5
                
                validated_cards.append(card)
        
        return validated_cards if validated_cards else generate_fallback_flashcards(text)
        
    except Exception as e:
        logger.error(f"Error generating advanced flashcards: {str(e)}")
        return generate_fallback_flashcards(text)

def generate_fallback_flashcards(text: str) -> List[Dict]:
    """Генерация флеш-карт без GPT"""
    flashcards = []
    
    try:
        definition_patterns = [
            r'([А-Я][а-я]+(?:\s+[а-я]+){0,3})\s+(?:—|–|-|это|является)\s*([^.]+)\.',
            r'([А-Я][а-я]+(?:\s+[а-я]+){0,3})\s+называется\s+([^.]+)\.',
            r'Под\s+([а-я]+(?:\s+[а-я]+){0,3})\s+понимают\s+([^.]+)\.'
        ]
        
        for pattern in definition_patterns:
            matches = re.findall(pattern, text, re.MULTILINE)
            for term, definition in matches[:3]:
                if len(term) > 3 and len(definition) > 10:
                    flashcards.append({
                        "type": "definition",
                        "q": f"Что такое {term.strip()}?",
                        "a": f"{term} — это {definition.strip()}",
                        "hint": f"Определение дано в тексте",
                        "difficulty": 1,
                        "related_topics": [term.strip()],
                        "memory_hook": f"Запомни: {term} = {definition.split()[0]}...",
                        "common_mistakes": "Не путать с другими терминами",
                        "text_reference": "Определение из текста",
                        "next_review": calculate_next_review(1),
                        "ease_factor": 2.5
                    })
        
        formula_matches = re.findall(r'([A-Za-z]+\([^)]+\))\s*=\s*([^.]+)', text)
        for formula_name, formula_body in formula_matches[:2]:
            flashcards.append({
                "type": "concept",
                "q": f"Как вычисляется {formula_name}?",
                "a": f"{formula_name} = {formula_body.strip()}",
                "hint": "Формула приведена в тексте",
                "difficulty": 2,
                "related_topics": ["формулы", "вычисления"],
                "memory_hook": f"Формула: {formula_name}",
                "common_mistakes": "Проверьте все переменные в формуле",
                "text_reference": "Формула из текста",
                "next_review": calculate_next_review(2),
                "ease_factor": 2.5
            })
        
        example_sentences = re.findall(r'(?:Например|К примеру|Пример)[,:]?\s*([^.]+)\.', text, re.IGNORECASE)
        for i, example in enumerate(example_sentences[:2]):
            flashcards.append({
                "type": "application",
                "q": f"Приведите пример из текста #{i+1}",
                "a": example.strip(),
                "hint": "Пример явно указан в тексте",
                "difficulty": 2,
                "related_topics": ["примеры", "применение"],
                "memory_hook": "Конкретный пример из текста",
                "common_mistakes": "Убедитесь, что пример полный",
                "text_reference": "Пример из текста",
                "next_review": calculate_next_review(2),
                "ease_factor": 2.5
            })
        
        key_statements = re.findall(r'(?:Важно|Следует|Необходимо|Нужно)\s+([^.]+)\.', text, re.IGNORECASE)
        for statement in key_statements[:2]:
            flashcards.append({
                "type": "concept",
                "q": f"Что важно помнить согласно тексту?",
                "a": statement.strip(),
                "hint": "Обратите внимание на ключевые утверждения",
                "difficulty": 2,
                "related_topics": ["ключевые моменты"],
                "memory_hook": "Важное утверждение",
                "common_mistakes": "Не упустить контекст",
                "text_reference": "Важное замечание из текста",
                "next_review": calculate_next_review(2),
                "ease_factor": 2.5
            })
        
        if len(flashcards) < 5:
            sentences = sent_tokenize(text)
            informative_sentences = [s for s in sentences if len(s) > 50 and not s.endswith('?')]
            
            for i, sent in enumerate(informative_sentences[:5-len(flashcards)]):
                flashcards.append({
                    "type": "concept",
                    "q": f"Объясните утверждение из текста: {sent[:50]}...?",
                    "a": sent.strip(),
                    "hint": "Ответ содержится в самом вопросе",
                    "difficulty": 1,
                    "related_topics": ["основные положения"],
                    "memory_hook": "Ключевое утверждение",
                    "common_mistakes": "Прочитайте внимательно",
                    "text_reference": "Утверждение из текста",
                    "next_review": calculate_next_review(1),
                    "ease_factor": 2.5
                })
        
        return flashcards
        
    except Exception as e:
        logger.error(f"Error in fallback flashcard generation: {str(e)}")
        return [{
            "type": "definition",
            "q": "О чем этот текст?",
            "a": "Текст содержит учебный материал для изучения. Прочитайте внимательно для понимания основных концепций.",
            "hint": "Подумайте о главной теме",
            "difficulty": 1,
            "related_topics": ["основная тема"],
            "memory_hook": "Главная идея текста",
            "common_mistakes": "Не путать детали с главной идеей",
            "text_reference": "Весь текст",
            "next_review": calculate_next_review(1),
            "ease_factor": 2.5
        }]

def calculate_next_review(difficulty: int) -> str:
    """Считаем день следующей проверки"""
    days_map = {1: 1, 2: 3, 3: 7}
    days = days_map.get(difficulty, 3)
    next_date = datetime.now() + timedelta(days=days)
    return next_date.strftime("%Y-%m-%d")

def generate_mind_map(text: str, topics: List[Dict]) -> Dict:
    """Генерация Mind Map"""
    try:
        if topics and 'title' in topics[0]:
            central_topic = topics[0]['title']
        else:
            central_topic = "Основная тема"
        
        branches = []
        colors = ["#FF6B6B", "#4ECDC4", "#45B7D1", "#96CEB4", "#FECA57", "#48DBFB"]
        
        for i, topic in enumerate(topics[:6]):
            branch = {
                "name": topic['title'][:40],
                "importance": 0.9 - (i * 0.1),
                "color": colors[i % len(colors)],
                "children": []
            }
            
            for subtopic in topic.get('subtopics', [])[:3]:
                branch['children'].append({
                    "name": subtopic[:30],
                    "importance": 0.5,
                    "color": branch['color']
                })
            
            if not branch['children'] and topic.get('key_concepts'):
                for concept in topic['key_concepts'][:3]:
                    branch['children'].append({
                        "name": concept[:30],
                        "importance": 0.4,
                        "color": branch['color']
                    })
            
            branches.append(branch)
        
        return {
            "central_topic": central_topic,
            "branches": branches
        }
        
    except Exception as e:
        logger.error(f"Error generating mind map: {str(e)}")
        return {
            "central_topic": "Тема",
            "branches": []
        }

def generate_study_plan(topics: List[Dict], flashcards: List[Dict], text_length: int = 0) -> Dict:
    """Генерируем улучшенный персонализированный план обучения с научным подходом"""
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
        
        return {
            "sessions": sessions,
            "milestones": milestones,
            "review_schedule": review_system["intervals"],
            "total_hours": schedule_config["total_hours"],
            "completion_date": schedule_config["completion_date"],
            "difficulty_level": material_analysis["overall_difficulty"],
            "material_analysis": material_analysis,
            "adaptive_features": {
                "difficulty_adjustment": True,
                "personalized_pace": True,
                "progress_tracking": True
            },
            "success_metrics": {
                "target_retention": 85,
                "target_completion": 90,
                "target_satisfaction": 8
            }
        }
        
    except Exception as e:
        logger.error(f"Error generating enhanced study plan: {str(e)}")
        return _generate_fallback_study_plan()

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
    
    # Оценка времени изучения
    base_time_per_topic = {1: 15, 2: 25, 3: 40}  # минуты
    time_per_card = 2  # минуты на флеш-карту
    reading_time = (text_length / 5) / 200  # 200 слов в минуту
    
    topic_time = len(topics) * base_time_per_topic.get(int(overall_difficulty), 25)
    card_time = len(flashcards) * time_per_card
    total_minutes = (reading_time + topic_time + card_time) * 1.3  # +30% на повторения
    
    return {
        "complexity_distribution": complexity_distribution,
        "topic_depths": topic_depths,
        "avg_topic_depth": sum(topic_depths) / len(topic_depths) if topic_depths else 1,
        "avg_card_difficulty": avg_card_difficulty,
        "volume_factor": volume_factor,
        "overall_difficulty": overall_difficulty,
        "estimated_study_time": {
            "total_minutes": int(total_minutes),
            "total_hours": round(total_minutes / 60, 1),
            "reading_time": int(reading_time),
            "study_time": int(topic_time + card_time),
            "review_time": int(total_minutes * 0.3)
        }
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

def _create_learning_sequence(topics: List[Dict], analysis: Dict) -> Dict:
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
    cards_per_session = max(3, len(flashcards) // total_sessions) if flashcards else 0
    
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
        
        # Расчет даты сессии
        days_from_start = (session_num - 1) * (7 / config["sessions_per_week"])
        session_date = datetime.now() + timedelta(days=days_from_start)
        
        session = {
            "day": session_num,
            "session_number": session_num,
            "date": session_date.strftime("%d.%m.%Y"),
            "day_of_week": ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"][session_date.weekday()],
            "phase": phase,
            "phase_name": phase_name,
            "duration_minutes": session_duration,
            "main_topic": current_topic,
            "topics": [current_topic["title"]],
            "flashcards_count": end_card - start_card,
            "flashcard_ids": list(range(start_card, end_card)),
            "focus": _get_session_focus(phase),
            "exercises": _generate_session_exercises(current_topic, phase),
            "learning_objectives": _generate_session_objectives(current_topic, phase),
            "success_criteria": _generate_success_criteria(current_topic, end_card - start_card),
            "estimated_difficulty": current_topic.get("complexity", "basic"),
            "activities": _generate_session_activities(current_topic, phase, session_duration)
        }
        
        sessions.append(session)
    
    return sessions

def _get_session_focus(phase: str) -> str:
    """Определение фокуса сессии"""
    focus_map = {
        "foundation": "Понимание базовых концепций и терминологии",
        "development": "Углубление знаний и установление связей",
        "mastery": "Закрепление и практическое применение"
    }
    return focus_map.get(phase, "Изучение материала")

def _generate_session_exercises(topic: Dict, phase: str) -> List[str]:
    """Генерация упражнений для сессии"""
    
    topic_title = topic.get("title", "изученную тему")
    
    if phase == "foundation":
        return [
            f"Объясните {topic_title} простыми словами",
            f"Приведите 2-3 примера применения '{topic_title}'",
            f"Создайте простую схему для '{topic_title}'"
        ]
    elif phase == "development":
        return [
            f"Сравните {topic_title} с ранее изученными темами",
            f"Решите практическую задачу по теме '{topic_title}'",
            f"Создайте mind map для '{topic_title}'"
        ]
    else:  # mastery
        return [
            f"Критически оцените применимость '{topic_title}'",
            f"Создайте собственный пример для '{topic_title}'",
            f"Объясните '{topic_title}' новичку"
        ]

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
        f"Правильно ответить на {max(1, int(cards_count * 0.8))} из {cards_count} флеш-карт" if cards_count > 0 else "Изучить основной материал",
        "Объяснить основные концепции своими словами",
        "Привести минимум 1 практический пример применения",
        "Оценить свое понимание темы на 7+ баллов из 10"
    ]

def _generate_session_activities(topic: Dict, phase: str, duration: int) -> List[Dict]:
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
    
    # Основное изучение (50% времени)
    main_study_time = int(duration * 0.5)
    activities.append({
        "type": "study",
        "name": "Изучение основного материала",
        "duration": main_study_time,
        "description": f"Глубокое изучение темы '{topic_title}' с фокусом на ключевые концепции",
        "icon": "📚"
    })
    
    # Практическое применение (25% времени)
    practice_time = int(duration * 0.25)
    activities.append({
        "type": "practice",
        "name": "Практическое применение",
        "duration": practice_time,
        "description": "Применение изученных концепций на практике",
        "icon": "⚡"
    })
    
    # Рефлексия (20% времени)
    reflection_time = int(duration * 0.2)
    activities.append({
        "type": "reflection",
        "name": "Рефлексия и планирование",
        "duration": reflection_time,
        "description": "Оценка понимания и планирование следующих шагов",
        "icon": "🤔"
    })
    
    return activities

def _create_spaced_repetition_schedule(sessions: List[Dict], analysis: Dict) -> Dict:
    """Создание системы интервальных повторений"""
    
    # Интервалы повторений по Эббингаузу (дни)
    difficulty = analysis["overall_difficulty"]
    if difficulty > 2.5:
        intervals = [1, 2, 5, 10, 21, 45]  # чаще для сложного материала
    elif difficulty < 1.5:
        intervals = [2, 5, 10, 21, 45, 90]  # реже для легкого материала
    else:
        intervals = [1, 3, 7, 14, 30, 60]  # стандартные интервалы
    
    return {
        "intervals": intervals,
        "strategy": "spaced_repetition",
        "total_reviews": len(sessions) * len(intervals)
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
        "progress_percent": 25
    })
    
    # Milestone 2: Развитие навыков (50% прогресса)
    development_session = max(2, total_sessions // 2)
    milestones.append({
        "session": development_session,
        "title": "Развитие навыков",
        "description": "Применение знаний и установление связей",
        "progress_percent": 50
    })
    
    # Milestone 3: Мастерство (75% прогресса)
    mastery_session = max(3, 3 * total_sessions // 4)
    milestones.append({
        "session": mastery_session,
        "title": "Достижение мастерства",
        "description": "Экспертное понимание и критическое мышление",
        "progress_percent": 75
    })
    
    # Final Milestone: Завершение курса (100% прогресса)
    milestones.append({
        "session": total_sessions,
        "title": "Завершение изучения",
        "description": "Полное освоение материала",
        "progress_percent": 100
    })
    
    return milestones

def _generate_fallback_study_plan() -> Dict:
    """Базовый план на случай ошибки"""
    
    return {
        "sessions": [{
            "day": 1,
            "session_number": 1,
            "date": datetime.now().strftime("%d.%m.%Y"),
            "duration_minutes": 45,
            "topics": ["Изучение материала"],
            "focus": "Изучение основного материала",
            "exercises": ["Прочитать материал", "Сделать заметки", "Повторить ключевые моменты"],
            "main_topic": {"title": "Изучение материала", "complexity": "basic"},
            "phase_name": "Основы",
            "flashcards_count": 0,
            "activities": []
        }],
        "milestones": [{"title": "Изучить материал", "progress_percent": 100, "session": 1, "description": "Основное изучение"}],
        "review_schedule": [1, 3, 7],
        "total_hours": 0.75,
        "completion_date": (datetime.now() + timedelta(days=7)).strftime("%d.%m.%Y"),
        "material_analysis": {
            "overall_difficulty": 1.5,
            "estimated_study_time": {"total_hours": 0.75, "study_time": 30, "review_time": 15, "reading_time": 10}
        },
        "adaptive_features": {"difficulty_adjustment": False, "personalized_pace": False, "progress_tracking": False},
        "success_metrics": {"target_retention": 80, "target_completion": 85, "target_satisfaction": 7}
    }

def assess_content_quality(text: str, topics: List[Dict], summary: str, flashcards: List[Dict]) -> Dict:
    """Оцениваем качество создаваемого материала"""
    try:
        # Оценка глубины - на основе иерархии тем и качества
        depth_score = 0.0
        
        # Провяем, есть ли у тем осмысленные названия (а не просто фрагменты текста)
        meaningful_titles = sum(1 for t in topics if len(t.get('title', '')) < 100 and not t['title'].endswith('...'))
        depth_score += min(0.5, meaningful_titles / len(topics) * 0.5) if topics else 0
        
        # Проверяем наличие подтем и примеров
        topics_with_subtopics = sum(1 for t in topics if len(t.get('subtopics', [])) > 0)
        topics_with_examples = sum(1 for t in topics if len(t.get('examples', [])) > 0)
        depth_score += min(0.25, topics_with_subtopics / len(topics) * 0.25) if topics else 0
        depth_score += min(0.25, topics_with_examples / len(topics) * 0.25) if topics else 0
        
        # Оценка охвата - основана на извлеченных ключевых понятиях
        total_concepts = sum(len(t.get('key_concepts', [])) for t in topics)
        coverage_score = min(1.0, total_concepts / 30)
        
        # Оценка практичности - на основе примеров и приложений
        total_examples = sum(len(t.get('examples', [])) for t in topics)
        practical_flashcards = sum(1 for f in flashcards if f.get('type') in ['application', 'problem'])
        practical_score = min(1.0, (total_examples / 10 * 0.5) + (practical_flashcards / 5 * 0.5))
        
        # Оценка ясности - на основе структуры резюме и качества карточек
        clarity_score = 0.5  # Base score
        if len(summary) > 100 and '##' in summary:
            clarity_score += 0.3
        if flashcards and all('hint' in f and 'memory_hook' in f for f in flashcards[:5]):
            clarity_score += 0.2
        
        suggestions = []
        if depth_score < 0.7:
            suggestions.append("Улучшить извлечение тем - сейчас используются фрагменты текста вместо осмысленных названий")
        if coverage_score < 0.7:
            suggestions.append("Расширить охват ключевых концепций")
        if practical_score < 0.7:
            suggestions.append("Добавить больше практических примеров")
        if clarity_score < 0.7:
            suggestions.append("Улучшить структуру и ясность изложения")
        
        return {
            "depth_score": round(depth_score, 2),
            "coverage_score": round(coverage_score, 2),
            "practical_score": round(practical_score, 2),
            "clarity_score": round(clarity_score, 2),
            "overall_score": round((depth_score + coverage_score + practical_score + clarity_score) / 4, 2),
            "suggestions": suggestions
        }
        
    except Exception as e:
        logger.error(f"Error assessing content quality: {str(e)}")
        return {
            "depth_score": 0.5,
            "coverage_score": 0.5,
            "practical_score": 0.5,
            "clarity_score": 0.5,
            "overall_score": 0.5,
            "suggestions": ["Не удалось оценить качество"]
        }

def process_file(filepath: str, filename: str, page_range: str = None) -> Dict[str, Any]:
    """Обработка файла с возможностью выбора страниц"""
    try:
        logger.info(f"Starting processing for: {filename}")
        if page_range:
            logger.info(f"Page range specified: {page_range}")
        
        # Извлекаем текст в зависимости от типа файла
        file_ext = Path(filename).suffix.lower()
        
        if file_ext == '.pdf':
            text = extract_text_from_pdf_with_pages(filepath, page_range)
            video_data = None
        elif file_ext in ['.mp4', '.mov', '.mkv']:
            video_data = transcribe_video_with_timestamps(filepath)
            text = video_data['full_text']
        else:
            raise ValueError(f"Unsupported file type: {file_ext}")
        
        if not text or len(text.strip()) < 100:
            raise ValueError("Extracted text is too short or empty")
        
        logger.info(f"Extracted {len(text)} characters of text")
        
        try:
            topics_data = extract_topics_with_gpt(text)
            logger.info("Successfully extracted topics with GPT")
        except Exception as e:
            logger.warning(f"Failed to extract topics with GPT: {str(e)}, falling back to local method")
            topics_data = extract_topics_fallback(text)
        
        summary = generate_summary(text)
        flashcards = generate_flashcards(text)
        mind_map = generate_mind_map(text, topics_data.get('main_topics', []))
        study_plan = generate_study_plan(topics_data.get('main_topics', []), flashcards, len(text))
        quality = assess_content_quality(text, topics_data.get('main_topics', []), summary, flashcards)
        
        # Собираем результат
        result = {
            "topics_data": topics_data,
            "summary": summary,
            "flashcards": flashcards,
            "mind_map": mind_map,
            "study_plan": study_plan,
            "quality_assessment": quality,
            "metadata": {
                "filename": filename,
                "file_type": file_ext,
                "text_length": len(text),
                "processing_date": datetime.now().isoformat()
            }
        }
        
        if video_data:
            result["video_segments"] = video_data.get('segments', [])
            result["key_moments"] = video_data.get('key_moments', [])
        
        logger.info(f"Advanced processing complete. Quality score: {quality['overall_score']}")
        
        return result
        
    except Exception as e:
        logger.error(f"Error in advanced processing: {str(e)}")
        raise

# Для теста
if __name__ == "__main__":
    sample_text = """
    Линейные модели классификации

    Линейная классификация является фундаментальным подходом в машинном обучении.
    Основная идея заключается в разделении пространства признаков гиперплоскостью.
    
    Метрики качества классификации включают:
    - Точность (precision) - доля правильных положительных предсказаний
    - Полнота (recall) - доля найденных положительных примеров
    - F-мера - гармоническое среднее точности и полноты
    
    Функция потерь используется для обучения модели. Например, логистическая
    функция потерь позволяет получить вероятностные предсказания.
    
    Применение: классификация текстов, распознавание образов, медицинская диагностика.
    """
    
    print("Testing advanced topic extraction...")
    topics_data = extract_topics_fallback(sample_text)
    print(f"Found {len(topics_data['main_topics'])} main topics")
    if topics_data['main_topics']:
        print(f"First topic: {topics_data['main_topics'][0]['title']}")
        print(f"Summary: {topics_data['main_topics'][0]['summary'][:100]}...")
    
    if os.environ.get('OPENAI_API_KEY'):
        print("\nTesting with GPT...")
        topics_gpt = extract_topics_with_gpt(sample_text)
        if topics_gpt.get('main_topics'):
            print(f"GPT topic: {topics_gpt['main_topics'][0]['title']}")
    else:
        print("\nSkipping GPT tests - OPENAI_API_KEY not set")