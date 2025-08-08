import os
import json
import sqlite3
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, flash, send_file, jsonify, session, send_from_directory
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.utils import secure_filename
from usage_tracking import usage_tracker
from auth import User, init_auth_db, generate_password_hash, check_password_hash
from migration_manager import run_migrations
from analytics import element_analytics
from subscription_manager import subscription_manager, SUBSCRIPTION_PLANS
from subscription_decorators import require_subscription_limit, track_usage, subscription_required
from gamification import gamification
from smart_upgrade_triggers import smart_triggers
from analytics_manager import analytics_manager

# Функция проверки прав администратора
def is_admin(user):
    """Проверка, является ли пользователь администратором"""
    if not user or not user.is_authenticated:
        return False
    return user.email == 'test@test.ru'

def get_user_learning_stats(user_id):
    """Получение персональной статистики обучения пользователя"""
    conn = sqlite3.connect('ai_study.db')
    c = conn.cursor()
    
    # Общая статистика пользователя
    c.execute('''
        SELECT COUNT(*) FROM result WHERE user_id = ?
    ''', (user_id,))
    total_results = c.fetchone()[0]
    
    # Статистика по флеш-картам
    c.execute('''
        SELECT COUNT(*) FROM user_progress 
        WHERE user_id = ? AND consecutive_correct >= 3
    ''', (user_id,))
    mastered_cards = c.fetchone()[0]
    
    c.execute('''
        SELECT COUNT(*) FROM user_progress WHERE user_id = ?
    ''', (user_id,))
    total_cards_studied = c.fetchone()[0]
    
    # Карточки для повторения сегодня
    c.execute('''
        SELECT COUNT(*) FROM user_progress 
        WHERE user_id = ? AND date(next_review) <= date('now')
    ''', (user_id,))
    cards_due_today = c.fetchone()[0]
    
    # Статистика по типам файлов
    c.execute('''
        SELECT file_type, COUNT(*) 
        FROM result 
        WHERE user_id = ? 
        GROUP BY file_type
    ''', (user_id,))
    file_types = dict(c.fetchall())
    
    # Активность за последние 30 дней
    c.execute('''
        SELECT DATE(created_at) as date, COUNT(*) as count
        FROM result 
        WHERE user_id = ? AND created_at >= date('now', '-30 days')
        GROUP BY DATE(created_at)
        ORDER BY date DESC
    ''', (user_id,))
    recent_activity = c.fetchall()
    
    # Прогресс изучения (на основе флеш-карт)
    learning_progress = 0
    if total_cards_studied > 0:
        learning_progress = min(100, int((mastered_cards / max(total_cards_studied, 1)) * 100))
    
    # Расчет контрольных точек на основе реальных данных
    checkpoints = calculate_user_checkpoints(user_id, total_results, mastered_cards, total_cards_studied)
    
    # Целевые показатели
    targets = calculate_user_targets(user_id, total_results, mastered_cards, total_cards_studied)
    
    # Персональные учебные сессии
    study_sessions = get_or_create_user_study_sessions(user_id)
    
    conn.close()
    
    return {
        'total_results': total_results,
        'mastered_cards': mastered_cards,
        'total_cards_studied': total_cards_studied,
        'cards_due_today': cards_due_today,
        'file_types': file_types,
        'recent_activity': recent_activity,
        'learning_progress': learning_progress,
        'checkpoints': checkpoints,
        'targets': targets,
        'study_sessions': study_sessions
    }

def calculate_user_checkpoints(user_id, total_results, mastered_cards, total_cards_studied):
    """Расчет персональных контрольных точек пользователя"""
    checkpoints = []
    
    # Контрольная точка 1: Первые шаги
    first_progress = min(100, (total_results / 3) * 100) if total_results > 0 else 0
    checkpoints.append({
        'title': 'Первые шаги',
        'description': 'Загрузка и анализ первых файлов',
        'progress': int(first_progress),
        'status': 'completed' if total_results >= 3 else ('current' if total_results > 0 else 'upcoming'),
        'target': f'{min(total_results, 3)}/3 файлов'
    })
    
    # Контрольная точка 2: Активное изучение
    study_progress = min(100, (total_cards_studied / 20) * 100) if total_cards_studied > 0 else 0
    checkpoints.append({
        'title': 'Активное изучение',
        'description': 'Работа с флеш-картами и повторения',
        'progress': int(study_progress),
        'status': 'completed' if total_cards_studied >= 20 else ('current' if total_cards_studied > 0 else 'upcoming'),
        'target': f'{min(total_cards_studied, 20)}/20 карточек'
    })
    
    # Контрольная точка 3: Мастерство
    mastery_progress = min(100, (mastered_cards / 10) * 100) if mastered_cards > 0 else 0
    checkpoints.append({
        'title': 'Достижение мастерства',
        'description': 'Освоение материала и закрепление знаний',
        'progress': int(mastery_progress),
        'status': 'completed' if mastered_cards >= 10 else ('current' if mastered_cards > 0 else 'upcoming'),
        'target': f'{min(mastered_cards, 10)}/10 освоенных'
    })
    
    # Контрольная точка 4: Эксперт
    expert_progress = min(100, (total_results / 10) * 100) if total_results > 0 else 0
    checkpoints.append({
        'title': 'Экспертный уровень',
        'description': 'Глубокое изучение разнообразных материалов',
        'progress': int(expert_progress),
        'status': 'completed' if total_results >= 10 else ('current' if total_results >= 5 else 'upcoming'),
        'target': f'{min(total_results, 10)}/10 файлов'
    })
    
    return checkpoints

def calculate_user_targets(user_id, total_results, mastered_cards, total_cards_studied):
    """Расчет персональных целевых показателей"""
    targets = []
    
    # Цель 1: Удержание знаний
    retention_rate = 0
    if total_cards_studied > 0:
        retention_rate = min(100, int((mastered_cards / total_cards_studied) * 100))
    
    targets.append({
        'label': 'Удержание знаний',
        'value': f'{retention_rate}%',
        'progress': retention_rate,
        'color': 'success' if retention_rate >= 70 else ('warning' if retention_rate >= 50 else 'danger')
    })
    
    # Цель 2: Активность изучения
    activity_rate = min(100, (total_results / 5) * 100) if total_results > 0 else 0
    targets.append({
        'label': 'Активность изучения',
        'value': f'{int(activity_rate)}%',
        'progress': int(activity_rate),
        'color': 'info' if activity_rate >= 80 else ('warning' if activity_rate >= 40 else 'danger')
    })
    
    return targets

def get_or_create_user_study_sessions(user_id):
    """Получение или создание персональных учебных сессий пользователя"""
    conn = sqlite3.connect('ai_study.db')
    c = conn.cursor()
    
    logger.info(f"Getting study sessions for user {user_id}")
    
    # Сначала проверяем, есть ли уже созданные сессии для пользователя
    c.execute('''
        SELECT id, title, description, phase, difficulty, duration_minutes, 
               status, created_at, started_at, completed_at, result_id, session_type
        FROM study_sessions 
        WHERE user_id = ? 
        ORDER BY created_at ASC
    ''', (user_id,))
    
    existing_sessions = c.fetchall()
    
    logger.info(f"Found {len(existing_sessions)} existing sessions for user {user_id}")
    
    if existing_sessions:
        # Если сессии уже есть, проверяем, нужно ли добавить новые
        logger.info(f"Found existing sessions, checking for new files for user {user_id}")
        
        # Получаем ID файлов, для которых уже есть сессии
        existing_result_ids = set()
        for row in existing_sessions:
            result_id = row[10]  # result_id
            if result_id:
                existing_result_ids.add(result_id)
        
        # Получаем все файлы пользователя
        c.execute('''
            SELECT id, filename, file_type, created_at 
            FROM result 
            WHERE user_id = ? 
            ORDER BY created_at ASC
        ''', (user_id,))
        
        all_user_files = c.fetchall()
        
        # Находим файлы без сессий
        new_files = []
        for file_data in all_user_files:
            if file_data[0] not in existing_result_ids:  # file_data[0] это id
                new_files.append(file_data)
        
        # Создаем сессии для новых файлов
        if new_files:
            logger.info(f"Creating sessions for {len(new_files)} new files")
            
            # Получаем статистику для определения статуса новых сессий
            c.execute('''
                SELECT COUNT(*) FROM user_progress 
                WHERE user_id = ? AND consecutive_correct >= 3
            ''', (user_id,))
            mastered_cards = c.fetchone()[0]
            
            # Определяем следующий номер сессии
            next_session_number = len([s for s in existing_sessions if s[11] == 'study']) + 1  # session_type == 'study'
            
            for file_data in new_files[:5]:  # Максимум 5 новых сессий
                result_id, filename, file_type, created_at = file_data
                
                # Определяем фазу на основе номера
                if next_session_number == 1:
                    phase = 'ОСНОВЫ'
                elif next_session_number <= 3:
                    phase = 'РАЗВИТИЕ'
                else:
                    phase = 'МАСТЕРСТВО'
                
                # Создаем персональную сессию на основе файла
                file_name_short = filename[:30] + '...' if len(filename) > 30 else filename
                title = f'Сессия {next_session_number}: Изучение "{file_name_short}"'
                description = f'Работа с материалом из файла {file_type.upper()}'
                difficulty = 'легкий' if next_session_number == 1 else ('средний' if next_session_number <= 3 else 'сложный')
                status = 'available'
                
                # Сохраняем новую сессию в базу данных
                c.execute('''
                    INSERT INTO study_sessions 
                    (user_id, result_id, session_type, title, description, phase, difficulty, duration_minutes, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (user_id, result_id, 'study', title, description, phase, difficulty, 45, status))
                
                next_session_number += 1
            
            conn.commit()
            
            # Перезапрашиваем все сессии после добавления новых
            c.execute('''
                SELECT id, title, description, phase, difficulty, duration_minutes, 
                       status, created_at, started_at, completed_at, result_id, session_type
                FROM study_sessions 
                WHERE user_id = ? 
                ORDER BY created_at ASC
            ''', (user_id,))
            
            existing_sessions = c.fetchall()
        
        # Формируем список всех сессий для возврата
        sessions = []
        for row in existing_sessions:
            session_id, title, description, phase, difficulty, duration_minutes, status, created_at, started_at, completed_at, result_id, session_type = row
            
            # Определяем класс фазы
            phase_class = f'phase-{phase.lower()}'
            difficulty_class = f'difficulty-{difficulty}'
            
            # Определяем текст действия на основе статуса
            if status == 'completed':
                action_text = 'Повторить'
            elif status == 'in_progress':
                action_text = 'Продолжить'
            else:
                action_text = 'Начать'
            
            sessions.append({
                'id': session_id,
                'phase': phase,
                'phase_class': phase_class,
                'title': title,
                'description': description,
                'date': datetime.strptime(created_at, '%Y-%m-%d %H:%M:%S').strftime('%d.%m.%Y'),
                'duration': f'{duration_minutes} мин',
                'difficulty': difficulty,
                'difficulty_class': difficulty_class,
                'status': status,
                'action_text': action_text,
                'result_id': result_id,
                'session_type': session_type,
                'started_at': started_at,
                'completed_at': completed_at
            })
        
        conn.close()
        return sessions
    
    # Если сессий нет, создаем их на основе файлов пользователя
    c.execute('''
        SELECT id, filename, file_type, created_at 
        FROM result 
        WHERE user_id = ? 
        ORDER BY created_at ASC 
        LIMIT 5
    ''', (user_id,))
    
    user_files = c.fetchall()
    
    # Получаем статистику пользователя для определения статуса сессий
    c.execute('SELECT COUNT(*) FROM result WHERE user_id = ?', (user_id,))
    total_results = c.fetchone()[0]
    
    c.execute('''
        SELECT COUNT(*) FROM user_progress 
        WHERE user_id = ? AND consecutive_correct >= 3
    ''', (user_id,))
    mastered_cards = c.fetchone()[0]
    
    c.execute('SELECT COUNT(*) FROM user_progress WHERE user_id = ?', (user_id,))
    total_cards_studied = c.fetchone()[0]
    
    sessions = []
    
    if total_results == 0:
        # Для пользователей без файлов - создаем мотивирующую сессию
        c.execute('''
            INSERT INTO study_sessions 
            (user_id, session_type, title, description, phase, difficulty, duration_minutes, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, 'onboarding', 'Начните свое обучение', 
              'Загрузите первый файл для анализа', 'НАЧАЛО', 'легкий', 15, 'available'))
        
        session_id = c.lastrowid
        
        sessions.append({
            'id': session_id,
            'phase': 'НАЧАЛО',
            'phase_class': 'phase-начало',
            'title': 'Начните свое обучение',
            'description': 'Загрузите первый файл для анализа',
            'date': datetime.now().strftime('%d.%m.%Y'),
            'duration': '15 мин',
            'difficulty': 'легкий',
            'difficulty_class': 'difficulty-легкий',
            'status': 'available',
            'action_text': 'Загрузить файл',
            'action_url': '/',
            'session_type': 'onboarding'
        })
    else:
        # Создаем сессии на основе реальных файлов пользователя
        for i, (result_id, filename, file_type, created_at) in enumerate(user_files[:3], 1):
            # Определяем фазу на основе порядка
            if i == 1:
                phase = 'ОСНОВЫ'
            elif i == 2:
                phase = 'РАЗВИТИЕ'
            else:
                phase = 'МАСТЕРСТВО'
            
            # Создаем персональную сессию на основе файла
            file_name_short = filename[:30] + '...' if len(filename) > 30 else filename
            title = f'Сессия {i}: Изучение "{file_name_short}"'
            description = f'Работа с материалом из файла {file_type.upper()}'
            difficulty = 'средний' if i <= 2 else 'сложный'
            status = 'completed' if mastered_cards > i * 2 else 'available'
            
            # Сохраняем сессию в базу данных
            c.execute('''
                INSERT INTO study_sessions 
                (user_id, result_id, session_type, title, description, phase, difficulty, duration_minutes, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (user_id, result_id, 'study', title, description, phase, difficulty, 45, status))
            
            session_id = c.lastrowid
            
            sessions.append({
                'id': session_id,
                'phase': phase,
                'phase_class': f'phase-{phase.lower()}',
                'title': title,
                'description': description,
                'date': datetime.strptime(created_at, '%Y-%m-%d %H:%M:%S').strftime('%d.%m.%Y'),
                'duration': '45 мин',
                'difficulty': difficulty,
                'difficulty_class': f'difficulty-{difficulty}',
                'status': status,
                'action_text': 'Повторить' if status == 'completed' else 'Начать',
                'filename': filename,
                'file_type': file_type,
                'result_id': result_id,
                'session_type': 'study'
            })
        
        # Добавляем сессию повторения, если есть карточки для повторения
        if total_cards_studied > 0:
            c.execute('''
                INSERT INTO study_sessions 
                (user_id, session_type, title, description, phase, difficulty, duration_minutes, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (user_id, 'review', 'Сессия повторения', 
                  f'Повторение {total_cards_studied} изученных карточек', 
                  'ПОВТОРЕНИЕ', 'легкий', 30, 'available'))
            
            session_id = c.lastrowid
            
            sessions.append({
                'id': session_id,
                'phase': 'ПОВТОРЕНИЕ',
                'phase_class': 'phase-повторение',
                'title': 'Сессия повторения',
                'description': f'Повторение {total_cards_studied} изученных карточек',
                'date': datetime.now().strftime('%d.%m.%Y'),
                'duration': '30 мин',
                'difficulty': 'легкий',
                'difficulty_class': 'difficulty-легкий',
                'status': 'available',
                'action_text': 'Повторить',
                'cards_count': total_cards_studied,
                'session_type': 'review'
            })
    
    conn.commit()
    conn.close()
    
    return sessions
import logging
from pathlib import Path
import yt_dlp
import tempfile
import re
import secrets

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['MAX_CONTENT_LENGTH'] = int(os.environ.get('MAX_UPLOAD_MB', 200)) * 1024 * 1024
app.config['UPLOAD_FOLDER'] = 'uploads'

# Настройка Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Пожалуйста, войдите в систему для доступа к этой странице.'
login_manager.login_message_category = 'info'

@login_manager.user_loader
def load_user(user_id):
    return User.get(int(user_id))

# Убедитесь, что папка для загрузки существует
Path(app.config['UPLOAD_FOLDER']).mkdir(exist_ok=True)

# Настройка ведения журнала логов
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('app.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Допустимые форматы файла
ALLOWED_EXTENSIONS = {'pdf', 'pptx', 'mp4', 'mov', 'mkv'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def is_valid_video_url(url):
    """Проверка валидности URL для загрузки видео"""
    # Поддерживаемые платформы
    supported_patterns = [
        r'youtube\.com/watch\?v=',
        r'youtu\.be/',
        r'vimeo\.com/',
        r'rutube\.ru/',
        r'ok\.ru/',
        r'vk\.com/',
        r'dailymotion\.com/',
        r'twitch\.tv/',
        r'facebook\.com/',
        r'instagram\.com/',
        r'tiktok\.com/'
    ]
    
    for pattern in supported_patterns:
        if re.search(pattern, url, re.IGNORECASE):
            return True
    return False

def download_video_from_url(url, upload_folder):
    """Загрузка видео по URL с помощью yt-dlp"""
    try:
        # Настройки для yt-dlp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_template = os.path.join(upload_folder, f'{timestamp}_%(title)s.%(ext)s')
        
        logger.info(f"📁 Output template: {output_template}")
        
        # Получаем список файлов до загрузки
        files_before = set(os.listdir(upload_folder)) if os.path.exists(upload_folder) else set()
        
        ydl_opts = {
            'format': 'best[height<=720]/best',  # Максимум 720p для экономии места
            'outtmpl': output_template,
            'restrictfilenames': True,  # Безопасные имена файлов
            'noplaylist': True,  # Только одно видео
            'extract_flat': False,
            'writethumbnail': False,
            'writeinfojson': False,
            'ignoreerrors': False,
            'no_warnings': False,
            'extractaudio': False,
            'audioformat': 'mp3',
            'audioquality': '192',
            'embed_subs': False,
            'writesubtitles': False,
            'writeautomaticsub': False,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Получаем информацию о видео
            logger.info("📋 Extracting video info...")
            info = ydl.extract_info(url, download=False)
            title = info.get('title', 'video')
            duration = info.get('duration', 0)
            
            logger.info(f"📺 Video info: {title} ({duration}s)")
            
            # Проверяем длительность (максимум 2 часа)
            if duration and duration > 7200:
                raise Exception(f"Видео слишком длинное ({duration//60} мин). Максимум 120 минут.")
            
            # Проверяем лимит длительности видео для пользователя
            if current_user and current_user.is_authenticated:
                duration_minutes = duration // 60 if duration else 0
                allowed, message = subscription_manager.check_video_duration_limit(current_user.id, duration_minutes)
                if not allowed:
                    raise Exception(message)
            
            # Загружаем видео
            logger.info("⬇️ Starting download...")
            ydl.download([url])
            logger.info("✅ Download completed")
            
            # Получаем список файлов после загрузки
            files_after = set(os.listdir(upload_folder)) if os.path.exists(upload_folder) else set()
            new_files = files_after - files_before
            
            logger.info(f"📁 New files found: {list(new_files)}")
            
            # Ищем видеофайл среди новых файлов
            video_extensions = ['.mp4', '.mkv', '.webm', '.mov', '.avi', '.flv']
            downloaded_file = None
            
            for file in new_files:
                file_ext = os.path.splitext(file)[1].lower()
                if file_ext in video_extensions:
                    downloaded_file = file
                    break
            
            if not downloaded_file:
                # Fallback: ищем по timestamp
                logger.warning("🔍 Fallback: searching by timestamp...")
                for file in os.listdir(upload_folder):
                    if file.startswith(timestamp):
                        file_ext = os.path.splitext(file)[1].lower()
                        if file_ext in video_extensions:
                            downloaded_file = file
                            break
            
            if not downloaded_file:
                logger.error(f"❌ Available files: {list(os.listdir(upload_folder))}")
                raise Exception("Не удалось найти загруженный видеофайл")
            
            filepath = os.path.join(upload_folder, downloaded_file)
            
            # Проверяем, что файл действительно существует и не пустой
            if not os.path.exists(filepath):
                raise Exception(f"Файл не найден: {filepath}")
            
            file_size = os.path.getsize(filepath)
            if file_size == 0:
                raise Exception(f"Загруженный файл пустой: {downloaded_file}")
            
            logger.info(f"✅ Successfully downloaded: {downloaded_file} ({file_size} bytes)")
            
            return filepath, downloaded_file, title
            
    except Exception as e:
        logger.error(f"❌ Error downloading video from URL {url}: {str(e)}")
        raise e

def init_db():
    """Инициализация БД SQLite"""
    # Запускаем миграции перед инициализацией
    try:
        run_migrations()
    except Exception as e:
        logger.warning(f"Migration error (continuing): {e}")
    
    conn = sqlite3.connect('ai_study.db')
    c = conn.cursor()
    
    # Таблица с результатом
    c.execute('''
        CREATE TABLE IF NOT EXISTS result (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            file_type TEXT NOT NULL,
            topics_json TEXT NOT NULL,
            summary TEXT NOT NULL,
            flashcards_json TEXT NOT NULL,
            mind_map_json TEXT,
            study_plan_json TEXT,
            quality_json TEXT,
            video_segments_json TEXT,
            key_moments_json TEXT,
            full_text TEXT,
            user_id INTEGER,
            access_token TEXT UNIQUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    
    # Добавляем колонку full_text если её нет (миграция)
    try:
        c.execute('ALTER TABLE result ADD COLUMN full_text TEXT')
        logger.info("Added full_text column to result table")
    except sqlite3.OperationalError:
        # Колонка уже существует
        pass
    
    # Добавляем колонку user_id если её нет (миграция)
    try:
        c.execute('ALTER TABLE result ADD COLUMN user_id INTEGER')
        logger.info("Added user_id column to result table")
    except sqlite3.OperationalError:
        # Колонка уже существует
        pass
    
    # Добавляем колонку test_questions_json если её нет (миграция)
    try:
        c.execute('ALTER TABLE result ADD COLUMN test_questions_json TEXT')
        logger.info("Added test_questions_json column to result table")
    except sqlite3.OperationalError:
        # Колонка уже существует
        pass
    
    # Добавляем колонку access_token если её нет (миграция)
    try:
        # Сначала добавляем колонку без UNIQUE ограничения
        c.execute('ALTER TABLE result ADD COLUMN access_token TEXT')
        logger.info("Added access_token column to result table")
        
        # Добавляем токены к существующим записям без токенов
        c.execute('SELECT id FROM result WHERE access_token IS NULL')
        results_without_tokens = c.fetchall()
        
        for (result_id,) in results_without_tokens:
            access_token = secrets.token_urlsafe(32)
            c.execute('UPDATE result SET access_token = ? WHERE id = ?', (access_token, result_id))
            logger.info(f"Added access token to existing result {result_id}")
        
        # Теперь создаем уникальный индекс
        try:
            c.execute('CREATE UNIQUE INDEX idx_result_access_token ON result(access_token)')
            logger.info("Created unique index for access_token")
        except sqlite3.OperationalError as e:
            if "already exists" not in str(e):
                logger.warning(f"Could not create unique index: {e}")
        
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e):
            # Колонка уже существует, проверяем есть ли записи без токенов
            try:
                c.execute('SELECT id FROM result WHERE access_token IS NULL')
                results_without_tokens = c.fetchall()
                
                for (result_id,) in results_without_tokens:
                    access_token = secrets.token_urlsafe(32)
                    c.execute('UPDATE result SET access_token = ? WHERE id = ?', (access_token, result_id))
                    logger.info(f"Added access token to existing result {result_id}")
            except sqlite3.OperationalError:
                # Колонка не существует, что странно, но продолжаем
                pass
        else:
            logger.error(f"Error adding access_token column: {e}")
    
    # Таблица прогресса пользователя
    c.execute('''
        CREATE TABLE IF NOT EXISTS user_progress (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            result_id INTEGER,
            flashcard_id INTEGER,
            user_id INTEGER,
            last_review TIMESTAMP,
            next_review TIMESTAMP,
            ease_factor REAL DEFAULT 2.5,
            consecutive_correct INTEGER DEFAULT 0,
            FOREIGN KEY (result_id) REFERENCES result(id),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    
    # Добавляем колонку user_id в user_progress если её нет
    try:
        c.execute('ALTER TABLE user_progress ADD COLUMN user_id INTEGER')
        logger.info("Added user_id column to user_progress table")
    except sqlite3.OperationalError:
        # Колонка уже существует
        pass
    
    # Таблица для истории чата
    c.execute('''
        CREATE TABLE IF NOT EXISTS chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            result_id INTEGER,
            user_id INTEGER,
            user_message TEXT NOT NULL,
            ai_response TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (result_id) REFERENCES result(id),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    
    # Добавляем колонку user_id в chat_history если её нет
    try:
        c.execute('ALTER TABLE chat_history ADD COLUMN user_id INTEGER')
        logger.info("Added user_id column to chat_history table")
    except sqlite3.OperationalError:
        # Колонка уже существует
        pass
    
    # Инициализируем таблицы аутентификации
    init_auth_db()
    
    conn.commit()
    conn.close()

def save_result(filename, file_type, analysis_result, page_info=None):
    """Сохранение результата в БД"""
    conn = sqlite3.connect('ai_study.db')
    c = conn.cursor()
    
    # Добавляем информацию о страницах в результат
    if page_info:
        analysis_result['page_info'] = page_info
    
    # Сериализовываем данные
    topics_json = json.dumps(analysis_result['topics_data'], ensure_ascii=False)
    flashcards_json = json.dumps(analysis_result['flashcards'], ensure_ascii=False)
    mind_map_json = json.dumps(analysis_result.get('mind_map', {}), ensure_ascii=False)
    study_plan_json = json.dumps(analysis_result.get('study_plan', {}), ensure_ascii=False)
    quality_json = json.dumps(analysis_result.get('quality_assessment', {}), ensure_ascii=False)
    video_segments_json = json.dumps(analysis_result.get('video_segments', []), ensure_ascii=False)
    key_moments_json = json.dumps(analysis_result.get('key_moments', []), ensure_ascii=False)
    
    # Получаем полный текст для чата
    full_text = analysis_result.get('full_text', '')
    
    # Генерируем тестовые вопросы заранее
    logger.info("Генерируем тестовые вопросы...")
    test_questions = generate_test_questions({
        'full_text': full_text,
        'summary': analysis_result['summary'],
        'topics_data': analysis_result['topics_data']
    })
    test_questions_json = json.dumps(test_questions, ensure_ascii=False)
    logger.info(f"Сгенерировано {len(test_questions)} тестовых вопросов")
    
    # Получаем ID текущего пользователя (если авторизован)
    user_id = current_user.id if current_user.is_authenticated else None
    
    # Генерируем уникальный токен доступа
    access_token = secrets.token_urlsafe(32)
    
    c.execute('''
        INSERT INTO result (
            filename, file_type, topics_json, summary, flashcards_json,
            mind_map_json, study_plan_json, quality_json,
            video_segments_json, key_moments_json, full_text, user_id, test_questions_json, access_token
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        filename, file_type, topics_json, analysis_result['summary'], 
        flashcards_json, mind_map_json, study_plan_json, quality_json,
        video_segments_json, key_moments_json, full_text, user_id, test_questions_json, access_token
    ))
    
    result_id = c.lastrowid
    conn.commit()
    conn.close()
    
    return access_token

def get_result_by_token(access_token):
    """Получение результата по токену доступа"""
    conn = sqlite3.connect('ai_study.db')
    c = conn.cursor()
    
    c.execute('''
        SELECT id, filename, file_type, topics_json, summary, flashcards_json,
               mind_map_json, study_plan_json, quality_json,
               video_segments_json, key_moments_json, full_text, created_at, user_id, test_questions_json
        FROM result WHERE access_token = ?
    ''', (access_token,))
    
    row = c.fetchone()
    conn.close()
    
    if row:
        result_data = {
            'id': row[0],
            'filename': row[1],
            'file_type': row[2],
            'topics_data': json.loads(row[3]),
            'summary': row[4],
            'flashcards': json.loads(row[5]),
            'mind_map': json.loads(row[6]),
            'study_plan': json.loads(row[7]),
            'quality_assessment': json.loads(row[8]),
            'video_segments': json.loads(row[9]),
            'key_moments': json.loads(row[10]),
            'full_text': row[11] or '',
            'created_at': row[12],
            'user_id': row[13],
            'test_questions': json.loads(row[14]) if row[14] else []
        }
        
        # Проверяем права доступа - если у результата есть владелец, доступ только у него
        if result_data['user_id']:
            # Результат принадлежит конкретному пользователю
            if not (current_user and current_user.is_authenticated and result_data['user_id'] == current_user.id):
                return None  # Нет доступа к чужому результату
        
        # Извлекаем информацию о страницах из mind_map (если она там сохранена)
        mind_map_data = result_data['mind_map']
        if isinstance(mind_map_data, dict) and 'page_info' in mind_map_data:
            result_data['page_info'] = mind_map_data['page_info']
        
        return result_data
    return None

def get_result(result_id, check_access=True):
    """Получение результата из базы данных по ID (для обратной совместимости)"""
    conn = sqlite3.connect('ai_study.db')
    c = conn.cursor()
    
    c.execute('''
        SELECT filename, file_type, topics_json, summary, flashcards_json,
               mind_map_json, study_plan_json, quality_json,
               video_segments_json, key_moments_json, full_text, created_at, user_id, test_questions_json, access_token
        FROM result WHERE id = ?
    ''', (result_id,))
    
    row = c.fetchone()
    conn.close()
    
    if row:
        # Проверяем права доступа
        if check_access and current_user.is_authenticated:
            result_user_id = row[12]  # user_id из результата
            if result_user_id and result_user_id != current_user.id:
                return None  # Нет доступа к чужому результату
        
        result_data = {
            'filename': row[0],
            'file_type': row[1],
            'topics_data': json.loads(row[2]),
            'summary': row[3],
            'flashcards': json.loads(row[4]),
            'mind_map': json.loads(row[5]),
            'study_plan': json.loads(row[6]),
            'quality_assessment': json.loads(row[7]),
            'video_segments': json.loads(row[8]),
            'key_moments': json.loads(row[9]),
            'full_text': row[10] or '',
            'created_at': row[11],
            'user_id': row[12],
            'test_questions': json.loads(row[13]) if row[13] else [],
            'access_token': row[14]
        }
        
        # Извлекаем информацию о страницах из mind_map (если она там сохранена)
        mind_map_data = result_data['mind_map']
        if isinstance(mind_map_data, dict) and 'page_info' in mind_map_data:
            result_data['page_info'] = mind_map_data['page_info']
        
        return result_data
    return None

# Маршруты аутентификации
@app.route('/login', methods=['GET', 'POST'])
def login():
    """Страница входа"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        remember = bool(request.form.get('remember'))
        
        if not email or not password:
            flash('Заполните все поля', 'danger')
            return render_template('auth/login.html')
        
        user = User.get_by_email(email)
        if user and user.check_password(password):
            if user.is_active:
                login_user(user, remember=remember)
                
                # Обновляем время последнего входа
                conn = sqlite3.connect('ai_study.db')
                c = conn.cursor()
                c.execute('UPDATE users SET last_login = ? WHERE id = ?', 
                         (datetime.now(), user.id))
                conn.commit()
                conn.close()
                
                logger.info(f"User logged in: {email}")
                
                # Перенаправляем на запрошенную страницу или в личный кабинет
                next_page = request.args.get('next')
                if next_page:
                    return redirect(next_page)
                return redirect(url_for('dashboard'))
            else:
                flash('Аккаунт деактивирован', 'danger')
        else:
            flash('Неверный email или пароль', 'danger')
    
    return render_template('auth/login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    """Страница регистрации"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        password_confirm = request.form.get('password_confirm', '')
        
        # Расширенная валидация
        errors = []
        
        # Проверка заполненности полей
        if not email:
            errors.append('Email обязателен для заполнения')
        if not username:
            errors.append('Имя пользователя обязательно для заполнения')
        if not password:
            errors.append('Пароль обязателен для заполнения')
        if not password_confirm:
            errors.append('Подтверждение пароля обязательно')
        
        # Валидация email
        if email:
            import re
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not re.match(email_pattern, email):
                errors.append('Неверный формат email адреса')
        
        # Валидация имени пользователя
        if username:
            if len(username) < 2:
                errors.append('Имя пользователя должно содержать минимум 2 символа')
            if len(username) > 50:
                errors.append('Имя пользователя не должно превышать 50 символов')
        
        # Валидация пароля
        if password:
            if len(password) < 6:
                errors.append('Пароль должен содержать минимум 6 символов')
            if len(password) > 128:
                errors.append('Пароль не должен превышать 128 символов')
        
        # Проверка совпадения паролей
        if password and password_confirm and password != password_confirm:
            errors.append('Пароли не совпадают')
        
        # Проверка существования пользователя
        if email and not errors:  # Проверяем только если email валиден
            existing_user = User.get_by_email(email)
            if existing_user:
                errors.append('Пользователь с таким email уже зарегистрирован')
        
        # Если есть ошибки, показываем их
        if errors:
            for error in errors:
                flash(error, 'danger')
            return render_template('auth/register.html')
        
        # Создаем пользователя
        try:
            user = User.create(email, username, password)
            if user:
                login_user(user)
                logger.info(f"New user registered and logged in: {email}")
                flash('Добро пожаловать! Регистрация прошла успешно', 'success')
                return redirect(url_for('dashboard'))
            else:
                flash('Ошибка при создании аккаунта. Попробуйте еще раз', 'danger')
        except Exception as e:
            logger.error(f"Error creating user {email}: {str(e)}")
            flash('Произошла ошибка при регистрации. Попробуйте позже', 'danger')
    
    return render_template('auth/register.html')

@app.route('/logout')
@login_required
def logout():
    """Выход из системы"""
    logger.info(f"User logged out: {current_user.email}")
    logout_user()
    flash('Вы успешно вышли из системы', 'info')
    return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
def dashboard():
    """Личный кабинет пользователя"""
    page = request.args.get('page', 1, type=int)
    per_page = 10
    
    # Получаем статистику пользователя
    conn = sqlite3.connect('ai_study.db')
    c = conn.cursor()
    
    # Общая статистика
    c.execute('SELECT COUNT(*) FROM result WHERE user_id = ?', (current_user.id,))
    total_results = c.fetchone()[0]
    
    c.execute('''
        SELECT COUNT(*) FROM user_progress 
        WHERE user_id = ? AND consecutive_correct >= 3
    ''', (current_user.id,))
    mastered_cards = c.fetchone()[0]
    
    c.execute('SELECT COUNT(*) FROM user_progress WHERE user_id = ?', (current_user.id,))
    total_progress = c.fetchone()[0]
    
    # Карточки для повторения сегодня
    c.execute('''
        SELECT COUNT(*) FROM user_progress 
        WHERE user_id = ? AND date(next_review) <= date('now')
    ''', (current_user.id,))
    cards_due_today = c.fetchone()[0]
    
    # Все результаты с пагинацией
    offset = (page - 1) * per_page
    c.execute('''
        SELECT id, filename, file_type, created_at, access_token
        FROM result 
        WHERE user_id = ?
        ORDER BY created_at DESC
        LIMIT ? OFFSET ?
    ''', (current_user.id, per_page, offset))
    
    all_results = []
    for row in c.fetchall():
        all_results.append({
            'id': row[0],
            'filename': row[1],
            'file_type': row[2],
            'created_at': row[3],
            'access_token': row[4]
        })
    
    conn.close()
    
    # Простая пагинация
    has_prev = page > 1
    has_next = offset + per_page < total_results
    prev_num = page - 1 if has_prev else None
    next_num = page + 1 if has_next else None
    
    pagination = {
        'page': page,
        'per_page': per_page,
        'total': total_results,
        'has_prev': has_prev,
        'has_next': has_next,
        'prev_num': prev_num,
        'next_num': next_num
    }
    
    stats = {
        'total_results': total_results,
        'mastered_cards': mastered_cards,
        'total_progress': total_progress,
        'cards_due_today': cards_due_today
    }
    
    # Получаем персональную статистику обучения
    learning_stats = get_user_learning_stats(current_user.id)
    
    # Получаем информацию о подписке
    user_subscription = subscription_manager.get_user_subscription(current_user.id)
    usage_stats = subscription_manager.get_usage_stats(current_user.id)
    
    return render_template('dashboard.html', 
                         stats=stats, 
                         all_results=all_results, 
                         pagination=pagination, 
                         learning_stats=learning_stats,
                         user_subscription=user_subscription,
                         usage_stats=usage_stats)

@app.route('/profile')
@login_required
def profile():
    """Профиль пользователя"""
    return render_template('profile.html', datetime=datetime)

@app.route('/profile/update', methods=['POST'])
@login_required
def update_profile():
    """Обновление профиля пользователя"""
    username = request.form.get('username', '').strip()
    current_password = request.form.get('current_password', '')
    new_password = request.form.get('new_password', '')
    new_password_confirm = request.form.get('new_password_confirm', '')
    
    conn = sqlite3.connect('ai_study.db')
    c = conn.cursor()
    
    # Обновляем имя пользователя
    if username and username != current_user.username:
        c.execute('UPDATE users SET username = ? WHERE id = ?', 
                 (username, current_user.id))
        flash('Имя пользователя обновлено', 'success')
    
    # Обновляем пароль
    if new_password:
        if not current_password:
            flash('Введите текущий пароль', 'danger')
            conn.close()
            return redirect(url_for('profile'))
        
        if not current_user.check_password(current_password):
            flash('Неверный текущий пароль', 'danger')
            conn.close()
            return redirect(url_for('profile'))
        
        if new_password != new_password_confirm:
            flash('Новые пароли не совпадают', 'danger')
            conn.close()
            return redirect(url_for('profile'))
        
        if len(new_password) < 6:
            flash('Новый пароль должен содержать минимум 6 символов', 'danger')
            conn.close()
            return redirect(url_for('profile'))
        
        new_password_hash = generate_password_hash(new_password)
        c.execute('UPDATE users SET password_hash = ? WHERE id = ?', 
                 (new_password_hash, current_user.id))
        flash('Пароль успешно изменен', 'success')
    
    conn.commit()
    conn.close()
    
    return redirect(url_for('profile'))

@app.route('/my-results')
@login_required
def my_results():
    """Мои результаты"""
    page = request.args.get('page', 1, type=int)
    file_filter = request.args.get('filter', '')
    per_page = 10
    
    conn = sqlite3.connect('ai_study.db')
    c = conn.cursor()
    
    # Строим SQL запрос с учетом фильтра
    base_where = 'WHERE user_id = ?'
    params = [current_user.id]
    
    if file_filter:
        if file_filter == 'pdf':
            base_where += ' AND file_type = ?'
            params.append('.pdf')
        elif file_filter == 'pptx':
            base_where += ' AND file_type = ?'
            params.append('.pptx')
        elif file_filter == 'video':
            base_where += ' AND file_type IN (?, ?, ?)'
            params.extend(['.mp4', '.mov', '.mkv'])
    
    # Получаем общее количество результатов с учетом фильтра
    c.execute(f'SELECT COUNT(*) FROM result {base_where}', params)
    total = c.fetchone()[0]
    
    # Получаем результаты с пагинацией и фильтрацией
    offset = (page - 1) * per_page
    c.execute(f'''
        SELECT id, filename, file_type, created_at, access_token
        FROM result 
        {base_where}
        ORDER BY created_at DESC
        LIMIT ? OFFSET ?
    ''', params + [per_page, offset])
    
    results = []
    for row in c.fetchall():
        results.append({
            'id': row[0],
            'filename': row[1],
            'file_type': row[2],
            'created_at': row[3],
            'access_token': row[4]
        })
    
    conn.close()
    
    # Простая пагинация
    has_prev = page > 1
    has_next = offset + per_page < total
    prev_num = page - 1 if has_prev else None
    next_num = page + 1 if has_next else None
    
    pagination = {
        'page': page,
        'per_page': per_page,
        'total': total,
        'has_prev': has_prev,
        'has_next': has_next,
        'prev_num': prev_num,
        'next_num': next_num
    }
    
    return render_template('my_results.html', results=results, pagination=pagination)

def extract_questions_from_broken_json(json_text):
    """Извлекает вопросы из поврежденного JSON с помощью регулярных выражений"""
    import re
    
    logger.info("Пытаемся извлечь вопросы из поврежденного JSON...")
    
    questions = []
    
    try:
        # Улучшенный паттерн для поиска вопросов
        # Ищем блоки, которые содержат все необходимые поля
        question_blocks = re.findall(
            r'\{[^}]*?"id":\s*(\d+)[^}]*?"question":\s*"([^"]+)"[^}]*?"options":\s*\{([^}]+)\}[^}]*?"correct_answer":\s*"([^"]+)"[^}]*?"explanation":\s*"([^"]+)"[^}]*?\}',
            json_text,
            re.DOTALL
        )
        
        for i, (question_id, question_text, options_str, correct_answer, explanation) in enumerate(question_blocks[:10]):
            # Парсим опции
            options = {}
            option_pattern = r'"([A-D])":\s*"([^"]+)"'
            option_matches = re.findall(option_pattern, options_str)
            
            for opt_key, opt_value in option_matches:
                # Очищаем значение опции от лишних символов
                clean_value = re.sub(r'[\\n\\r\\t]', ' ', opt_value).strip()
                options[opt_key] = clean_value
            
            # Проверяем, что у нас есть все 4 опции
            if len(options) == 4 and correct_answer in options:
                questions.append({
                    "id": int(question_id) if question_id.isdigit() else i + 1,
                    "question": question_text.strip(),
                    "options": options,
                    "correct_answer": correct_answer,
                    "explanation": explanation.strip(),
                    "difficulty": 1 + (i % 3),  # Распределяем сложность 1-3
                    "topic": "Материал"
                })
        
        # Если не нашли полные блоки, пробуем более простой подход
        if not questions:
            logger.info("Пробуем альтернативный метод извлечения...")
            
            # Ищем отдельные компоненты
            question_texts = re.findall(r'"question":\s*"([^"]+)"', json_text)
            correct_answers = re.findall(r'"correct_answer":\s*"([A-D])"', json_text)
            explanations = re.findall(r'"explanation":\s*"([^"]+)"', json_text)
            
            # Ищем блоки опций
            options_blocks = re.findall(r'"options":\s*\{([^}]+)\}', json_text)
            
            min_length = min(len(question_texts), len(correct_answers), len(explanations), len(options_blocks))
            
            for i in range(min(min_length, 5)):  # Максимум 5 вопросов
                # Парсим опции для этого вопроса
                options = {}
                option_matches = re.findall(r'"([A-D])":\s*"([^"]+)"', options_blocks[i])
                
                for opt_key, opt_value in option_matches:
                    options[opt_key] = opt_value.strip()
                
                if len(options) == 4:
                    questions.append({
                        "id": i + 1,
                        "question": question_texts[i].strip(),
                        "options": options,
                        "correct_answer": correct_answers[i],
                        "explanation": explanations[i].strip(),
                        "difficulty": 1 + (i % 3),
                        "topic": "Материал"
                    })
        
        logger.info(f"Извлечено {len(questions)} вопросов из поврежденного JSON")
        return questions
        
    except Exception as e:
        logger.error(f"Ошибка при извлечении вопросов: {e}")
        return []

def fix_json_syntax(json_text):
    """Улучшенное исправление синтаксических ошибок JSON"""
    import re
    
    logger.info("Пытаемся исправить JSON синтаксис...")
    
    # Сохраняем оригинал для отладки
    original_length = len(json_text)
    
    # 1. Исправляем отсутствующие запятые между объектами в массиве
    json_text = re.sub(r'}\s*\n\s*{', '},\n{', json_text)
    
    # 2. Исправляем отсутствующие запятые после строковых значений
    json_text = re.sub(r'"\s*\n\s*"([a-zA-Z_]+)":', '",\n"\\1":', json_text)
    
    # 3. Исправляем отсутствующие запятые после чисел
    json_text = re.sub(r'(\d)\s*\n\s*"([a-zA-Z_]+)":', r'\1,\n"\2":', json_text)
    
    # 4. Исправляем отсутствующие запятые после закрывающих скобок объектов
    json_text = re.sub(r'}\s*\n\s*"([a-zA-Z_]+)":', r'},\n"\1":', json_text)
    
    # 5. Исправляем отсутствующие запятые после закрывающих скобок массивов
    json_text = re.sub(r']\s*\n\s*"([a-zA-Z_]+)":', r'],\n"\1":', json_text)
    
    # 6. Убираем лишние запятые перед закрывающими скобками
    json_text = re.sub(r',\s*}', '}', json_text)
    json_text = re.sub(r',\s*]', ']', json_text)
    
    # 7. Исправляем неэкранированные кавычки в строках
    # Ищем строки с неэкранированными кавычками и экранируем их
    def fix_quotes_in_strings(match):
        content = match.group(1)
        # Экранируем кавычки внутри строки, но не те что уже экранированы
        fixed_content = re.sub(r'(?<!\\)"', '\\"', content)
        return f'"{fixed_content}"'
    
    # Применяем исправление кавычек к значениям строк
    json_text = re.sub(r'"([^"]*(?:\\.[^"]*)*)"(?=\s*[,}:\]])', fix_quotes_in_strings, json_text)
    
    # 8. Убираем возможные дублирующиеся запятые
    json_text = re.sub(r',+', ',', json_text)
    
    # 9. Исправляем пробелы вокруг двоеточий и запятых
    json_text = re.sub(r'\s*:\s*', ': ', json_text)
    json_text = re.sub(r'\s*,\s*', ', ', json_text)
    
    logger.info(f"JSON исправлен: {original_length} → {len(json_text)} символов")
    
    return json_text

def generate_test_questions(result_data):
    """Генерирует тестовые вопросы с вариантами ответов на основе материала"""
    try:
        from openai import OpenAI
        client = OpenAI(api_key=os.environ.get('OPENAI_API_KEY'))
        
        # Получаем текст материала
        full_text = result_data.get('full_text', '')
        summary = result_data.get('summary', '')
        topics_data = result_data.get('topics_data', {})
        
        # Формируем расширенный контекст для генерации вопросов
        # Берем больше текста для лучшего понимания материала
        text_sample = full_text[:5000] if len(full_text) > 5000 else full_text
        
        # Извлекаем ключевые темы и подтемы
        main_topics = []
        if isinstance(topics_data, dict):
            for topic, details in topics_data.items():
                if isinstance(details, dict) and 'subtopics' in details:
                    subtopics = details['subtopics'][:3]  # Берем первые 3 подтемы
                    main_topics.append(f"{topic}: {', '.join(subtopics)}")
                else:
                    main_topics.append(str(topic))
        
        context = f"""
        НАЗВАНИЕ МАТЕРИАЛА: {result_data.get('filename', 'Учебный материал')}
        
        КРАТКОЕ РЕЗЮМЕ:
        {summary}
        
        ОСНОВНЫЕ ТЕМЫ И ПОДТЕМЫ:
        {chr(10).join(main_topics) if main_topics else 'Темы не определены'}
        
        ФРАГМЕНТ ПОЛНОГО ТЕКСТА (для понимания стиля и деталей):
        {text_sample}
        {'...' if len(full_text) > 5000 else ''}
        
        ДОПОЛНИТЕЛЬНАЯ ИНФОРМАЦИЯ:
        - Общий объем материала: {len(full_text)} символов
        - Количество основных тем: {len(main_topics)}
        """
        
        prompt = f"""
        На основе КОНКРЕТНОГО предоставленного учебного материала создай 25 тестовых вопросов разной сложности.
        
        ВАЖНО: Вопросы должны быть СТРОГО основаны на содержании данного материала, а не на общих знаниях по теме.
        
        Материал:
        {context}
        
        Требования к вопросам:
        1. 8 легких вопросов (конкретные определения и факты из материала)
        2. 12 средних вопросов (понимание концепций, формул, алгоритмов из материала)
        3. 5 сложных вопросов (анализ примеров, применение методов из материала)
        
        ОБЯЗАТЕЛЬНЫЕ требования:
        - Вопросы должны проверять знание ИМЕННО этого материала
        - Используй конкретные термины, формулы, примеры из текста
        - НЕ задавай общие вопросы по теме, которые можно ответить без чтения материала
        - Включай специфические детали, числа, названия из материала
        - Ссылайся на конкретные разделы, примеры, диаграммы из текста
        
        Каждый вопрос должен иметь:
        - Четкую формулировку на русском языке, основанную на материале
        - 4 варианта ответа (A, B, C, D) - все правдоподобные для данной темы
        - Только один правильный ответ из материала
        - Подробное объяснение со ссылкой на материал
        - Неправильные варианты должны быть близкими по теме, но четко неверными
        
        Примеры хороших вопросов:
        - "Согласно материалу, какая формула используется для расчета..."
        - "В приведенном примере автор демонстрирует..."
        - "Какой метод рекомендуется в материале для решения..."
        - "Согласно тексту, основное отличие между X и Y заключается в..."
        
        Верни результат в формате JSON:
        {{
            "questions": [
                {{
                    "id": 1,
                    "question": "Конкретный вопрос по материалу",
                    "options": {{
                        "A": "Вариант A из материала",
                        "B": "Вариант B из материала", 
                        "C": "Вариант C из материала",
                        "D": "Вариант D из материала"
                    }},
                    "correct_answer": "A",
                    "explanation": "Объяснение со ссылкой на конкретное место в материале",
                    "difficulty": 1,
                    "topic": "Конкретная тема из материала"
                }}
            ]
        }}
        
        Сложность: 1 = легко, 2 = средне, 3 = сложно
        """
        
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Ты эксперт по созданию образовательных тестов, специализирующийся на создании вопросов строго по содержанию конкретного учебного материала. Твоя задача - создавать вопросы, которые можно ответить ТОЛЬКО прочитав данный материал, а не на основе общих знаний по теме. Фокусируйся на специфических деталях, примерах, формулах и концепциях из предоставленного текста."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,  # Снижаем температуру для более точных вопросов
            max_tokens=4000
        )
        
        # Парсим ответ
        response_text = response.choices[0].message.content
        logger.info(f"Получен ответ от GPT длиной {len(response_text)} символов")
        
        # Извлекаем JSON из ответа
        import re
        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        if json_match:
            json_text = json_match.group()
            logger.info(f"Извлечен JSON длиной {len(json_text)} символов")
            
            try:
                questions_data = json.loads(json_text)
                questions = questions_data.get('questions', [])
                logger.info(f"JSON успешно распарсен, найдено {len(questions)} вопросов")
                return questions
            except json.JSONDecodeError as e:
                logger.error(f"Ошибка парсинга JSON: {e}")
                logger.info("Пытаемся исправить JSON...")
                
                # Улучшенное исправление JSON
                try:
                    fixed_json = fix_json_syntax(json_text)
                    questions_data = json.loads(fixed_json)
                    questions = questions_data.get('questions', [])
                    logger.info(f"JSON успешно исправлен, найдено {len(questions)} вопросов")
                    return questions
                except json.JSONDecodeError as e2:
                    logger.error(f"Не удалось исправить JSON: {e2}")
                    # Попробуем извлечь отдельные вопросы с улучшенным парсингом
                    questions = extract_questions_from_broken_json(json_text)
                    if questions:
                        logger.info(f"Извлечено {len(questions)} вопросов из поврежденного JSON")
                        return questions
                    
                    logger.error("Используем демонстрационные вопросы")
                    return get_demo_questions()
        else:
            logger.error("Не удалось извлечь JSON из ответа GPT")
            return get_demo_questions()
            
    except Exception as e:
        logger.error(f"Ошибка генерации тестовых вопросов: {str(e)}")
        # Возвращаем демонстрационные вопросы в случае ошибки
        return get_demo_questions()

def get_demo_questions():
    """Возвращает демонстрационные вопросы для тестирования"""
    return [
        {
            "id": 1,
            "question": "Что такое машинное обучение?",
            "options": {
                "A": "Способность машин физически обучаться новым движениям",
                "B": "Раздел ИИ, позволяющий компьютерам обучаться на данных",
                "C": "Процесс обучения людей работе с машинами",
                "D": "Автоматическое обновление программного обеспечения"
            },
            "correct_answer": "B",
            "explanation": "Машинное обучение — это раздел искусственного интеллекта, который позволяет компьютерам обучаться и принимать решения на основе данных без явного программирования.",
            "difficulty": 1,
            "topic": "Основы ML"
        },
        {
            "id": 2,
            "question": "Какие основные типы машинного обучения существуют?",
            "options": {
                "A": "Быстрое, медленное и среднее обучение",
                "B": "Обучение с учителем, без учителя и с подкреплением",
                "C": "Линейное, нелинейное и циклическое обучение",
                "D": "Простое, сложное и экспертное обучение"
            },
            "correct_answer": "B",
            "explanation": "Основные типы: supervised learning (с учителем), unsupervised learning (без учителя) и reinforcement learning (с подкреплением).",
            "difficulty": 2,
            "topic": "Типы обучения"
        },
        {
            "id": 3,
            "question": "Что происходит при переобучении модели?",
            "options": {
                "A": "Модель работает слишком быстро",
                "B": "Модель потребляет много памяти",
                "C": "Модель слишком хорошо запоминает обучающие данные",
                "D": "Модель обучается дольше обычного"
            },
            "correct_answer": "C",
            "explanation": "При переобучении модель слишком хорошо запоминает обучающие данные, включая шум, что ухудшает её работу на новых данных.",
            "difficulty": 2,
            "topic": "Проблемы обучения"
        },
        {
            "id": 4,
            "question": "Что такое нейронная сеть?",
            "options": {
                "A": "Сеть компьютеров для обработки данных",
                "B": "Математическая модель, имитирующая работу нейронов мозга",
                "C": "Программа для создания графиков",
                "D": "База данных для хранения информации"
            },
            "correct_answer": "B",
            "explanation": "Нейронная сеть — это математическая модель, построенная по принципу организации и функционирования биологических нейронных сетей.",
            "difficulty": 1,
            "topic": "Нейронные сети"
        },
        {
            "id": 5,
            "question": "Что такое градиентный спуск?",
            "options": {
                "A": "Метод физических упражнений",
                "B": "Алгоритм оптимизации для минимизации функции потерь",
                "C": "Способ сжатия данных",
                "D": "Техника визуализации данных"
            },
            "correct_answer": "B",
            "explanation": "Градиентный спуск — это итерационный алгоритм оптимизации, используемый для минимизации функции потерь путем движения в направлении наибольшего убывания градиента.",
            "difficulty": 2,
            "topic": "Оптимизация"
        },
        {
            "id": 6,
            "question": "Что означает термин 'Big Data'?",
            "options": {
                "A": "Большие файлы на компьютере",
                "B": "Наборы данных большого объема, скорости и разнообразия",
                "C": "Дорогое программное обеспечение",
                "D": "Быстрый интернет"
            },
            "correct_answer": "B",
            "explanation": "Big Data характеризуется тремя V: Volume (объем), Velocity (скорость) и Variety (разнообразие) данных, которые сложно обрабатывать традиционными методами.",
            "difficulty": 1,
            "topic": "Big Data"
        },
        {
            "id": 7,
            "question": "Что такое кросс-валидация?",
            "options": {
                "A": "Проверка правописания в коде",
                "B": "Метод оценки качества модели на разных подвыборках данных",
                "C": "Способ шифрования данных",
                "D": "Техника сжатия изображений"
            },
            "correct_answer": "B",
            "explanation": "Кросс-валидация — это метод оценки обобщающей способности модели путем разделения данных на несколько частей и тестирования модели на каждой из них.",
            "difficulty": 2,
            "topic": "Валидация модели"
        },
        {
            "id": 8,
            "question": "Что такое признак (feature) в машинном обучении?",
            "options": {
                "A": "Ошибка в программе",
                "B": "Индивидуальная измеримая характеристика объекта",
                "C": "Тип алгоритма",
                "D": "Результат работы модели"
            },
            "correct_answer": "B",
            "explanation": "Признак — это индивидуальная измеримая характеристика или свойство наблюдаемого объекта, используемая в качестве входных данных для модели.",
            "difficulty": 1,
            "topic": "Признаки"
        }
    ]

@app.route('/test/<int:result_id>')
def test_mode(result_id):
    """Режим тестирования с предварительно сгенерированными вопросами"""
    result_data = get_result(result_id, check_access=True)
    if not result_data:
        flash('Результат не найден или нет доступа', 'danger')
        return redirect(url_for('index'))
    
    # Получаем предварительно сгенерированные тестовые вопросы
    test_questions = result_data.get('test_questions', [])
    
    # Если вопросов нет, генерируем их сейчас (для старых результатов)
    if not test_questions:
        logger.info("Тестовые вопросы не найдены, генерируем...")
        test_questions = generate_test_questions(result_data)
        
        if test_questions:
            # Сохраняем сгенерированные вопросы в базу данных
            conn = sqlite3.connect('ai_study.db')
            c = conn.cursor()
            test_questions_json = json.dumps(test_questions, ensure_ascii=False)
            c.execute('UPDATE result SET test_questions_json = ? WHERE id = ?', 
                     (test_questions_json, result_id))
            conn.commit()
            conn.close()
            logger.info(f"Сохранено {len(test_questions)} тестовых вопросов")
        else:
            flash('Не удалось сгенерировать тестовые вопросы', 'warning')
            return redirect(url_for('result', result_id=result_id))
    
    # Получаем прогресс пользователя
    conn = sqlite3.connect('ai_study.db')
    c = conn.cursor()
    
    progress_data = {}
    if current_user.is_authenticated:
        c.execute('''
            SELECT flashcard_id, consecutive_correct, ease_factor, next_review
            FROM user_progress 
            WHERE result_id = ? AND user_id = ?
        ''', (result_id, current_user.id))
        
        for row in c.fetchall():
            progress_data[row[0]] = {
                'consecutive_correct': row[1],
                'ease_factor': row[2],
                'next_review': row[3]
            }
    
    conn.close()
    
    # Добавляем прогресс к вопросам
    for i, question in enumerate(test_questions):
        question['id'] = i
        if i in progress_data:
            question['progress'] = progress_data[i]
        else:
            question['progress'] = {
                'consecutive_correct': 0,
                'ease_factor': 2.5,
                'next_review': None
            }
    
    return render_template('test_mode.html', 
                         result_data=result_data, 
                         test_questions=test_questions,
                         result_id=result_id,
                         access_token=result_data.get('access_token'))

@app.route('/test/<int:result_id>/answer', methods=['POST'])
def submit_test_answer(result_id):
    """Обработка ответа в режиме теста"""
    if not current_user.is_authenticated:
        return jsonify({'error': 'Необходима авторизация'}), 401
    
    data = request.get_json()
    flashcard_id = data.get('flashcard_id')
    is_correct = data.get('is_correct', False)
    
    if flashcard_id is None:
        return jsonify({'error': 'Не указан ID карточки'}), 400
    
    # Обновляем прогресс пользователя
    conn = sqlite3.connect('ai_study.db')
    c = conn.cursor()
    
    # Получаем текущий прогресс
    c.execute('''
        SELECT consecutive_correct, ease_factor, next_review
        FROM user_progress 
        WHERE result_id = ? AND flashcard_id = ? AND user_id = ?
    ''', (result_id, flashcard_id, current_user.id))
    
    row = c.fetchone()
    
    if row:
        consecutive_correct, ease_factor, next_review = row
    else:
        consecutive_correct = 0
        ease_factor = 2.5
        next_review = None
    
    # Алгоритм интервального повторения (упрощенный SM-2)
    if is_correct:
        consecutive_correct += 1
        if consecutive_correct == 1:
            interval = 1  # 1 день
        elif consecutive_correct == 2:
            interval = 6  # 6 дней
        else:
            interval = int((consecutive_correct - 1) * ease_factor)
        
        # Корректируем ease_factor
        ease_factor = max(1.3, ease_factor + (0.1 - (5 - 4) * (0.08 + (5 - 4) * 0.02)))
    else:
        consecutive_correct = 0
        interval = 1
        ease_factor = max(1.3, ease_factor - 0.2)
    
    # Вычисляем следующую дату повторения
    next_review_date = datetime.now() + timedelta(days=interval)
    
    # Сохраняем или обновляем прогресс
    c.execute('''
        INSERT OR REPLACE INTO user_progress 
        (result_id, flashcard_id, user_id, last_review, next_review, ease_factor, consecutive_correct)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (result_id, flashcard_id, current_user.id, datetime.now(), 
          next_review_date, ease_factor, consecutive_correct))
    
    conn.commit()
    conn.close()
    
    return jsonify({
        'success': True,
        'consecutive_correct': consecutive_correct,
        'next_review': next_review_date.strftime('%Y-%m-%d'),
        'ease_factor': round(ease_factor, 2)
    })

@app.route('/test/<int:result_id>/stats')
def test_stats(result_id):
    """Статистика тестирования"""
    if not current_user.is_authenticated:
        return jsonify({'error': 'Необходима авторизация'}), 401
    
    conn = sqlite3.connect('ai_study.db')
    c = conn.cursor()
    
    # Общая статистика по результату
    c.execute('''
        SELECT 
            COUNT(*) as total_cards,
            SUM(CASE WHEN consecutive_correct >= 3 THEN 1 ELSE 0 END) as mastered_cards,
            AVG(consecutive_correct) as avg_correct,
            AVG(ease_factor) as avg_ease
        FROM user_progress 
        WHERE result_id = ? AND user_id = ?
    ''', (result_id, current_user.id))
    
    stats = c.fetchone()
    conn.close()
    
    if stats and stats[0] > 0:
        return jsonify({
            'total_cards': stats[0],
            'mastered_cards': stats[1] or 0,
            'mastery_percentage': round((stats[1] or 0) / stats[0] * 100, 1),
            'avg_correct': round(stats[2] or 0, 1),
            'avg_ease': round(stats[3] or 2.5, 2)
        })
    else:
        return jsonify({
            'total_cards': 0,
            'mastered_cards': 0,
            'mastery_percentage': 0,
            'avg_correct': 0,
            'avg_ease': 2.5
        })

@app.route('/')
def index():
    """Главная страница"""
    user_subscription = None
    usage_stats = None
    
    if current_user.is_authenticated:
        user_subscription = subscription_manager.get_user_subscription(current_user.id)
        usage_stats = subscription_manager.get_usage_stats(current_user.id)
    
    return render_template('index.html', 
                         user_subscription=user_subscription,
                         usage_stats=usage_stats)



@app.route('/upload', methods=['POST'])
@login_required
@require_subscription_limit('analysis')
@track_usage('analysis')
def upload_file():
    """Загрузка и обработка файла"""
    try:
        # Проверка загружен ли файл
        if 'file' not in request.files:
            flash('Выберите файл', 'danger')
            return redirect(url_for('index'))
        
        file = request.files['file']
        
        # Проверка пустой ли файл
        if file.filename == '':
            flash('Выберите файл', 'danger')
            return redirect(url_for('index'))
        
        # Проверка формата файла
        if not allowed_file(file.filename):
            flash('Формат не поддерживается. Используйте PDF, PPTX, MP4, MOV или MKV', 'danger')
            return redirect(url_for('index'))
        
        # Сохранение файла
        original_filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Отладочная информация
        logger.info(f"Original filename: {file.filename}")
        logger.info(f"Secure filename: {original_filename}")
        
        # Сохраняем оригинальное расширение файла
        file_ext = Path(original_filename).suffix.lower()
        filename_without_ext = Path(original_filename).stem
        
        # Дополнительная проверка расширения
        if not file_ext:
            # Если расширение потерялось, попробуем извлечь из оригинального имени
            original_ext = Path(file.filename).suffix.lower()
            if original_ext:
                file_ext = original_ext
                logger.warning(f"Extension recovered from original filename: {file_ext}")
            else:
                logger.error(f"No file extension found in: {file.filename}")
                flash('Ошибка: не удалось определить тип файла', 'danger')
                return redirect(url_for('index'))
        
        filename = f"{timestamp}_{filename_without_ext}{file_ext}"
        
        logger.info(f"File extension: {file_ext}")
        logger.info(f"Final filename: {filename}")
        
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        logger.info(f"File uploaded: {filename}")
        
        # Получение диапазона страниц/слайдов (для PDF и PPTX)
        page_range = None
        file_type = Path(filename).suffix.lower()
        if file_type in ['.pdf', '.pptx']:
            page_range = request.form.get('page_range', '').strip()
            if not page_range:
                page_range = '1-20'  # По умолчанию
            if file_type == '.pdf':
                logger.info(f"PDF page range specified: {page_range}")
                # Проверка лимита страниц PDF
                try:
                    if '-' in page_range:
                        start, end = map(int, page_range.split('-'))
                        pages_count = end - start + 1
                    else:
                        pages_count = len(page_range.split(','))
                    
                    allowed, message = subscription_manager.check_pdf_pages_limit(current_user.id, pages_count)
                    if not allowed:
                        flash(message, 'error')
                        os.remove(filepath)
                        return redirect(url_for('index'))
                    
                    # Записываем использование страниц PDF
                    subscription_manager.record_usage(current_user.id, 'pdf_pages', pages_count, filename)
                    
                except ValueError:
                    flash('Неверный формат диапазона страниц', 'error')
                    os.remove(filepath)
                    return redirect(url_for('index'))
            else:
                logger.info(f"PowerPoint slide range specified: {page_range}")
        
        # Обработка файла
        try:
            from ml import process_file
            analysis_result = process_file(filepath, filename, page_range=page_range)
            
            # Подготовка информации о страницах/слайдах
            page_info = None
            if file_type in ['.pdf', '.pptx'] and page_range:
                page_info = {
                    'page_range': page_range,
                    'processed_at': datetime.now().isoformat(),
                    'file_type': file_type
                }
            
            # Сохранение результата в БД
            access_token = save_result(filename, file_type, analysis_result, page_info)
            
            # Начисление XP за анализ документа
            if current_user.is_authenticated:
                xp_result = gamification.award_xp(
                    current_user.id, 
                    'document_analysis', 
                    f'Анализ {file_type.upper()} файла: {filename}',
                    {'file_type': file_type, 'filename': filename}
                )
                
                # Обновляем ежедневную серию
                streak_result = gamification.update_daily_streak(current_user.id)
                
                # Если есть повышение уровня или новые достижения, добавляем в flash сообщения
                if xp_result.get('level_up'):
                    flash(f'🎉 Поздравляем! Вы достигли уровня {xp_result["new_level"]}: {xp_result["new_level_title"]}!', 'success')
                
                for achievement in xp_result.get('new_achievements', []):
                    flash(f'🏆 Новое достижение: {achievement["title"]}! +{achievement["xp_reward"]} XP', 'success')
            
            # Удаление файла
            os.remove(filepath)
            
            logger.info(f"Advanced processing completed for: {filename}")
            
            return redirect(url_for('result', access_token=access_token))
            
        except Exception as e:
            logger.error(f"Error processing file {filename}: {str(e)}")
            # Удаление файла с ошибкой
            if os.path.exists(filepath):
                os.remove(filepath)
            flash('Ошибка обработки, попробуйте ещё раз', 'danger')
            return redirect(url_for('index'))
            
    except Exception as e:
        logger.error(f"Upload error: {str(e)}")
        flash('Ошибка загрузки файла', 'danger')
        return redirect(url_for('index'))

@app.route('/upload_url', methods=['POST'])
@login_required
@require_subscription_limit('analysis')
@track_usage('analysis')
def upload_video_url():
    """Загрузка и обработка видео по URL"""
    try:
        video_url = request.form.get('video_url', '').strip()
        
        if not video_url:
            flash('Введите ссылку на видео', 'danger')
            return redirect(url_for('index'))
        
        # Проверка валидности URL
        if not is_valid_video_url(video_url):
            flash('Неподдерживаемая платформа. Поддерживаются: YouTube, Vimeo, RuTube, VK, OK.ru и другие', 'danger')
            return redirect(url_for('index'))
        
        logger.info(f"🎥 Starting video download from URL: {video_url}")
        
        # Загрузка видео
        try:
            logger.info("📥 Downloading video...")
            filepath, filename, original_title = download_video_from_url(video_url, app.config['UPLOAD_FOLDER'])
            logger.info(f"✅ Video downloaded successfully: {filename} (Title: {original_title})")
            
            # Обработка видео
            try:
                logger.info("🧠 Starting video processing...")
                from ml import process_file
                
                logger.info("🎤 Beginning transcription and analysis...")
                
                # ВАЖНО: НЕ удаляем файл до завершения обработки
                analysis_result = process_file(filepath, filename)
                logger.info("✅ Video analysis completed successfully")
                
                # Добавляем информацию об источнике
                video_info = {
                    'source_url': video_url,
                    'original_title': original_title,
                    'downloaded_at': datetime.now().isoformat()
                }
                
                # Сохранение результата в БД
                logger.info("💾 Saving results to database...")
                access_token = save_result(filename, '.mp4', analysis_result, video_info)
                logger.info(f"✅ Results saved with token: {access_token}")
                
                # Начисление XP за анализ видео
                if current_user.is_authenticated:
                    video_duration = video_info.get('duration_minutes', 0) if video_info else 0
                    xp_result = gamification.award_xp(
                        current_user.id, 
                        'video_analysis', 
                        f'Анализ видео: {filename} ({video_duration:.1f} мин)',
                        {'filename': filename, 'duration': video_duration, 'source': 'url'}
                    )
                    
                    # Дополнительный XP за длинное видео
                    if video_duration > 30:
                        gamification.award_xp(
                            current_user.id,
                            'long_study_session',
                            f'Анализ длинного видео ({video_duration:.1f} мин)'
                        )
                    
                    # Обновляем ежедневную серию
                    streak_result = gamification.update_daily_streak(current_user.id)
                    
                    # Уведомления о достижениях
                    if xp_result.get('level_up'):
                        flash(f'🎉 Поздравляем! Вы достигли уровня {xp_result["new_level"]}: {xp_result["new_level_title"]}!', 'success')
                    
                    for achievement in xp_result.get('new_achievements', []):
                        flash(f'🏆 Новое достижение: {achievement["title"]}! +{achievement["xp_reward"]} XP', 'success')
                
                # Теперь можно безопасно удалить файл
                if os.path.exists(filepath):
                    os.remove(filepath)
                    logger.info(f"🗑️ Temporary file {filename} removed")
                
                logger.info(f"🎉 Video processing completed successfully for: {filename}")
                
                return redirect(url_for('result', access_token=access_token))
                
            except Exception as e:
                logger.error(f"❌ Error processing video {filename}: {str(e)}")
                logger.exception("Detailed processing error:")
                
                # Удаление файла с ошибкой
                if os.path.exists(filepath):
                    os.remove(filepath)
                    logger.info(f"🗑️ Cleaned up failed file: {filename}")
                
                # Более детальные сообщения об ошибках
                if "transcrib" in str(e).lower():
                    flash('Ошибка транскрипции видео. Возможно, видео не содержит речи или аудио повреждено', 'danger')
                elif "whisper" in str(e).lower():
                    flash('Ошибка модели распознавания речи. Попробуйте позже', 'danger')
                elif "openai" in str(e).lower():
                    flash('Ошибка анализа содержимого. Проверьте настройки API', 'danger')
                else:
                    flash('Ошибка обработки видео. Попробуйте другое видео или повторите позже', 'danger')
                
                return redirect(url_for('index'))
                
        except Exception as e:
            logger.error(f"❌ Error downloading video from {video_url}: {str(e)}")
            logger.exception("Detailed download error:")
            
            if "слишком длинное" in str(e):
                flash(str(e), 'danger')
            elif "Unsupported URL" in str(e) or "No video formats found" in str(e):
                flash('Не удалось загрузить видео с этой ссылки. Проверьте URL или попробуйте другое видео', 'danger')
            elif "HTTP Error 403" in str(e):
                flash('Доступ к видео ограничен. Попробуйте другое видео', 'danger')
            elif "HTTP Error 404" in str(e):
                flash('Видео не найдено. Проверьте ссылку', 'danger')
            elif "network" in str(e).lower() or "connection" in str(e).lower():
                flash('Проблемы с сетевым соединением. Попробуйте позже', 'danger')
            else:
                flash('Ошибка загрузки видео. Проверьте ссылку и попробуйте ещё раз', 'danger')
            return redirect(url_for('index'))
            
    except Exception as e:
        logger.error(f"❌ General URL upload error: {str(e)}")
        logger.exception("Detailed general error:")
        flash('Общая ошибка загрузки видео по ссылке', 'danger')
        return redirect(url_for('index'))

@app.route('/result/<access_token>')
def result(access_token):
    """Отображение результата по уникальному токену"""
    data = get_result_by_token(access_token)
    if not data:
        flash('Результат не найден или нет доступа', 'danger')
        return redirect(url_for('index'))
    
    return render_template('result.html', **data, result_id=data['id'], access_token=access_token)

@app.route('/api/create_flashcard', methods=['POST'])
def create_flashcard():
    """Создание новой флеш-карты"""
    try:
        data = request.json
        if not data:
            return jsonify({"success": False, "error": "No data provided"}), 400
            
        result_id = data.get('result_id')
        card_data = data.get('card')
        
        if not result_id or not card_data:
            return jsonify({"success": False, "error": "Missing required parameters"}), 400
            
        # Проверяем, что результат существует
        result = get_result(result_id)
        if not result:
            return jsonify({"success": False, "error": "Result not found"}), 404
            
        # Добавляем новую карту к существующим
        existing_flashcards = result['flashcards']
        new_card_id = len(existing_flashcards)
        
        # Добавляем ID к новой карте
        card_data['id'] = new_card_id
        existing_flashcards.append(card_data)
        
        # Обновляем результат в базе данных
        conn = sqlite3.connect('ai_study.db')
        c = conn.cursor()
        
        flashcards_json = json.dumps(existing_flashcards, ensure_ascii=False)
        
        c.execute('''
            UPDATE result 
            SET flashcards_json = ?
            WHERE id = ?
        ''', (flashcards_json, result_id))
        
        conn.commit()
        conn.close()
        
        logger.info(f"New flashcard created for result {result_id}, card ID: {new_card_id}")
        return jsonify({"success": True, "card_id": new_card_id})
        
    except Exception as e:
        logger.error(f"Error creating flashcard: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/flashcard_progress', methods=['POST'])
@login_required
def update_flashcard_progress():
    """Обновление прогресса изучения флеш-карт"""
    try:
        data = request.json
        if not data:
            return jsonify({"success": False, "error": "No data provided"}), 400
            
        result_id = data.get('result_id')
        flashcard_id = data.get('flashcard_id')
        correct = data.get('correct', False)
        confidence = data.get('confidence', 2)
        
        # Валидация входных данных
        if not result_id or flashcard_id is None:
            return jsonify({"success": False, "error": "Missing required parameters"}), 400
            
        logger.info(f"Updating flashcard progress: result_id={result_id}, flashcard_id={flashcard_id}, correct={correct}, confidence={confidence}")
        
        conn = sqlite3.connect('ai_study.db')
        c = conn.cursor()
        
        # Проверяем, что результат принадлежит текущему пользователю
        c.execute('SELECT user_id FROM result WHERE id = ?', (result_id,))
        result_owner = c.fetchone()
        if not result_owner or result_owner[0] != current_user.id:
            conn.close()
            return jsonify({"success": False, "error": "Access denied"}), 403
        
        # Проверка существования прогресса
        c.execute('''
            SELECT id, ease_factor, consecutive_correct 
            FROM user_progress 
            WHERE result_id = ? AND flashcard_id = ? AND user_id = ?
        ''', (result_id, flashcard_id, current_user.id))
        
        progress = c.fetchone()
        
        if progress:
            # Обновление существующего прогресса
            prog_id, ease_factor, consecutive = progress
            
            if correct:
                # Повышение сложности при правильном ответе с учетом уверенности
                confidence_multiplier = confidence / 2.0  # 1=0.5, 2=1.0, 3=1.5
                new_ease = min(2.5, ease_factor + (0.1 * confidence_multiplier))
                new_consecutive = consecutive + 1
                interval_days = max(1, int(new_consecutive * new_ease * confidence_multiplier))
            else:
                # Понижение сложности при неправильном ответе
                new_ease = max(1.3, ease_factor - 0.2)
                new_consecutive = 0
                interval_days = 1
            
            c.execute('''
                UPDATE user_progress 
                SET last_review = CURRENT_TIMESTAMP,
                    next_review = datetime('now', '+' || ? || ' days'),
                    ease_factor = ?,
                    consecutive_correct = ?
                WHERE id = ?
            ''', (interval_days, new_ease, new_consecutive, prog_id))
        else:
            # Создание новой истории прогресса
            if correct:
                interval_days = max(1, confidence)  # 1-3 дня в зависимости от уверенности
                consecutive = 1
            else:
                interval_days = 1
                consecutive = 0
                
            c.execute('''
                INSERT INTO user_progress 
                (result_id, flashcard_id, user_id, last_review, next_review, ease_factor, consecutive_correct)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP, datetime('now', '+' || ? || ' days'), 2.5, ?)
            ''', (result_id, flashcard_id, current_user.id, interval_days, consecutive))
        
        conn.commit()
        conn.close()
        
        logger.info(f"Flashcard progress updated successfully. Next review in {interval_days} days")
        return jsonify({"success": True, "next_review_days": interval_days})
        
    except Exception as e:
        logger.error(f"Error updating flashcard progress: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/download/<int:result_id>')
def download_flashcards_old(result_id):
    """Старая функция скачивания флеш-карт (оставлена для совместимости)"""
    data = get_result(result_id)
    if not data:
        flash('Результат не найден', 'danger')
        return redirect(url_for('index'))
    
    anki_cards = []
    for i, card in enumerate(data['flashcards']):
        anki_card = {
            "id": i + 1,
            "question": card['q'],
            "answer": card['a'],
            "tags": [card['type']] + card.get('related_topics', []),
            "hint": card.get('hint', ''),
            "memory_hook": card.get('memory_hook', ''),
            "common_mistakes": card.get('common_mistakes', ''),
            "difficulty": card.get('difficulty', 1)
        }
        anki_cards.append(anki_card)
    
    # Метадата
    export_data = {
        "deck_name": f"AI_Study_{data['filename']}",
        "created": datetime.now().isoformat(),
        "total_cards": len(anki_cards),
        "cards": anki_cards,
        "study_plan": data.get('study_plan', {}),
        "mind_map": data.get('mind_map', {})
    }
    
    # Создание JSON файла
    json_content = json.dumps(export_data, ensure_ascii=False, indent=2)
    
    temp_filename = f"ai_study_export_{result_id}.json"
    temp_path = os.path.join(app.config['UPLOAD_FOLDER'], temp_filename)
    
    with open(temp_path, 'w', encoding='utf-8') as f:
        f.write(json_content)
    
    def remove_file(response):
        try:
            os.remove(temp_path)
        except Exception:
            pass
        return response
    
    return send_file(
        temp_path,
        as_attachment=True,
        download_name=f"ai_study_{datetime.now().strftime('%Y%m%d')}.json",
        mimetype='application/json'
    )

@app.route('/api/mind_map/<int:result_id>')
def get_mind_map_data(result_id):
    """Получение Mind Map"""
    data = get_result(result_id)
    if not data:
        return jsonify({"error": "Not found"}), 404
    
    return jsonify(data.get('mind_map', {}))

@app.route('/api/study_progress/<int:result_id>')
def get_study_progress(result_id):
    """Получение прогресса пользователя"""
    try:
        conn = sqlite3.connect('ai_study.db')
        c = conn.cursor()
        
        # Получение прогресса флеш-карт
        c.execute('''
            SELECT flashcard_id, last_review, next_review, 
                   ease_factor, consecutive_correct
            FROM user_progress
            WHERE result_id = ?
        ''', (result_id,))
        
        progress_data = []
        for row in c.fetchall():
            progress_data.append({
                "flashcard_id": row[0],
                "last_review": row[1],
                "next_review": row[2],
                "ease_factor": row[3],
                "consecutive_correct": row[4]
            })
        
        # Подсчет прогресса
        total_cards = len(get_result(result_id)['flashcards'])
        reviewed_cards = len(progress_data)
        mastered_cards = sum(1 for p in progress_data if p['consecutive_correct'] >= 3)
        
        conn.close()
        
        return jsonify({
            "total_cards": total_cards,
            "reviewed_cards": reviewed_cards,
            "mastered_cards": mastered_cards,
            "progress_percentage": round((mastered_cards / total_cards * 100) if total_cards > 0 else 0, 1),
            "card_progress": progress_data
        })
        
    except Exception as e:
        logger.error(f"Error getting study progress: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/chat/<int:result_id>', methods=['POST'])
@login_required
def chat_with_lecture(result_id):
    """Чат с ChatGPT на основе загруженной лекции"""
    try:
        # Проверяем лимит AI чата ПЕРЕД обработкой
        allowed, message = subscription_manager.check_ai_chat_limit(current_user.id)
        if not allowed:
            return jsonify({
                "success": False, 
                "error": message, 
                "limit_exceeded": True,
                "upgrade_required": True
            }), 403
        
        data = request.json
        if not data:
            return jsonify({"success": False, "error": "No data provided"}), 400
            
        user_message = data.get('message', '').strip()
        if not user_message:
            return jsonify({"success": False, "error": "Message is required"}), 400
            
        # Получаем данные лекции с проверкой доступа
        result_data = get_result(result_id, check_access=True)
        if not result_data:
            return jsonify({"success": False, "error": "Lecture not found or access denied"}), 404
            
        full_text = result_data.get('full_text', '')
        if not full_text:
            return jsonify({"success": False, "error": "No lecture text available for chat"}), 400
            
        # Импортируем OpenAI клиент из ml.py
        from ml import get_chat_response
        
        # Получаем ответ от ChatGPT
        ai_response = get_chat_response(user_message, full_text, result_data)
        
        # Записываем использование AI чата ПОСЛЕ успешного получения ответа
        subscription_manager.record_usage(current_user.id, 'ai_chat', 1, f'chat_message_{result_id}')
        
        # Сохраняем в историю чата
        conn = sqlite3.connect('ai_study.db')
        c = conn.cursor()
        
        c.execute('''
            INSERT INTO chat_history (result_id, user_id, user_message, ai_response)
            VALUES (?, ?, ?, ?)
        ''', (result_id, current_user.id, user_message, ai_response))
        
        conn.commit()
        conn.close()
        
        # Начисление XP за AI чат
        if current_user.is_authenticated:
            gamification.award_xp(
                current_user.id,
                'ai_chat_message',
                f'Вопрос в AI чате: {user_message[:50]}...',
                {'result_id': result_id, 'message_length': len(user_message)}
            )
        
        logger.info(f"Chat message processed for result {result_id} by user {current_user.id}")
        return jsonify({
            "success": True, 
            "response": ai_response,
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error in chat: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/check_email', methods=['POST'])
def check_email():
    """Проверка существования email для AJAX запросов"""
    try:
        data = request.json
        if not data:
            return jsonify({"error": "No data provided"}), 400
            
        email = data.get('email', '').strip().lower()
        if not email:
            return jsonify({"error": "Email is required"}), 400
        
        # Простая валидация email
        import re
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, email):
            return jsonify({"exists": False, "valid": False, "message": "Неверный формат email"})
        
        # Проверяем существование пользователя
        user = User.get_by_email(email)
        if user:
            return jsonify({"exists": True, "valid": True, "message": "Пользователь с таким email уже существует"})
        else:
            return jsonify({"exists": False, "valid": True, "message": "Email доступен"})
            
    except Exception as e:
        logger.error(f"Error checking email: {str(e)}")
        return jsonify({"error": "Server error"}), 500

@app.route('/api/chat_history/<int:result_id>')
def get_chat_history(result_id):
    """Получение истории чата для лекции"""
    try:
        # Проверяем, что результат существует
        result_data = get_result(result_id)
        if not result_data:
            return jsonify({"error": "Lecture not found"}), 404
            
        conn = sqlite3.connect('ai_study.db')
        c = conn.cursor()
        
        c.execute('''
            SELECT user_message, ai_response, created_at
            FROM chat_history
            WHERE result_id = ?
            ORDER BY created_at ASC
        ''', (result_id,))
        
        history = []
        for row in c.fetchall():
            history.append({
                "user_message": row[0],
                "ai_response": row[1],
                "timestamp": row[2]
            })
        
        conn.close()
        
        return jsonify({
            "success": True,
            "history": history,
            "lecture_title": result_data.get('filename', 'Лекция')
        })
        
    except Exception as e:
        logger.error(f"Error getting chat history: {str(e)}")
        return jsonify({"error": str(e)}), 500

# API endpoints
@app.route('/api/check_email', methods=['POST'])
def api_check_email():
    """API для проверки доступности email"""
    try:
        data = request.get_json()
        email = data.get('email', '').strip().lower()
        
        if not email:
            return jsonify({'error': True, 'message': 'Email не указан'})
        
        # Валидация формата email
        import re
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, email):
            return jsonify({
                'valid': False,
                'message': 'Неверный формат email адреса'
            })
        
        # Проверка существования пользователя
        existing_user = User.get_by_email(email)
        if existing_user:
            return jsonify({
                'valid': True,
                'exists': True,
                'message': 'Пользователь с таким email уже зарегистрирован'
            })
        
        return jsonify({
            'valid': True,
            'exists': False,
            'message': 'Email доступен для регистрации'
        })
        
    except Exception as e:
        logger.error(f"Error checking email: {str(e)}")
        return jsonify({'error': True, 'message': 'Ошибка сервера'})

@app.route('/api/delete_result/<int:result_id>', methods=['DELETE'])
@login_required
def delete_result_api(result_id):
    """API для удаления результата"""
    try:
        # Проверяем права доступа
        result_data = get_result(result_id, check_access=True)
        if not result_data:
            return jsonify({'error': True, 'message': 'Результат не найден или нет доступа'})
        
        # Удаляем из базы данных
        conn = sqlite3.connect('ai_study.db')
        c = conn.cursor()
        
        # Удаляем связанные данные
        c.execute('DELETE FROM user_progress WHERE result_id = ?', (result_id,))
        c.execute('DELETE FROM chat_history WHERE result_id = ?', (result_id,))
        c.execute('DELETE FROM result WHERE id = ? AND user_id = ?', (result_id, current_user.id))
        
        conn.commit()
        conn.close()
        
        logger.info(f"Result {result_id} deleted by user {current_user.id}")
        return jsonify({'success': True, 'message': 'Результат успешно удален'})
        
    except Exception as e:
        logger.error(f"Error deleting result {result_id}: {str(e)}")
        return jsonify({'error': True, 'message': 'Ошибка при удалении'})

@app.route('/download_flashcards/<int:result_id>')
@login_required
def download_flashcards(result_id):
    """Скачивание флеш-карт в формате JSON"""
    try:
        result_data = get_result(result_id, check_access=True)
        if not result_data:
            flash('Результат не найден', 'danger')
            return redirect(url_for('my_results'))
        
        # Подготавливаем данные для скачивания
        export_data = {
            'filename': result_data['filename'],
            'created_at': result_data['created_at'],
            'summary': result_data['summary'],
            'flashcards': result_data['flashcards'],
            'topics': result_data['topics_data']
        }
        
        # Создаем временный файл
        import tempfile
        import json
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2)
            temp_path = f.name
        
        # Отправляем файл
        safe_filename = secure_filename(f"flashcards_{result_data['filename']}.json")
        
        return send_file(
            temp_path,
            as_attachment=True,
            download_name=safe_filename,
            mimetype='application/json'
        )
        
    except Exception as e:
        logger.error(f"Error downloading flashcards for result {result_id}: {str(e)}")
        flash('Ошибка при скачивании файла', 'danger')
        return redirect(url_for('my_results'))



@app.errorhandler(413)
def request_entity_too_large(e):
    """Превышен максимальный размер файла"""
    max_mb = app.config['MAX_CONTENT_LENGTH'] // (1024 * 1024)
    flash(f'Размер файла превышает лимит в {max_mb} МБ', 'danger')
    return redirect(url_for('index'))

# API для аналитики элементов интерфейса
@app.route('/api/track_interaction', methods=['POST'])
def track_interaction():
    """API для записи взаимодействий с элементами интерфейса"""
    try:
        data = request.get_json()
        
        # Получаем данные из запроса
        element_type = data.get('element_type')
        element_id = data.get('element_id', '')
        action_type = data.get('action_type')
        page_url = data.get('page_url', request.referrer)
        page_title = data.get('page_title', '')
        metadata = data.get('metadata', {})
        
        # Получаем session_id из сессии или создаем новый
        session_id = session.get('analytics_session_id')
        if not session_id:
            import uuid
            session_id = str(uuid.uuid4())
            session['analytics_session_id'] = session_id
            
            # Начинаем новую сессию
            user_agent = request.headers.get('User-Agent', '')
            ip_address = request.remote_addr
            user_id = current_user.id if current_user.is_authenticated else None
            
            element_analytics.start_session(session_id, user_id, user_agent, ip_address)
        
        # Записываем взаимодействие
        user_id = current_user.id if current_user.is_authenticated else None
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
        
        return jsonify({'success': True})
        
    except Exception as e:
        logger.error(f"Error tracking interaction: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/analytics/popular_elements')
@login_required
def get_popular_elements():
    """API для получения популярных элементов (только для администратора)"""
    try:
        if not is_admin(current_user):
            return jsonify({'error': 'Access denied. Admin rights required.'}), 403
        
        days = request.args.get('days', 30, type=int)
        limit = request.args.get('limit', 20, type=int)
        
        popular_elements = element_analytics.get_popular_elements(limit=limit, days=days)
        return jsonify({'popular_elements': popular_elements})
        
    except Exception as e:
        logger.error(f"Error getting popular elements: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/analytics/element_stats')
@login_required
def get_element_stats():
    """API для получения статистики элементов (только для администратора)"""
    try:
        if not is_admin(current_user):
            return jsonify({'error': 'Access denied. Admin rights required.'}), 403
        
        element_type = request.args.get('element_type')
        element_id = request.args.get('element_id')
        days = request.args.get('days', 30, type=int)
        
        stats = element_analytics.get_element_usage_stats(
            element_type=element_type,
            element_id=element_id,
            days=days
        )
        
        return jsonify(stats)
        
    except Exception as e:
        logger.error(f"Error getting element stats: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/analytics/user_behavior')
@login_required
def get_user_behavior():
    """API для получения паттернов поведения пользователей (только для администратора)"""
    try:
        if not is_admin(current_user):
            return jsonify({'error': 'Access denied. Admin rights required.'}), 403
        
        user_id = request.args.get('user_id', type=int)
        days = request.args.get('days', 30, type=int)
        
        behavior = element_analytics.get_user_behavior_patterns(user_id=user_id, days=days)
        return jsonify(behavior)
        
    except Exception as e:
        logger.error(f"Error getting user behavior: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/analytics/page_stats')
@login_required
def get_page_stats():
    """API для получения статистики по страницам (только для администратора)"""
    try:
        if not is_admin(current_user):
            return jsonify({'error': 'Access denied. Admin rights required.'}), 403
        
        page_url = request.args.get('page_url')
        days = request.args.get('days', 30, type=int)
        
        stats = element_analytics.get_page_analytics(page_url=page_url, days=days)
        return jsonify(stats)
        
    except Exception as e:
        logger.error(f"Error getting page stats: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/analytics/user_stats')
@login_required
def get_detailed_user_stats():
    """API для получения детальной статистики пользователей (только для администратора)"""
    try:
        if not is_admin(current_user):
            return jsonify({'error': 'Access denied. Admin rights required.'}), 403
        
        days = request.args.get('days', 30, type=int)
        
        stats = element_analytics.get_detailed_user_stats(days=days)
        return jsonify(stats)
        
    except Exception as e:
        logger.error(f"Error getting user stats: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/analytics/user_engagement')
@login_required
def get_user_engagement():
    """API для получения метрик вовлеченности пользователей (только для администратора)"""
    try:
        if not is_admin(current_user):
            return jsonify({'error': 'Access denied. Admin rights required.'}), 403
        
        days = request.args.get('days', 30, type=int)
        
        engagement = element_analytics.get_user_engagement_metrics(days=days)
        return jsonify(engagement)
        
    except Exception as e:
        logger.error(f"Error getting user engagement: {str(e)}")
        return jsonify({'error': str(e)}), 500

# API для управления учебными сессиями
@app.route('/api/study_session/start/<int:session_id>', methods=['POST'])
@login_required
def start_study_session(session_id):
    """Запуск учебной сессии"""
    try:
        conn = sqlite3.connect('ai_study.db')
        c = conn.cursor()
        
        # Проверяем, что сессия принадлежит текущему пользователю
        c.execute('''
            SELECT id, status FROM study_sessions 
            WHERE id = ? AND user_id = ?
        ''', (session_id, current_user.id))
        
        session = c.fetchone()
        if not session:
            return jsonify({'success': False, 'error': 'Сессия не найдена'}), 404
        
        # Обновляем статус сессии
        c.execute('''
            UPDATE study_sessions 
            SET status = 'in_progress', started_at = ?
            WHERE id = ?
        ''', (datetime.now(), session_id))
        
        # Записываем активность
        c.execute('''
            INSERT INTO session_activities 
            (session_id, user_id, activity_type, created_at)
            VALUES (?, ?, ?, ?)
        ''', (session_id, current_user.id, 'session_started', datetime.now()))
        
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Сессия запущена'})
        
    except Exception as e:
        logger.error(f"Error starting study session: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/study_session/complete/<int:session_id>', methods=['POST'])
@login_required
def complete_study_session(session_id):
    """Завершение учебной сессии"""
    try:
        data = request.get_json() or {}
        duration_seconds = data.get('duration_seconds', 0)
        cards_reviewed = data.get('cards_reviewed', 0)
        cards_mastered = data.get('cards_mastered', 0)
        notes = data.get('notes', '')
        
        conn = sqlite3.connect('ai_study.db')
        c = conn.cursor()
        
        # Проверяем, что сессия принадлежит текущему пользователю
        c.execute('''
            SELECT id, status FROM study_sessions 
            WHERE id = ? AND user_id = ?
        ''', (session_id, current_user.id))
        
        session = c.fetchone()
        if not session:
            return jsonify({'success': False, 'error': 'Сессия не найдена'}), 404
        
        # Обновляем статус сессии
        c.execute('''
            UPDATE study_sessions 
            SET status = 'completed', completed_at = ?, progress = 100
            WHERE id = ?
        ''', (datetime.now(), session_id))
        
        # Записываем активность
        c.execute('''
            INSERT INTO session_activities 
            (session_id, user_id, activity_type, duration_seconds, 
             cards_reviewed, cards_mastered, notes, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (session_id, current_user.id, 'session_completed', duration_seconds,
              cards_reviewed, cards_mastered, notes, datetime.now()))
        
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Сессия завершена'})
        
    except Exception as e:
        logger.error(f"Error completing study session: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/study_session/reset_sessions', methods=['POST'])
@login_required
def reset_user_sessions():
    """Сброс всех сессий пользователя (для пересоздания)"""
    try:
        conn = sqlite3.connect('ai_study.db')
        c = conn.cursor()
        
        # Удаляем все сессии пользователя
        c.execute('DELETE FROM session_activities WHERE user_id = ?', (current_user.id,))
        c.execute('DELETE FROM study_sessions WHERE user_id = ?', (current_user.id,))
        
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Сессии сброшены'})
        
    except Exception as e:
        logger.error(f"Error resetting sessions: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

# Страница аналитики
@app.route('/analytics')
@login_required
def analytics_dashboard():
    """Страница аналитики использования элементов"""
    if not is_admin(current_user):
        flash('Доступ запрещен. Недостаточно прав.', 'danger')
        return redirect(url_for('dashboard'))
    return render_template('analytics_dashboard.html')

@app.route('/analytics/demo')
@login_required
def analytics_demo():
    """Демонстрационная страница для тестирования аналитики"""
    if not is_admin(current_user):
        flash('Доступ запрещен. Недостаточно прав.', 'danger')
        return redirect(url_for('dashboard'))
    return render_template('analytics_demo.html')

@app.route('/analytics/users')
@login_required
def user_analytics():
    """Страница статистики пользователей"""
    if not is_admin(current_user):
        flash('Доступ запрещен. Недостаточно прав.', 'danger')
        return redirect(url_for('dashboard'))
    return render_template('user_analytics.html')

@app.route('/my-analytics')
@login_required
def my_analytics():
    """Персональная аналитика пользователя по плану подписки"""
    try:
        # Получаем план подписки пользователя
        user_subscription = subscription_manager.get_user_subscription(current_user.id)
        plan_type = user_subscription.get('type', 'freemium') if user_subscription else 'freemium'
        
        logger.info(f"User {current_user.id} analytics request, plan: {plan_type}")
        
        # Получаем аналитику в зависимости от плана
        analytics_data = None
        if plan_type == 'lite':
            analytics_data = analytics_manager.get_learning_stats(current_user.id)
            logger.info(f"LITE analytics data: {analytics_data}")
        elif plan_type == 'starter':
            analytics_data = analytics_manager.get_learning_progress(current_user.id)
            logger.info(f"STARTER analytics data: {analytics_data}")
        elif plan_type == 'basic':
            analytics_data = analytics_manager.get_detailed_analytics(current_user.id)
            logger.info(f"BASIC analytics data: {analytics_data}")
        elif plan_type == 'pro':
            analytics_data = analytics_manager.get_full_analytics(current_user.id)
            logger.info(f"PRO analytics data: {analytics_data}")
        
        return render_template('user_analytics_page.html', 
                             analytics_data=analytics_data,
                             plan_type=plan_type,
                             subscription_plans=SUBSCRIPTION_PLANS)
    except Exception as e:
        logger.error(f"Error loading user analytics: {e}")
        flash('Ошибка при загрузке аналитики', 'danger')
        return redirect(url_for('dashboard'))

@app.route('/api/user-analytics')
@login_required
def api_user_analytics():
    """API для получения персональной аналитики пользователя"""
    try:
        # Получаем план подписки пользователя
        user_subscription = subscription_manager.get_user_subscription(current_user.id)
        plan_type = user_subscription.get('type', 'freemium') if user_subscription else 'freemium'
        
        # Получаем аналитику в зависимости от плана
        analytics_data = None
        if plan_type == 'lite':
            analytics_data = analytics_manager.get_learning_stats(current_user.id)
        elif plan_type == 'starter':
            analytics_data = analytics_manager.get_learning_progress(current_user.id)
        elif plan_type == 'basic':
            analytics_data = analytics_manager.get_detailed_analytics(current_user.id)
        elif plan_type == 'pro':
            analytics_data = analytics_manager.get_full_analytics(current_user.id)
        
        return jsonify({
            'success': True,
            'plan': plan_type,
            'analytics': analytics_data
        })
    except Exception as e:
        logger.error(f"Error in user analytics API: {e}")
        return jsonify({
            'success': False,
            'error': 'Ошибка при получении аналитики'
        }), 500

@app.route('/pricing')
def pricing():
    """Страница с планами подписки"""
    user_subscription = None
    usage_stats = None
    
    if current_user.is_authenticated:
        user_subscription = subscription_manager.get_user_subscription(current_user.id)
        usage_stats = subscription_manager.get_usage_stats(current_user.id)
    
    return render_template('pricing.html', 
                         user_subscription=user_subscription,
                         usage_stats=usage_stats,
                         subscription_plans=SUBSCRIPTION_PLANS)

@app.route('/upgrade_subscription', methods=['POST'])
@login_required
def upgrade_subscription():
    """Обновление плана подписки"""
    try:
        data = request.get_json()
        new_plan = data.get('plan')
        
        if not new_plan or new_plan not in SUBSCRIPTION_PLANS:
            return jsonify({'success': False, 'error': 'Неверный план подписки'})
        
        success = subscription_manager.upgrade_subscription(current_user.id, new_plan)
        
        if success:
            return jsonify({'success': True, 'message': f'План успешно изменен на {new_plan.upper()}'})
        else:
            return jsonify({'success': False, 'error': 'Ошибка при изменении плана'})
            
    except Exception as e:
        logger.error(f"Error upgrading subscription: {e}")
        return jsonify({'success': False, 'error': 'Произошла ошибка'})

@app.route('/subscription_status')
@login_required
def subscription_status():
    """API для получения статуса подписки"""
    try:
        subscription = subscription_manager.get_user_subscription(current_user.id)
        usage_stats = subscription_manager.get_usage_stats(current_user.id)
        
        return jsonify({
            'success': True,
            'subscription': subscription,
            'usage_stats': usage_stats
        })
        
    except Exception as e:
        logger.error(f"Error getting subscription status: {e}")
        return jsonify({'success': False, 'error': 'Ошибка получения статуса'})

# ==================== ГЕЙМИФИКАЦИЯ И УМНЫЕ УВЕДОМЛЕНИЯ ====================

@app.route('/api/smart-notifications')
@login_required
def get_smart_notifications():
    """API для получения умных уведомлений"""
    try:
        # Получаем триггеры апгрейда
        upgrade_offers = smart_triggers.get_upgrade_triggers(current_user.id)
        
        # Получаем данные геймификации
        gamification_data = gamification.get_user_gamification_data(current_user.id)
        
        # Получаем статистику подписки
        usage_stats = subscription_manager.get_usage_stats(current_user.id)
        
        notifications = []
        
        # Уведомления об апгрейде
        for offer in upgrade_offers[:2]:  # Максимум 2 предложения
            notification = {
                'id': f'upgrade_{offer.trigger_reason}',
                'type': 'upgrade',
                'title': offer.title,
                'message': offer.message,
                'icon': 'fas fa-arrow-up',
                'social_proof': offer.social_proof,
                'auto_hide': None,  # Не скрываем автоматически
                'actions': [
                    {
                        'text': offer.cta_text,
                        'type': 'primary',
                        'action': 'upgrade',
                        'icon': 'fas fa-rocket',
                        'url': '/pricing'
                    },
                    {
                        'text': 'Позже',
                        'type': 'outline-secondary',
                        'action': 'dismiss',
                        'icon': 'fas fa-times'
                    }
                ]
            }
            
            if offer.discount > 0:
                notification['message'] += f" Скидка {offer.discount}%!"
            
            notifications.append(notification)
        
        # Уведомления о лимитах
        if not usage_stats['analyses']['unlimited']:
            usage_percent = (usage_stats['analyses']['used'] / usage_stats['analyses']['limit']) * 100
            
            if usage_percent >= 80:
                notifications.append({
                    'id': 'limit_warning_analyses',
                    'type': 'limit',
                    'title': '⚠️ Лимит анализов почти исчерпан',
                    'message': f'Использовано {usage_stats["analyses"]["used"]} из {usage_stats["analyses"]["limit"]} анализов.',
                    'icon': 'fas fa-exclamation-triangle',
                    'progress': usage_percent,
                    'auto_hide': 30,
                    'actions': [
                        {
                            'text': 'Увеличить лимиты',
                            'type': 'warning',
                            'action': 'upgrade',
                            'icon': 'fas fa-arrow-up',
                            'url': '/pricing'
                        }
                    ]
                })
        
        # Уведомления о достижениях (если есть новые)
        if gamification_data['recent_xp']:
            recent_xp = gamification_data['recent_xp'][0]  # Последнее действие
            if recent_xp['action'] == 'achievement_unlocked':
                notifications.append({
                    'id': f'achievement_{datetime.now().timestamp()}',
                    'type': 'achievement',
                    'title': '🏆 Новое достижение!',
                    'message': recent_xp['description'],
                    'icon': 'fas fa-trophy',
                    'auto_hide': 10,
                    'actions': [
                        {
                            'text': 'Посмотреть все',
                            'type': 'success',
                            'action': 'learn_more',
                            'icon': 'fas fa-eye'
                        }
                    ]
                })
        
        # Социальные уведомления
        if gamification_data['level'] >= 5:
            leaderboard = gamification.get_leaderboard(10)
            user_rank = next((i for i, user in enumerate(leaderboard, 1) if user['user_id'] == current_user.id), None)
            
            if user_rank and user_rank <= 5:
                notifications.append({
                    'id': 'social_leaderboard',
                    'type': 'social',
                    'title': f'🌟 Вы в топ-{user_rank}!',
                    'message': f'Отличная работа! Вы занимаете {user_rank} место в рейтинге.',
                    'icon': 'fas fa-star',
                    'social_proof': f'Опережаете {len(leaderboard) - user_rank} пользователей',
                    'auto_hide': 15,
                    'actions': [
                        {
                            'text': 'Посмотреть рейтинг',
                            'type': 'info',
                            'action': 'learn_more',
                            'icon': 'fas fa-list'
                        }
                    ]
                })
        
        # Записываем показ уведомлений для аналитики
        for notification in notifications:
            if notification['type'] == 'upgrade':
                smart_triggers.record_trigger_shown(
                    current_user.id, 
                    notification['id'].replace('upgrade_', ''),
                    notification
                )
        
        return jsonify({
            'success': True,
            'notifications': notifications
        })
        
    except Exception as e:
        logger.error(f"Error getting smart notifications: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/track-notification-action', methods=['POST'])
@login_required
def track_notification_action():
    """Отслеживание действий с уведомлениями"""
    try:
        data = request.get_json()
        notification_id = data.get('notification_id')
        action = data.get('action')
        
        # Записываем действие для аналитики
        if notification_id.startswith('upgrade_'):
            trigger_reason = notification_id.replace('upgrade_', '')
            smart_triggers.record_trigger_action(current_user.id, trigger_reason, action)
        
        return jsonify({'success': True})
        
    except Exception as e:
        logger.error(f"Error tracking notification action: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/gamification/profile')
@login_required
def get_gamification_profile():
    """API для получения профиля геймификации"""
    try:
        data = gamification.get_user_gamification_data(current_user.id)
        return jsonify({'success': True, 'data': data})
        
    except Exception as e:
        logger.error(f"Error getting gamification profile: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/gamification/leaderboard')
@login_required
def get_leaderboard():
    """API для получения таблицы лидеров"""
    try:
        leaderboard = gamification.get_leaderboard(20)
        return jsonify({'success': True, 'leaderboard': leaderboard})
        
    except Exception as e:
        logger.error(f"Error getting leaderboard: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/gamification')
@login_required
def gamification_dashboard():
    """Страница геймификации"""
    try:
        # Получаем данные пользователя
        user_data = gamification.get_user_gamification_data(current_user.id)
        
        # Получаем таблицу лидеров
        leaderboard = gamification.get_leaderboard(10)
        
        # Получаем доступные достижения
        from gamification import ACHIEVEMENTS
        available_achievements = []
        unlocked_ids = set(a['id'] for a in user_data['achievements'])
        
        for achievement_id, achievement in ACHIEVEMENTS.items():
            available_achievements.append({
                'id': achievement_id,
                'title': achievement.title,
                'description': achievement.description,
                'icon': achievement.icon,
                'category': achievement.category,
                'xp_reward': achievement.xp_reward,
                'rarity': achievement.rarity,
                'unlocked': achievement_id in unlocked_ids
            })
        
        return render_template('gamification_dashboard.html',
                             user_data=user_data,
                             leaderboard=leaderboard,
                             achievements=available_achievements)
        
    except Exception as e:
        logger.error(f"Error loading gamification dashboard: {e}")
        flash('Ошибка загрузки данных геймификации', 'error')
        return redirect(url_for('dashboard'))

# ==================== АНАЛИТИКА ПО ПЛАНАМ ПОДПИСКИ ====================

@app.route('/api/user-analytics')
@login_required
def get_user_analytics():
    """API для получения аналитики пользователя в зависимости от плана подписки"""
    try:
        # Получаем план подписки пользователя
        subscription = subscription_manager.get_user_subscription(current_user.id)
        plan_type = subscription['type'] if subscription else 'freemium'
        
        # Получаем соответствующую аналитику
        if plan_type == 'freemium':
            # FREEMIUM - нет аналитики
            analytics_data = {
                'type': 'no_analytics',
                'message': 'Аналитика доступна начиная с плана LITE',
                'upgrade_required': True,
                'recommended_plan': 'lite'
            }
        elif plan_type == 'lite':
            # LITE - базовая статистика изучения
            analytics_data = analytics_manager.get_learning_stats(current_user.id)
        elif plan_type == 'starter':
            # STARTER - прогресс обучения
            analytics_data = analytics_manager.get_learning_progress(current_user.id)
        elif plan_type == 'basic':
            # BASIC - детальная аналитика
            analytics_data = analytics_manager.get_detailed_analytics(current_user.id)
        elif plan_type == 'pro':
            # PRO - полная аналитика
            analytics_data = analytics_manager.get_full_analytics(current_user.id)
        else:
            analytics_data = {'type': 'error', 'message': 'Неизвестный план подписки'}
        
        return jsonify({
            'success': True,
            'plan': plan_type,
            'analytics': analytics_data
        })
        
    except Exception as e:
        logger.error(f"Error getting user analytics: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/my-analytics')
@login_required
def user_analytics_page():
    """Страница персональной аналитики пользователя"""
    try:
        # Получаем план подписки
        subscription = subscription_manager.get_user_subscription(current_user.id)
        plan_type = subscription['type'] if subscription else 'freemium'
        
        # Получаем аналитику
        if plan_type == 'freemium':
            analytics_data = None
        elif plan_type == 'lite':
            analytics_data = analytics_manager.get_learning_stats(current_user.id)
        elif plan_type == 'starter':
            analytics_data = analytics_manager.get_learning_progress(current_user.id)
        elif plan_type == 'basic':
            analytics_data = analytics_manager.get_detailed_analytics(current_user.id)
        elif plan_type == 'pro':
            analytics_data = analytics_manager.get_full_analytics(current_user.id)
        else:
            analytics_data = None
        
        return render_template('user_analytics_page.html',
                             plan_type=plan_type,
                             analytics_data=analytics_data,
                             subscription=subscription)
        
    except Exception as e:
        logger.error(f"Error loading user analytics page: {e}")
        flash('Ошибка загрузки аналитики', 'error')
        return redirect(url_for('dashboard'))

if __name__ == '__main__':
    init_db()
    app.run(debug=True, host='0.0.0.0', port=5000)