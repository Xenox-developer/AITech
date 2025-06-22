import os
import json
import logging
import re
from typing import List, Dict, Tuple, Any
import numpy as np
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime, timedelta

# Load environment variables
load_dotenv()

# PDF processing
from pdfminer.high_level import extract_text

# Video/Audio processing
import whisperx
import torch

# NLP and embeddings
from sentence_transformers import SentenceTransformer
from sklearn.cluster import HDBSCAN
from sklearn.preprocessing import normalize
import nltk
from nltk.tokenize import sent_tokenize, word_tokenize
from collections import Counter

# OpenAI for summarization and flashcards
from openai import OpenAI

# Download NLTK data if needed
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt')

# Configure logging
logger = logging.getLogger(__name__)

# Initialize models
device = "cuda" if torch.cuda.is_available() else "cpu"
compute_type = "float16" if device == "cuda" else "int8"

# Global variables for models
sentence_model = None
whisper_model = None
openai_client = None

def load_models():
    """Load AI models"""
    global sentence_model, whisper_model, openai_client
    
    logger.info("Loading models...")
    
    # Sentence transformer for embeddings
    sentence_model = SentenceTransformer("intfloat/e5-large-v2", device=device)
    
    # Whisper for audio transcription
    try:
        whisper_model = whisperx.load_model("large-v3", device, compute_type=compute_type)
    except Exception as e:
        logger.warning(f"Whisper model not loaded: {str(e)}")
    
    # OpenAI client
    api_key = os.environ.get('OPENAI_API_KEY')
    if not api_key:
        raise ValueError("OPENAI_API_KEY environment variable not set")
    openai_client = OpenAI(api_key=api_key)
    
    logger.info("Models loaded successfully")

# Load models on module import
try:
    load_models()
except Exception as e:
    logger.warning(f"Models not loaded on import: {str(e)}")

def extract_text_from_pdf(filepath: str) -> str:
    """Extract text from PDF file"""
    try:
        text = extract_text(filepath)
        return text.strip()
    except Exception as e:
        logger.error(f"Error extracting text from PDF: {str(e)}")
        raise

def transcribe_video_with_timestamps(filepath: str) -> Dict[str, Any]:
    """Transcribe video/audio with timestamps using Whisper"""
    try:
        logger.info(f"Transcribing video with timestamps: {filepath}")
        
        # Load audio
        audio = whisperx.load_audio(filepath)
        
        # Transcribe with timestamps
        result = whisper_model.transcribe(audio, batch_size=16)
        
        # Process segments
        segments = []
        key_moments = []
        full_text = ""
        
        for i, segment in enumerate(result["segments"]):
            text = segment["text"].strip()
            start = segment["start"]
            end = segment["end"]
            
            full_text += text + " "
            
            # Analyze segment importance (based on length and keywords)
            importance = min(1.0, len(text.split()) / 50)
            
            segments.append({
                "start": start,
                "end": end,
                "text": text,
                "importance": importance
            })
            
            # Identify key moments (longer segments with high importance)
            if importance > 0.7 and len(text.split()) > 20:
                key_moments.append({
                    "time": start,
                    "description": text[:100] + "..." if len(text) > 100 else text
                })
        
        return {
            "full_text": full_text.strip(),
            "segments": segments,
            "key_moments": key_moments[:10]  # Top 10 key moments
        }
        
    except Exception as e:
        logger.error(f"Error transcribing video: {str(e)}")
        # Fallback to simple transcription
        return {"full_text": transcribe_video_simple(filepath), "segments": [], "key_moments": []}

def transcribe_video_simple(filepath: str) -> str:
    """Simple video transcription without timestamps"""
    try:
        audio = whisperx.load_audio(filepath)
        result = whisper_model.transcribe(audio, batch_size=16)
        text = " ".join([segment["text"] for segment in result["segments"]])
        return text.strip()
    except Exception as e:
        logger.error(f"Error in simple transcription: {str(e)}")
        raise

def extract_topics_with_gpt(text: str) -> Dict[str, Any]:
    """Extract topics using GPT-4 for better understanding"""
    try:
        if not openai_client:
            load_models()
        
        # Limit text for API
        max_chars = 15000
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
    """Fallback method for topic extraction without GPT"""
    try:
        # Split into paragraphs instead of sentences for better context
        paragraphs = [p.strip() for p in text.split('\n\n') if len(p.strip()) > 50]
        
        if len(paragraphs) < 3:
            # If not enough paragraphs, split by sentences
            sentences = sent_tokenize(text)
            # Group sentences into pseudo-paragraphs
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
        
        # Generate embeddings for paragraphs
        embeddings = sentence_model.encode(paragraphs, convert_to_tensor=False)
        embeddings = normalize(embeddings)
        
        # Hierarchical clustering
        min_cluster_size = max(2, min(5, len(paragraphs) // 5))
        clusterer = HDBSCAN(
            min_cluster_size=min_cluster_size,
            min_samples=1,
            metric='euclidean',
            cluster_selection_method='eom'
        )
        
        cluster_labels = clusterer.fit_predict(embeddings)
        
        # Extract topics from clusters
        main_topics = []
        unique_labels = set(cluster_labels)
        
        for label in unique_labels:
            if label == -1:  # Skip noise
                continue
            
            # Get paragraphs in this cluster
            cluster_paragraphs = [paragraphs[i] for i, l in enumerate(cluster_labels) if l == label]
            
            if not cluster_paragraphs:
                continue
            
            # Extract a meaningful title (not just first sentence)
            title = extract_topic_title(cluster_paragraphs)
            
            # Create a proper summary
            summary = create_topic_summary(cluster_paragraphs)
            
            # Extract key concepts
            key_concepts = extract_key_concepts(" ".join(cluster_paragraphs))
            
            # Determine complexity
            complexity = determine_complexity(" ".join(cluster_paragraphs))
            
            # Find examples
            examples = extract_meaningful_examples(cluster_paragraphs)
            
            # Create topic
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
        
        # Sort by importance
        main_topics.sort(key=lambda x: len(x["summary"]), reverse=True)
        
        # Extract relationships
        relationships = extract_smart_relationships(main_topics, text)
        
        # Extract learning objectives
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
    """Extract meaningful topic title from paragraphs"""
    # Look for headers or strong statements
    for para in paragraphs:
        # Check for section headers (usually short and at the beginning)
        lines = para.split('\n')
        for line in lines:
            if len(line) < 100 and (
                line.strip().startswith('§') or 
                line.strip()[0].isdigit() or
                line.isupper() or
                ':' in line[:50]
            ):
                # Clean up the title
                title = line.strip()
                title = re.sub(r'^[§\d\s.]+', '', title)  # Remove section numbers
                title = title.strip(':').strip()
                if len(title) > 10:
                    return title[:80]
    
    # If no header found, extract key phrase
    all_text = " ".join(paragraphs[:2])  # Use first two paragraphs
    
    # Try to find the main concept
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
    
    # Last resort - use most important noun phrases
    words = word_tokenize(all_text.lower())
    # Find noun phrases (simplified)
    important_words = [w for w in words if len(w) > 4 and w.isalpha()]
    word_freq = Counter(important_words)
    
    if word_freq:
        top_words = [word for word, _ in word_freq.most_common(3)]
        return " ".join(top_words).capitalize()
    
    return "Тема раздела"

def create_topic_summary(paragraphs: List[str]) -> str:
    """Create meaningful summary from paragraphs"""
    # Don't just concatenate - extract key ideas
    key_sentences = []
    
    for para in paragraphs:
        sentences = sent_tokenize(para)
        for sent in sentences:
            # Look for definitional or explanatory sentences
            if any(marker in sent.lower() for marker in [
                'это', 'является', 'представляет', 'означает',
                'позволяет', 'используется', 'применяется',
                'можно', 'следует', 'необходимо'
            ]):
                key_sentences.append(sent)
                if len(key_sentences) >= 2:
                    break
    
    if not key_sentences:
        # Take first meaningful sentence
        for para in paragraphs:
            sentences = sent_tokenize(para)
            for sent in sentences:
                if len(sent) > 30:
                    key_sentences.append(sent)
                    break
            if key_sentences:
                break
    
    # Combine and clean
    summary = " ".join(key_sentences[:2])
    # Remove formulas and special characters
    summary = re.sub(r'\$[^$]+\$', '[формула]', summary)
    summary = re.sub(r'[^\w\s\[\].,!?;:()-]', '', summary)
    
    return summary[:300]

def extract_subtopics_smart(paragraphs: List[str]) -> List[str]:
    """Extract meaningful subtopics"""
    subtopics = []
    
    for para in paragraphs:
        # Look for enumeration or listing
        if re.search(r'(?:включает|содержит|состоит из|различают|выделяют):', para, re.IGNORECASE):
            # Extract items after colon
            parts = para.split(':')
            if len(parts) > 1:
                items = re.split(r'[;,]', parts[1])
                for item in items[:4]:
                    item = item.strip()
                    if 10 < len(item) < 100:
                        subtopics.append(item)
        
        # Look for numbered items
        numbered = re.findall(r'\d+\)\s*([^.]+)\.', para)
        subtopics.extend([item.strip() for item in numbered[:4] if 10 < len(item) < 100])
    
    # Remove duplicates while preserving order
    seen = set()
    unique_subtopics = []
    for topic in subtopics:
        if topic.lower() not in seen:
            seen.add(topic.lower())
            unique_subtopics.append(topic)
    
    return unique_subtopics[:5]

def extract_meaningful_examples(paragraphs: List[str]) -> List[str]:
    """Extract actual examples, not just random sentences"""
    examples = []
    
    for para in paragraphs:
        sentences = sent_tokenize(para)
        for sent in sentences:
            # Look for example indicators
            if any(indicator in sent.lower() for indicator in [
                'например', 'к примеру', 'в частности', 'рассмотрим',
                'пусть', 'допустим', 'представим', 'возьмем'
            ]):
                # Clean up the example
                example = sent.strip()
                # Remove the indicator for cleaner text
                for indicator in ['Например,', 'К примеру,', 'В частности,']:
                    example = example.replace(indicator, '').strip()
                
                if len(example) > 20:
                    examples.append(example)
            
            # Look for concrete values or scenarios
            elif re.search(r'\d+\s*(?:%|процент|объект|элемент|класс)', sent) and len(sent) < 200:
                examples.append(sent.strip())
    
    return examples[:5]

def extract_smart_relationships(topics: List[Dict], text: str) -> List[Dict]:
    """Extract meaningful relationships between topics"""
    relationships = []
    
    # Create a mapping of topic keywords
    topic_keywords = {}
    for i, topic in enumerate(topics):
        keywords = set()
        # Add words from title
        keywords.update(word_tokenize(topic['title'].lower()))
        # Add key concepts
        for concept in topic['key_concepts']:
            keywords.update(word_tokenize(concept.lower()))
        topic_keywords[i] = keywords
    
    # Look for relationships in text
    relationship_patterns = {
        'causes': ['приводит к', 'вызывает', 'влияет на', 'определяет'],
        'requires': ['требует', 'необходим', 'нужен для', 'основан на'],
        'part_of': ['часть', 'включает', 'состоит из', 'содержит'],
        'contrast': ['в отличие от', 'напротив', 'однако', 'но'],
        'similar': ['похож', 'аналогично', 'также как', 'подобно']
    }
    
    # Analyze text for relationships
    sentences = sent_tokenize(text.lower())
    
    for i, topic1 in enumerate(topics):
        for j, topic2 in enumerate(topics):
            if i >= j:
                continue
            
            # Check if topics are mentioned together
            for sent in sentences:
                t1_found = any(kw in sent for kw in topic_keywords[i])
                t2_found = any(kw in sent for kw in topic_keywords[j])
                
                if t1_found and t2_found:
                    # Check for relationship type
                    for rel_type, patterns in relationship_patterns.items():
                        if any(pattern in sent for pattern in patterns):
                            relationships.append({
                                "from": topic1['title'],
                                "to": topic2['title'],
                                "type": rel_type,
                                "description": f"{topic1['title']} {rel_type} {topic2['title']}"
                            })
                            break
                    
                    # Only one relationship per pair
                    break
    
    return relationships[:10]

def extract_learning_objectives(topics: List[Dict]) -> List[str]:
    """Extract learning objectives from topics"""
    objectives = []
    
    # Common objective patterns
    objective_verbs = [
        "Понимать", "Объяснять", "Применять", "Анализировать",
        "Различать", "Использовать", "Вычислять", "Определять"
    ]
    
    for topic in topics[:5]:  # Top 5 topics
        # Create objective based on topic
        verb = objective_verbs[len(objectives) % len(objective_verbs)]
        
        if topic['complexity'] == 'basic':
            objective = f"{verb} основные понятия {topic['title'].lower()}"
        elif topic['complexity'] == 'intermediate':
            objective = f"{verb} и применять {topic['title'].lower()}"
        else:
            objective = f"{verb} и решать сложные задачи по теме {topic['title'].lower()}"
        
        objectives.append(objective)
    
    # Add general objectives
    objectives.extend([
        "Решать практические задачи по изученным темам",
        "Связывать теоретические концепции с практическим применением"
    ])
    
    return objectives[:7]

def extract_key_concepts(text: str) -> List[str]:
    """Extract key concepts - improved version"""
    concepts = []
    
    # Look for defined terms
    defined_terms = re.findall(
        r'(?:([А-Я][а-я]+(?:\s+[а-я]+){0,2})\s*(?:—|это|называется|является))',
        text
    )
    concepts.extend([term.strip() for term in defined_terms if len(term) > 5])
    
    # Look for terms in parentheses (often English terms or abbreviations)
    parenthetical = re.findall(r'\(([A-Za-z]+(?:\s+[A-Za-z]+){0,2})\)', text)
    concepts.extend([term for term in parenthetical if len(term) > 3])
    
    # Look for emphasized terms
    emphasized = re.findall(r'«([^»]+)»', text)
    concepts.extend([term for term in emphasized if 5 < len(term) < 50])
    
    # Frequency-based extraction with filtering
    words = word_tokenize(text.lower())
    # Filter for meaningful words
    meaningful_words = [
        w for w in words 
        if len(w) > 4 and w.isalpha() and
        not w in ['можно', 'нужно', 'будет', 'может', 'этого', 'этому']
    ]
    
    word_freq = Counter(meaningful_words)
    
    # Add frequent terms
    for word, freq in word_freq.most_common(20):
        if freq > 3 and word not in [c.lower() for c in concepts]:
            # Check if it's a meaningful concept
            if any(pattern in text.lower() for pattern in [
                f'{word} это',
                f'{word} является',
                f'{word} представляет',
                f'используя {word}',
                f'методом {word}'
            ]):
                concepts.append(word.capitalize())
    
    # Remove duplicates while preserving order
    seen = set()
    unique_concepts = []
    for concept in concepts:
        if concept.lower() not in seen:
            seen.add(concept.lower())
            unique_concepts.append(concept)
    
    return unique_concepts[:15]

def determine_complexity(text: str) -> str:
    """Determine text complexity level"""
    words = word_tokenize(text.lower())
    
    # Indicators of complexity
    basic_words = ['основной', 'простой', 'базовый', 'элементарный', 'начальный']
    intermediate_words = ['применение', 'использование', 'алгоритм', 'метод', 'анализ']
    advanced_words = ['оптимизация', 'доказательство', 'теорема', 'сложность', 'производная']
    
    basic_count = sum(1 for w in words if w in basic_words)
    intermediate_count = sum(1 for w in words if w in intermediate_words)
    advanced_count = sum(1 for w in words if w in advanced_words)
    
    # Check for mathematical formulas
    formula_count = len(re.findall(r'[∑∫∂∇∈∀∃]|\$[^$]+\$', text))
    
    # Sentence complexity
    sentences = sent_tokenize(text)
    avg_sentence_length = np.mean([len(word_tokenize(s)) for s in sentences]) if sentences else 0
    
    # Decision logic
    if advanced_count > 2 or formula_count > 5 or avg_sentence_length > 25:
        return "advanced"
    elif intermediate_count > 2 or formula_count > 2 or avg_sentence_length > 20:
        return "intermediate"
    else:
        return "basic"

def generate_summary(text: str) -> str:
    """Generate structured summary with GPT-4"""
    try:
        if not openai_client:
            load_models()
        
        # Limit text for API
        max_chars = 10000
        if len(text) > max_chars:
            text = text[:max_chars] + "..."
        
        prompt = """Создай СТРУКТУРИРОВАННОЕ резюме учебного материала.

Формат ответа:

## 🎯 Главная идея
[1-2 предложения с основной мыслью всего материала. НЕ копируй текст, а объясни своими словами]

## 📊 Ключевые концепции
• **Концепция 1**: краткое объяснение своими словами (почему важно)
• **Концепция 2**: краткое объяснение своими словами (практическое применение)
[3-5 концепций]

## 🔗 Взаимосвязи
• Как концепция X влияет на Y
• Почему Z является следствием X
[2-3 важнейшие связи]

## 💡 Практическая ценность
• Где это применяется в реальной жизни
• Какие проблемы решает
[2-3 примера]

## ⚡ Запомнить в первую очередь
• Факт 1 (одно предложение)
• Факт 2 (одно предложение)
• Факт 3 (одно предложение)

Требования:
- НЕ КОПИРУЙ текст дословно! Переформулируй и объясни своими словами
- Используй эмодзи для визуальной навигации
- Выделяй важное **жирным**
- Максимум 200 слов общий объем
- Фокус на понимании, а не запоминании
- Пиши на русском языке"""
        
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
    """Generate multi-level flashcards with GPT-4"""
    try:
        if not openai_client:
            load_models()
        
        # Limit text for API
        max_chars = 10000
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
        
        # Extract JSON
        json_match = re.search(r'\[.*\]', content, re.DOTALL)
        if json_match:
            json_str = json_match.group(0)
        else:
            json_str = content
        
        # Parse and validate
        flashcards = json.loads(json_str)
        
        # Validate that cards are based on text content
        validated_cards = []
        for card in flashcards:
            # Ensure required fields
            if 'q' in card and 'a' in card:
                # Add text_reference if not present
                if 'text_reference' not in card:
                    card['text_reference'] = "См. текст выше"
                
                # Add spaced repetition data
                card['next_review'] = calculate_next_review(card.get('difficulty', 2))
                card['ease_factor'] = 2.5
                
                validated_cards.append(card)
        
        return validated_cards if validated_cards else generate_fallback_flashcards(text)
        
    except Exception as e:
        logger.error(f"Error generating advanced flashcards: {str(e)}")
        return generate_fallback_flashcards(text)

def generate_fallback_flashcards(text: str) -> List[Dict]:
    """Generate flashcards using rule-based approach when GPT fails"""
    flashcards = []
    
    try:
        # Extract definitions from text
        definition_patterns = [
            r'([А-Я][а-я]+(?:\s+[а-я]+){0,3})\s+(?:—|–|-|это|является)\s*([^.]+)\.',
            r'([А-Я][а-я]+(?:\s+[а-я]+){0,3})\s+называется\s+([^.]+)\.',
            r'Под\s+([а-я]+(?:\s+[а-я]+){0,3})\s+понимают\s+([^.]+)\.'
        ]
        
        for pattern in definition_patterns:
            matches = re.findall(pattern, text, re.MULTILINE)
            for term, definition in matches[:3]:  # Limit definitions
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
        
        # Extract formulas
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
        
        # Extract examples
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
        
        # Extract key statements
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
        
        # If not enough cards, add general ones
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
        # Return at least one card
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
    """Calculate next review date based on difficulty"""
    days_map = {1: 1, 2: 3, 3: 7}
    days = days_map.get(difficulty, 3)
    next_date = datetime.now() + timedelta(days=days)
    return next_date.strftime("%Y-%m-%d")

def generate_mind_map(text: str, topics: List[Dict]) -> Dict:
    """Generate mind map structure"""
    try:
        # Use actual topic titles
        if topics and 'title' in topics[0]:
            central_topic = topics[0]['title']
        else:
            central_topic = "Основная тема"
        
        # Create branches from main topics
        branches = []
        colors = ["#FF6B6B", "#4ECDC4", "#45B7D1", "#96CEB4", "#FECA57", "#48DBFB"]
        
        for i, topic in enumerate(topics[:6]):  # Max 6 main branches
            branch = {
                "name": topic['title'][:40],
                "importance": 0.9 - (i * 0.1),
                "color": colors[i % len(colors)],
                "children": []
            }
            
            # Add subtopics as children
            for subtopic in topic.get('subtopics', [])[:3]:
                branch['children'].append({
                    "name": subtopic[:30],
                    "importance": 0.5,
                    "color": branch['color']
                })
            
            # Add key concepts as additional children if no subtopics
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

def generate_study_plan(topics: List[Dict], flashcards: List[Dict], estimated_hours: int = 10) -> Dict:
    """Generate personalized study plan with meaningful topics"""
    try:
        # Calculate sessions based on content
        total_cards = len(flashcards)
        total_topics = len(topics)
        
        # Estimate time per session
        minutes_per_session = 45
        total_sessions = max(3, min(10, estimated_hours * 60 // minutes_per_session))
        
        sessions = []
        
        # Group topics by complexity
        basic_topics = [t for t in topics if t.get('complexity') == 'basic']
        intermediate_topics = [t for t in topics if t.get('complexity') == 'intermediate']
        advanced_topics = [t for t in topics if t.get('complexity') == 'advanced']
        
        # Distribute topics across sessions logically
        topic_distribution = []
        
        # First third: basic topics
        for i in range(total_sessions // 3):
            if basic_topics:
                topic_distribution.append(basic_topics.pop(0))
            elif intermediate_topics:
                topic_distribution.append(intermediate_topics.pop(0))
        
        # Second third: intermediate topics
        for i in range(total_sessions // 3, 2 * total_sessions // 3):
            if intermediate_topics:
                topic_distribution.append(intermediate_topics.pop(0))
            elif basic_topics:
                topic_distribution.append(basic_topics.pop(0))
            elif advanced_topics:
                topic_distribution.append(advanced_topics.pop(0))
        
        # Last third: advanced topics and review
        for i in range(2 * total_sessions // 3, total_sessions):
            if advanced_topics:
                topic_distribution.append(advanced_topics.pop(0))
            elif intermediate_topics:
                topic_distribution.append(intermediate_topics.pop(0))
            else:
                # Review previous topics
                if i - 3 >= 0 and i - 3 < len(topic_distribution):
                    topic_distribution.append(topic_distribution[i - 3])
        
        # Create sessions
        cards_per_session = max(3, total_cards // total_sessions)
        card_idx = 0
        
        for day in range(1, total_sessions + 1):
            session_topics = []
            session_cards = []
            
            # Add topic for this session
            if day - 1 < len(topic_distribution):
                topic = topic_distribution[day - 1]
                session_topics.append(topic['title'])
            
            # Add flashcards
            session_card_count = min(cards_per_session, total_cards - card_idx)
            for _ in range(session_card_count):
                if card_idx < total_cards:
                    session_cards.append(card_idx)
                    card_idx += 1
            
            # Determine focus based on day
            if day <= total_sessions // 3:
                focus = "Понимание базовых концепций"
            elif day <= 2 * total_sessions // 3:
                focus = "Углубление знаний и практика"
            else:
                focus = "Закрепление и проверка понимания"
            
            # Create meaningful exercises
            exercises = []
            if session_topics:
                topic_name = session_topics[0]
                exercises.extend([
                    f"Объясните своими словами: {topic_name}",
                    f"Приведите 3 примера применения концепций из темы '{topic_name}'",
                    f"Создайте схему или диаграмму для визуализации '{topic_name}'"
                ])
            
            sessions.append({
                "day": day,
                "topics": session_topics,
                "flashcard_ids": session_cards,
                "duration_minutes": minutes_per_session,
                "focus": focus,
                "exercises": exercises[:3]
            })
        
        # Create meaningful milestones based on actual topics
        milestones = []
        if topics:
            milestones.extend([
                f"Понимать основные концепции: {', '.join([t['title'] for t in topics[:3]])}",
                "Уметь объяснить взаимосвязи между изученными темами",
                "Применять полученные знания для решения практических задач",
                f"Успешно ответить на 80% флеш-карт уровня сложности 2 и выше"
            ])
        
        # Spaced repetition schedule
        review_schedule = [1, 3, 7, 14, 30]  # Days for review
        
        return {
            "sessions": sessions,
            "milestones": milestones[:4],
            "review_schedule": review_schedule,
            "total_hours": total_sessions * minutes_per_session / 60,
            "completion_date": (datetime.now() + timedelta(days=total_sessions)).strftime("%Y-%m-%d")
        }
        
    except Exception as e:
        logger.error(f"Error generating study plan: {str(e)}")
        return {
            "sessions": [{"day": 1, "topics": ["Изучение материала"], "duration_minutes": 45}],
            "milestones": ["Изучить материал"],
            "review_schedule": [1, 3, 7],
            "total_hours": 0.75,
            "completion_date": datetime.now().strftime("%Y-%m-%d")
        }

def assess_content_quality(text: str, topics: List[Dict], summary: str, flashcards: List[Dict]) -> Dict:
    """Assess the quality of generated content"""
    try:
        # Depth score - based on topic hierarchy and quality
        depth_score = 0.0
        
        # Check if topics have meaningful titles (not just text snippets)
        meaningful_titles = sum(1 for t in topics if len(t.get('title', '')) < 100 and not t['title'].endswith('...'))
        depth_score += min(0.5, meaningful_titles / len(topics) * 0.5) if topics else 0
        
        # Check for subtopics and examples
        topics_with_subtopics = sum(1 for t in topics if len(t.get('subtopics', [])) > 0)
        topics_with_examples = sum(1 for t in topics if len(t.get('examples', [])) > 0)
        depth_score += min(0.25, topics_with_subtopics / len(topics) * 0.25) if topics else 0
        depth_score += min(0.25, topics_with_examples / len(topics) * 0.25) if topics else 0
        
        # Coverage score - based on key concepts extracted
        total_concepts = sum(len(t.get('key_concepts', [])) for t in topics)
        coverage_score = min(1.0, total_concepts / 30)
        
        # Practical score - based on examples and applications
        total_examples = sum(len(t.get('examples', [])) for t in topics)
        practical_flashcards = sum(1 for f in flashcards if f.get('type') in ['application', 'problem'])
        practical_score = min(1.0, (total_examples / 10 * 0.5) + (practical_flashcards / 5 * 0.5))
        
        # Clarity score - based on summary structure and flashcard quality
        clarity_score = 0.5  # Base score
        if len(summary) > 100 and '##' in summary:
            clarity_score += 0.3
        if flashcards and all('hint' in f and 'memory_hook' in f for f in flashcards[:5]):
            clarity_score += 0.2
        
        # Generate suggestions
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

def process_file(filepath: str, filename: str) -> Dict[str, Any]:
    """Advanced processing pipeline with improved topic extraction"""
    try:
        logger.info(f"Starting advanced processing for: {filename}")
        
        # Extract text based on file type
        file_ext = Path(filename).suffix.lower()
        
        if file_ext == '.pdf':
            text = extract_text_from_pdf(filepath)
            video_data = None
        elif file_ext in ['.mp4', '.mov', '.mkv']:
            video_data = transcribe_video_with_timestamps(filepath)
            text = video_data['full_text']
        else:
            raise ValueError(f"Unsupported file type: {file_ext}")
        
        if not text or len(text.strip()) < 100:
            raise ValueError("Extracted text is too short or empty")
        
        logger.info(f"Extracted {len(text)} characters of text")
        
        # Try to use GPT for better topic extraction
        try:
            topics_data = extract_topics_with_gpt(text)
            logger.info("Successfully extracted topics with GPT")
        except Exception as e:
            logger.warning(f"Failed to extract topics with GPT: {str(e)}, falling back to local method")
            topics_data = extract_topics_fallback(text)
        
        # Generate other components
        summary = generate_summary(text)
        flashcards = generate_flashcards(text)
        mind_map = generate_mind_map(text, topics_data.get('main_topics', []))
        study_plan = generate_study_plan(topics_data.get('main_topics', []), flashcards)
        quality = assess_content_quality(text, topics_data.get('main_topics', []), summary, flashcards)
        
        # Compile results
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
        
        # Add video-specific data if available
        if video_data:
            result["video_segments"] = video_data.get('segments', [])
            result["key_moments"] = video_data.get('key_moments', [])
        
        logger.info(f"Advanced processing complete. Quality score: {quality['overall_score']}")
        
        return result
        
    except Exception as e:
        logger.error(f"Error in advanced processing: {str(e)}")
        raise

# Test function
if __name__ == "__main__":
    # Test with sample text
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