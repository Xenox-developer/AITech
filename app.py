import os
import json
import sqlite3
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, send_file, jsonify
from werkzeug.utils import secure_filename
import logging  
from pathlib import Path

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['MAX_CONTENT_LENGTH'] = int(os.environ.get('MAX_UPLOAD_MB', 200)) * 1024 * 1024
app.config['UPLOAD_FOLDER'] = 'uploads'

# Ensure upload folder exists
Path(app.config['UPLOAD_FOLDER']).mkdir(exist_ok=True)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('app.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Allowed extensions
ALLOWED_EXTENSIONS = {'pdf', 'mp4', 'mov', 'mkv'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def init_db():
    """Initialize SQLite database"""
    conn = sqlite3.connect('ai_study.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS result (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            topics TEXT NOT NULL,
            summary TEXT NOT NULL,
            flashcards_json TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

def save_result(filename, topics, summary, flashcards):
    """Save processing result to database"""
    conn = sqlite3.connect('ai_study.db')
    c = conn.cursor()
    
    topics_str = '\n'.join(topics)
    flashcards_json = json.dumps(flashcards, ensure_ascii=False)
    
    c.execute('''
        INSERT INTO result (filename, topics, summary, flashcards_json)
        VALUES (?, ?, ?, ?)
    ''', (filename, topics_str, summary, flashcards_json))
    
    result_id = c.lastrowid
    conn.commit()
    conn.close()
    
    return result_id

def get_result(result_id):
    """Retrieve result from database"""
    conn = sqlite3.connect('ai_study.db')
    c = conn.cursor()
    
    c.execute('''
        SELECT filename, topics, summary, flashcards_json
        FROM result WHERE id = ?
    ''', (result_id,))
    
    row = c.fetchone()
    conn.close()
    
    if row:
        return {
            'filename': row[0],
            'topics': row[1].split('\n'),
            'summary': row[2],
            'flashcards': json.loads(row[3])
        }
    return None

@app.route('/')
def index():
    """Main page with upload form"""
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    """Handle file upload and processing"""
    try:
        # Check if file was uploaded
        if 'file' not in request.files:
            flash('Выберите файл', 'danger')
            return redirect(url_for('index'))
        
        file = request.files['file']
        
        # Check if file is empty
        if file.filename == '':
            flash('Выберите файл', 'danger')
            return redirect(url_for('index'))
        
        # Check file type
        if not allowed_file(file.filename):
            flash('Формат не поддерживается. Используйте PDF, MP4, MOV или MKV', 'danger')
            return redirect(url_for('index'))
        
        # Save file
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{timestamp}_{filename}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        logger.info(f"File uploaded: {filename}")
        
        # Process file
        try:
            from ai_study_mvp.ml import process_file
            topics, summary, flashcards = process_file(filepath, filename)
            
            # Save result to database
            result_id = save_result(filename, topics, summary, flashcards)
            
            # Clean up file after processing
            os.remove(filepath)
            
            logger.info(f"Processing completed for: {filename}")
            
            return redirect(url_for('result', result_id=result_id))
            
        except Exception as e:
            logger.error(f"Error processing file {filename}: {str(e)}")
            # Clean up file on error
            if os.path.exists(filepath):
                os.remove(filepath)
            flash('Ошибка обработки, попробуйте ещё раз', 'danger')
            return redirect(url_for('index'))
            
    except Exception as e:
        logger.error(f"Upload error: {str(e)}")
        flash('Ошибка загрузки файла', 'danger')
        return redirect(url_for('index'))

@app.route('/result/<int:result_id>')
def result(result_id):
    """Display processing results"""
    data = get_result(result_id)
    if not data:
        flash('Результат не найден', 'danger')
        return redirect(url_for('index'))
    
    return render_template('result.html', **data, result_id=result_id)

@app.route('/download/<int:result_id>')
def download_flashcards(result_id):
    """Download flashcards as JSON"""
    data = get_result(result_id)
    if not data:
        flash('Результат не найден', 'danger')
        return redirect(url_for('index'))
    
    # Create JSON file
    json_content = json.dumps(data['flashcards'], ensure_ascii=False, indent=2)
    
    # Save to temporary file
    temp_filename = f"flashcards_{result_id}.json"
    temp_path = os.path.join(app.config['UPLOAD_FOLDER'], temp_filename)
    
    with open(temp_path, 'w', encoding='utf-8') as f:
        f.write(json_content)
    
    # Send file and clean up
    def remove_file(response):
        try:
            os.remove(temp_path)
        except Exception:
            pass
        return response
    
    return send_file(
        temp_path,
        as_attachment=True,
        download_name=f"ai_study_flashcards_{datetime.now().strftime('%Y%m%d')}.json",
        mimetype='application/json'
    )

@app.route('/process_url', methods=['POST'])
def process_url():
    """Process video from URL"""
    try:
        url = request.json.get('url', '').strip()
        
        if not url:
            return jsonify({'error': 'URL не указан'}), 400
        
        # Here you would implement URL video download and processing
        # For MVP, we'll return a mock response
        flash('Обработка видео по ссылке будет доступна в следующей версии', 'info')
        return jsonify({'redirect': url_for('index')})
        
    except Exception as e:
        logger.error(f"URL processing error: {str(e)}")
        return jsonify({'error': 'Ошибка обработки URL'}), 500

@app.errorhandler(413)
def request_entity_too_large(e):
    """Handle file size limit exceeded"""
    max_mb = app.config['MAX_CONTENT_LENGTH'] // (1024 * 1024)
    flash(f'Размер файла превышает лимит в {max_mb} МБ', 'danger')
    return redirect(url_for('index'))

if __name__ == '__main__':
    init_db()
    app.run(debug=True, host='0.0.0.0', port=5000)