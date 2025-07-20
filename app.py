import os
import json
import sqlite3
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, send_file, jsonify, session
from werkzeug.utils import secure_filename
from usage_tracking import usage_tracker
import logging
from pathlib import Path
import yt_dlp
import tempfile
import re

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['MAX_CONTENT_LENGTH'] = int(os.environ.get('MAX_UPLOAD_MB', 200)) * 1024 * 1024
app.config['UPLOAD_FOLDER'] = 'uploads'

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
ALLOWED_EXTENSIONS = {'pdf', 'mp4', 'mov', 'mkv'}

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
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Добавляем колонку full_text если её нет (миграция)
    try:
        c.execute('ALTER TABLE result ADD COLUMN full_text TEXT')
        logger.info("Added full_text column to result table")
    except sqlite3.OperationalError:
        # Колонка уже существует
        pass
    
    # Таблица прогресса пользователя
    c.execute('''
        CREATE TABLE IF NOT EXISTS user_progress (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            result_id INTEGER,
            flashcard_id INTEGER,
            last_review TIMESTAMP,
            next_review TIMESTAMP,
            ease_factor REAL DEFAULT 2.5,
            consecutive_correct INTEGER DEFAULT 0,
            FOREIGN KEY (result_id) REFERENCES result(id)
        )
    ''')
    
    # Таблица для истории чата
    c.execute('''
        CREATE TABLE IF NOT EXISTS chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            result_id INTEGER,
            user_message TEXT NOT NULL,
            ai_response TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (result_id) REFERENCES result(id)
        )
    ''')
    
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
    
    c.execute('''
        INSERT INTO result (
            filename, file_type, topics_json, summary, flashcards_json,
            mind_map_json, study_plan_json, quality_json,
            video_segments_json, key_moments_json, full_text
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        filename, file_type, topics_json, analysis_result['summary'], 
        flashcards_json, mind_map_json, study_plan_json, quality_json,
        video_segments_json, key_moments_json, full_text
    ))
    
    result_id = c.lastrowid
    conn.commit()
    conn.close()
    
    return result_id

def get_result(result_id):
    """Получение результата из базы данных"""
    conn = sqlite3.connect('ai_study.db')
    c = conn.cursor()
    
    c.execute('''
        SELECT filename, file_type, topics_json, summary, flashcards_json,
               mind_map_json, study_plan_json, quality_json,
               video_segments_json, key_moments_json, full_text, created_at
        FROM result WHERE id = ?
    ''', (result_id,))
    
    row = c.fetchone()
    conn.close()
    
    if row:
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
            'created_at': row[11]
        }
        
        # Извлекаем информацию о страницах из mind_map (если она там сохранена)
        mind_map_data = result_data['mind_map']
        if isinstance(mind_map_data, dict) and 'page_info' in mind_map_data:
            result_data['page_info'] = mind_map_data['page_info']
        
        return result_data
    return None

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
            flash('Формат не поддерживается. Используйте PDF, MP4, MOV или MKV', 'danger')
            return redirect(url_for('index'))
        
        # Сохранение файла
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{timestamp}_{filename}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        logger.info(f"File uploaded: {filename}")
        
        # Получение диапазона страниц (только для PDF)
        page_range = None
        file_type = Path(filename).suffix.lower()
        if file_type == '.pdf':
            page_range = request.form.get('page_range', '').strip()
            if not page_range:
                page_range = '1-20'  # По умолчанию
            logger.info(f"Page range specified: {page_range}")
        
        # Обработка файла
        try:
            from ml import process_file
            analysis_result = process_file(filepath, filename, page_range=page_range)
            
            # Подготовка информации о страницах
            page_info = None
            if file_type == '.pdf' and page_range:
                page_info = {
                    'page_range': page_range,
                    'processed_at': datetime.now().isoformat()
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
        
        # Проверка существования прогресса
        c.execute('''
            SELECT id, ease_factor, consecutive_correct 
            FROM user_progress 
            WHERE result_id = ? AND flashcard_id = ?
        ''', (result_id, flashcard_id))
        
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
                (result_id, flashcard_id, last_review, next_review, ease_factor, consecutive_correct)
                VALUES (?, ?, CURRENT_TIMESTAMP, datetime('now', '+' || ? || ' days'), 2.5, ?)
            ''', (result_id, flashcard_id, interval_days, consecutive))
        
        conn.commit()
        conn.close()
        
        logger.info(f"Flashcard progress updated successfully. Next review in {interval_days} days")
        return jsonify({"success": True, "next_review_days": interval_days})
        
    except Exception as e:
        logger.error(f"Error updating flashcard progress: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/download/<int:result_id>')
def download_flashcards(result_id):
    """Сохранение флеш-карт как JSON"""
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
def chat_with_lecture(result_id):
    """Чат с ChatGPT на основе загруженной лекции"""
    try:
        data = request.json
        if not data:
            return jsonify({"success": False, "error": "No data provided"}), 400
            
        user_message = data.get('message', '').strip()
        if not user_message:
            return jsonify({"success": False, "error": "Message is required"}), 400
            
        # Получаем данные лекции
        result_data = get_result(result_id)
        if not result_data:
            return jsonify({"success": False, "error": "Lecture not found"}), 404
            
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
            INSERT INTO chat_history (result_id, user_message, ai_response)
            VALUES (?, ?, ?)
        ''', (result_id, user_message, ai_response))
        
        conn.commit()
        conn.close()
        
        logger.info(f"Chat message processed for result {result_id}")
        return jsonify({
            "success": True, 
            "response": ai_response,
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error in chat: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500

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

@app.errorhandler(413)
def request_entity_too_large(e):
    """Превышен максимальный размер файла"""
    max_mb = app.config['MAX_CONTENT_LENGTH'] // (1024 * 1024)
    flash(f'Размер файла превышает лимит в {max_mb} МБ', 'danger')
    return redirect(url_for('index'))

if __name__ == '__main__':
    init_db()
    app.run(debug=True, host='0.0.0.0', port=5000)