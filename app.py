import os
import json
import sqlite3
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, flash, send_file, jsonify, session
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.utils import secure_filename
from usage_tracking import usage_tracker
from auth import User, init_auth_db, generate_password_hash, check_password_hash
from migration_manager import run_migrations
import logging
from pathlib import Path
import yt_dlp
import tempfile
import re

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
    
    c.execute('''
        INSERT INTO result (
            filename, file_type, topics_json, summary, flashcards_json,
            mind_map_json, study_plan_json, quality_json,
            video_segments_json, key_moments_json, full_text, user_id, test_questions_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        filename, file_type, topics_json, analysis_result['summary'], 
        flashcards_json, mind_map_json, study_plan_json, quality_json,
        video_segments_json, key_moments_json, full_text, user_id, test_questions_json
    ))
    
    result_id = c.lastrowid
    conn.commit()
    conn.close()
    
    return result_id

def get_result(result_id, check_access=True):
    """Получение результата из базы данных"""
    conn = sqlite3.connect('ai_study.db')
    c = conn.cursor()
    
    c.execute('''
        SELECT filename, file_type, topics_json, summary, flashcards_json,
               mind_map_json, study_plan_json, quality_json,
               video_segments_json, key_moments_json, full_text, created_at, user_id, test_questions_json
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
            'test_questions': json.loads(row[13]) if row[13] else []
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
        SELECT id, filename, file_type, created_at
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
            'created_at': row[3]
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
    
    return render_template('dashboard.html', stats=stats, all_results=all_results, pagination=pagination)

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
        SELECT id, filename, file_type, created_at
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
            'created_at': row[3]
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
                         result_id=result_id)

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
    return render_template('index.html')

@app.route('/pricing')
def pricing():
    """Страница тарифов"""
    return render_template('pricing.html')

@app.route('/upload', methods=['POST'])
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
        
        # Сохраняем оригинальное расширение файла
        file_ext = Path(original_filename).suffix.lower()
        filename_without_ext = Path(original_filename).stem
        filename = f"{timestamp}_{filename_without_ext}{file_ext}"
        
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
            result_id = save_result(filename, file_type, analysis_result, page_info)
            
            # Удаление файла
            os.remove(filepath)
            
            logger.info(f"Advanced processing completed for: {filename}")
            
            return redirect(url_for('result', result_id=result_id))
            
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
                result_id = save_result(filename, '.mp4', analysis_result, video_info)
                logger.info(f"✅ Results saved with ID: {result_id}")
                
                # Теперь можно безопасно удалить файл
                if os.path.exists(filepath):
                    os.remove(filepath)
                    logger.info(f"🗑️ Temporary file {filename} removed")
                
                logger.info(f"🎉 Video processing completed successfully for: {filename}")
                
                return redirect(url_for('result', result_id=result_id))
                
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

@app.route('/result/<int:result_id>')
def result(result_id):
    """Отображение результата"""
    data = get_result(result_id)
    if not data:
        flash('Результат не найден', 'danger')
        return redirect(url_for('index'))
    
    return render_template('result.html', **data, result_id=result_id)

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
        
        # Сохраняем в историю чата
        conn = sqlite3.connect('ai_study.db')
        c = conn.cursor()
        
        c.execute('''
            INSERT INTO chat_history (result_id, user_id, user_message, ai_response)
            VALUES (?, ?, ?, ?)
        ''', (result_id, current_user.id, user_message, ai_response))
        
        conn.commit()
        conn.close()
        
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

if __name__ == '__main__':
    init_db()
    app.run(debug=True, host='0.0.0.0', port=5000)