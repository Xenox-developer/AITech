import os
import json
import logging
import re
from typing import List, Tuple
import numpy as np
from pathlib import Path
from dotenv import load_dotenv

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

# OpenAI for summarization and flashcards
from openai import OpenAI

# Configure logging
logger = logging.getLogger(__name__)

# Initialize models
device = "cuda" if torch.cuda.is_available() else "cpu"
compute_type = "float16" if device == "cuda" else "int8"

# Global variables for models
sentence_model = None
whisper_model = None
openai_client = None

# Load models (these will be cached after first use)
def load_models():
    """Load AI models"""
    global sentence_model, whisper_model, openai_client
    
    logger.info("Loading models...")
    
    # Sentence transformer for embeddings
    sentence_model = SentenceTransformer("intfloat/e5-large-v2", device=device)
    
    # Whisper for audio transcription
    whisper_model = whisperx.load_model("large-v3", device, compute_type=compute_type)
    
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
    # Models will be loaded on first use

def extract_text_from_pdf(filepath: str) -> str:
    """Extract text from PDF file"""
    try:
        text = extract_text(filepath)
        return text.strip()
    except Exception as e:
        logger.error(f"Error extracting text from PDF: {str(e)}")
        raise

def transcribe_video(filepath: str) -> str:
    """Transcribe video/audio using Whisper"""
    try:
        logger.info(f"Transcribing video: {filepath}")
        
        # Load audio
        audio = whisperx.load_audio(filepath)
        
        # Transcribe
        result = whisper_model.transcribe(audio, batch_size=16)
        
        # Extract text without timestamps
        text = " ".join([segment["text"] for segment in result["segments"]])
        
        return text.strip()
    except Exception as e:
        logger.error(f"Error transcribing video: {str(e)}")
        raise

def split_into_paragraphs(text: str, min_length: int = 100) -> List[str]:
    """Split text into paragraphs"""
    # Split by double newlines or multiple spaces
    paragraphs = re.split(r'\n\n+|\r\n\r\n+', text)
    
    # Clean and filter paragraphs
    cleaned = []
    for p in paragraphs:
        p = p.strip()
        if len(p) >= min_length:
            cleaned.append(p)
    
    # If no good paragraphs, split by sentences
    if len(cleaned) < 3:
        sentences = re.split(r'[.!?]\s+', text)
        current_paragraph = ""
        cleaned = []
        
        for sentence in sentences:
            current_paragraph += sentence + ". "
            if len(current_paragraph) >= min_length:
                cleaned.append(current_paragraph.strip())
                current_paragraph = ""
        
        if current_paragraph:
            cleaned.append(current_paragraph.strip())
    
    return cleaned

def extract_topics(text: str, max_topics: int = 12) -> List[str]:
    """Extract main topics using embeddings and clustering"""
    try:
        # Split into paragraphs
        paragraphs = split_into_paragraphs(text)
        
        if len(paragraphs) < 3:
            # If too few paragraphs, return generic topic
            return ["Основная тема документа"]
        
        logger.info(f"Processing {len(paragraphs)} paragraphs for topic extraction")
        
        # Generate embeddings
        embeddings = sentence_model.encode(paragraphs, convert_to_tensor=False)
        embeddings = normalize(embeddings)
        
        # Cluster paragraphs
        min_cluster_size = max(2, min(3, len(paragraphs) // 4))  # Ensure min_cluster_size >= 2
        clusterer = HDBSCAN(
            min_cluster_size=min_cluster_size,
            min_samples=1,
            metric='euclidean'
        )
        
        cluster_labels = clusterer.fit_predict(embeddings)
        
        # Extract topics (first sentence of first paragraph in each cluster)
        topics = []
        unique_labels = set(cluster_labels)
        
        for label in unique_labels:
            if label == -1:  # Skip noise cluster
                continue
                
            # Find paragraphs in this cluster
            cluster_indices = [i for i, l in enumerate(cluster_labels) if l == label]
            
            if cluster_indices:
                # Get first paragraph of cluster
                first_paragraph = paragraphs[cluster_indices[0]]
                
                # Extract first sentence as topic
                first_sentence = re.split(r'[.!?]\s+', first_paragraph)[0]
                if first_sentence:
                    topics.append(first_sentence.strip() + ".")
        
        # If too few topics, add some generic ones based on content analysis
        if len(topics) < 3:
            # Try to extract key concepts from the text
            key_phrases = extract_key_phrases(text)
            for phrase in key_phrases:
                if len(topics) < max_topics:
                    topics.append(f"Концепция: {phrase}")
        
        # Limit to max topics
        topics = topics[:max_topics]
        
        logger.info(f"Extracted {len(topics)} topics")
        return topics
        
    except Exception as e:
        logger.error(f"Error extracting topics: {str(e)}")
        # Return fallback topic
        return ["Основная тема документа"]

def extract_key_phrases(text: str, max_phrases: int = 5) -> List[str]:
    """Extract key phrases from text (simple implementation)"""
    # Common Russian stop words
    stop_words = {
        'и', 'в', 'на', 'с', 'по', 'для', 'к', 'от', 'из', 'у', 'о', 'об',
        'это', 'что', 'как', 'так', 'но', 'да', 'нет', 'если', 'то', 'же',
        'бы', 'ли', 'а', 'или', 'ни', 'не', 'ну', 'вот', 'уже', 'еще'
    }
    
    # Extract words
    words = re.findall(r'\b[а-яА-Я]{4,}\b', text.lower())
    
    # Filter stop words and count frequencies
    word_freq = {}
    for word in words:
        if word not in stop_words:
            word_freq[word] = word_freq.get(word, 0) + 1
    
    # Get top words
    top_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)[:max_phrases]
    
    return [word[0].capitalize() for word in top_words]

def generate_summary(text: str) -> str:
    """Generate summary using GPT-4"""
    try:
        # Ensure models are loaded
        if not openai_client:
            load_models()
            
        logger.info("Generating summary with GPT-4")
        
        # Limit text length for API
        max_chars = 10000
        if len(text) > max_chars:
            text = text[:max_chars] + "..."
        
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "Ты - помощник для создания кратких резюме учебных материалов на русском языке."
                },
                {
                    "role": "user",
                    "content": f"""Сделай краткое резюме этого текста.
Требования:
- 5-7 пунктов, подчеркивающих главные идеи
- Каждый пункт начинается с '•'
- Общий объем не более 120 слов
- Пиши на русском языке

Текст:
{text}"""
                }
            ],
            temperature=0.7,
            max_tokens=500
        )
        
        summary = response.choices[0].message.content.strip()
        
        # Ensure bullet points
        if '•' not in summary:
            lines = summary.split('\n')
            summary = '\n'.join(['• ' + line.strip() for line in lines if line.strip()])
        
        return summary
        
    except Exception as e:
        logger.error(f"Error generating summary: {str(e)}")
        return "• Не удалось создать резюме из-за технической ошибки"

def generate_flashcards(text: str, num_cards: int = 12) -> List[dict]:
    """Generate flashcards using GPT-4"""
    try:
        # Ensure models are loaded
        if not openai_client:
            load_models()
            
        logger.info("Generating flashcards with GPT-4")
        
        # Limit text length for API
        max_chars = 10000
        if len(text) > max_chars:
            text = text[:max_chars] + "..."
        
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "Ты - помощник для создания обучающих флеш-карточек на русском языке."
                },
                {
                    "role": "user",
                    "content": f"""Создай {num_cards} флеш-карточек (вопрос-ответ) по этому тексту.

Требования:
- Формат JSON массив: [{{"q": "вопрос", "a": "ответ"}}, ...]
- Вопросы должны проверять понимание ключевых концепций
- Ответы должны быть информативными, но краткими (1-3 предложения)
- Ответ НЕ должен дублировать формулировку вопроса
- Покрой разные аспекты материала
- Пиши на русском языке

Текст:
{text}

Верни ТОЛЬКО валидный JSON массив, без дополнительного текста."""
                }
            ],
            temperature=0.8,
            max_tokens=2000
        )
        
        content = response.choices[0].message.content.strip()
        
        # Extract JSON from response
        json_match = re.search(r'\[.*\]', content, re.DOTALL)
        if json_match:
            json_str = json_match.group(0)
        else:
            json_str = content
        
        # Parse JSON
        flashcards = json.loads(json_str)
        
        # Validate format
        valid_flashcards = []
        for card in flashcards:
            if isinstance(card, dict) and 'q' in card and 'a' in card:
                # Check that answer doesn't duplicate question
                if card['a'].lower().strip() != card['q'].lower().strip():
                    valid_flashcards.append({
                        'q': card['q'].strip(),
                        'a': card['a'].strip()
                    })
        
        # Ensure we have at least some cards
        if len(valid_flashcards) < 3:
            # Generate fallback cards
            valid_flashcards = [
                {
                    'q': 'Какова основная тема этого материала?',
                    'a': 'Материал посвящен изучению представленной темы с акцентом на ключевые концепции и практическое применение.'
                },
                {
                    'q': 'Какие ключевые понятия были рассмотрены?',
                    'a': 'В материале рассмотрены основные понятия и принципы, необходимые для понимания данной предметной области.'
                },
                {
                    'q': 'Как можно применить полученные знания?',
                    'a': 'Полученные знания можно применить для решения практических задач и углубления понимания темы.'
                }
            ]
        
        return valid_flashcards[:num_cards]
        
    except Exception as e:
        logger.error(f"Error generating flashcards: {str(e)}")
        # Return fallback flashcards
        return [
            {
                'q': 'Что представляет собой данный учебный материал?',
                'a': 'Это образовательный контент, предназначенный для изучения и усвоения новых знаний.'
            }
        ]

def process_file(filepath: str, filename: str) -> Tuple[List[str], str, List[dict]]:
    """Main processing pipeline"""
    try:
        logger.info(f"Starting processing for: {filename}")
        
        # Extract text based on file type
        file_ext = Path(filename).suffix.lower()
        
        if file_ext == '.pdf':
            text = extract_text_from_pdf(filepath)
        elif file_ext in ['.mp4', '.mov', '.mkv']:
            text = transcribe_video(filepath)
        else:
            raise ValueError(f"Unsupported file type: {file_ext}")
        
        if not text or len(text.strip()) < 100:
            raise ValueError("Extracted text is too short or empty")
        
        logger.info(f"Extracted {len(text)} characters of text")
        
        # Process text to extract topics, summary, and flashcards
        topics = extract_topics(text)
        summary = generate_summary(text)
        flashcards = generate_flashcards(text)
        
        logger.info(f"Processing complete: {len(topics)} topics, {len(flashcards)} flashcards")
        
        return topics, summary, flashcards
        
    except Exception as e:
        logger.error(f"Error in process_file: {str(e)}")
        raise

# Test function for development
if __name__ == "__main__":
    # Test with sample text
    sample_text = """
    Машинное обучение является важной областью искусственного интеллекта.
    Оно позволяет компьютерам учиться на данных без явного программирования.
    
    Существуют различные типы машинного обучения: обучение с учителем,
    обучение без учителя и обучение с подкреплением.
    
    Нейронные сети представляют собой мощный инструмент для решения
    сложных задач распознавания образов и обработки естественного языка.
    """
    
    print("Testing topic extraction...")
    topics = extract_topics(sample_text)
    print("Topics:", topics)
    
    # Only test OpenAI functions if API key is available
    if os.environ.get('OPENAI_API_KEY'):
        print("\nTesting summary generation...")
        summary = generate_summary(sample_text)
        print("Summary:", summary)
        
        print("\nTesting flashcard generation...")
        flashcards = generate_flashcards(sample_text)
        print("Flashcards:", json.dumps(flashcards, ensure_ascii=False, indent=2))
    else:
        print("\nSkipping OpenAI tests - OPENAI_API_KEY not set")
        print("To test OpenAI features:")
        print("1. Get API key from https://platform.openai.com")
        print("2. Set environment variable: export OPENAI_API_KEY='your-key-here'")
        print("3. Or create .env file with: OPENAI_API_KEY=your-key-here")