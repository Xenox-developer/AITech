"""
Модуль аутентификации и авторизации пользователей
"""
import sqlite3
import hashlib
import secrets
from datetime import datetime, timedelta
from flask import current_app
from flask_login import UserMixin
import logging

logger = logging.getLogger(__name__)

class User(UserMixin):
    def __init__(self, id, email, username, password_hash, created_at, is_active=True, subscription_type='free'):
        self.id = id
        self.email = email
        self.username = username
        self.password_hash = password_hash
        self.created_at = created_at
        self._is_active = is_active
        self.subscription_type = subscription_type
    
    @property
    def is_active(self):
        return self._is_active
    
    def get_id(self):
        return str(self.id)
    
    def check_password(self, password):
        """Проверка пароля"""
        return check_password_hash(self.password_hash, password)
    
    @staticmethod
    def get(user_id):
        """Получение пользователя по ID"""
        conn = sqlite3.connect('ai_study.db')
        c = conn.cursor()
        
        c.execute('''
            SELECT id, email, username, password_hash, created_at, is_active, subscription_type
            FROM users WHERE id = ?
        ''', (user_id,))
        
        row = c.fetchone()
        conn.close()
        
        if row:
            return User(*row)
        return None
    
    @staticmethod
    def get_by_email(email):
        """Получение пользователя по email"""
        conn = sqlite3.connect('ai_study.db')
        c = conn.cursor()
        
        c.execute('''
            SELECT id, email, username, password_hash, created_at, is_active, subscription_type
            FROM users WHERE email = ?
        ''', (email,))
        
        row = c.fetchone()
        conn.close()
        
        if row:
            return User(*row)
        return None
    
    @staticmethod
    def create(email, username, password):
        """Создание нового пользователя"""
        conn = sqlite3.connect('ai_study.db')
        c = conn.cursor()
        
        password_hash = generate_password_hash(password)
        
        try:
            c.execute('''
                INSERT INTO users (email, username, password_hash, created_at, is_active, subscription_type)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (email, username, password_hash, datetime.now(), True, 'free'))
            
            user_id = c.lastrowid
            conn.commit()
            conn.close()
            
            logger.info(f"New user created: {email} (ID: {user_id})")
            return User.get(user_id)
            
        except sqlite3.IntegrityError:
            conn.close()
            return None
    
    def get_results_count(self):
        """Получение количества результатов пользователя"""
        conn = sqlite3.connect('ai_study.db')
        c = conn.cursor()
        
        c.execute('SELECT COUNT(*) FROM result WHERE user_id = ?', (self.id,))
        count = c.fetchone()[0]
        conn.close()
        
        return count
    
    def get_recent_results(self, limit=5):
        """Получение последних результатов пользователя"""
        conn = sqlite3.connect('ai_study.db')
        c = conn.cursor()
        
        c.execute('''
            SELECT id, filename, file_type, created_at
            FROM result 
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT ?
        ''', (self.id, limit))
        
        results = []
        for row in c.fetchall():
            results.append({
                'id': row[0],
                'filename': row[1],
                'file_type': row[2],
                'created_at': row[3]
            })
        
        conn.close()
        return results

def generate_password_hash(password):
    """Генерация хеша пароля"""
    salt = secrets.token_hex(16)
    password_hash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), 100000)
    return salt + password_hash.hex()

def check_password_hash(stored_hash, password):
    """Проверка пароля"""
    salt = stored_hash[:32]
    stored_password_hash = stored_hash[32:]
    password_hash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), 100000)
    return password_hash.hex() == stored_password_hash

def init_auth_db():
    """Инициализация таблиц для аутентификации"""
    conn = sqlite3.connect('ai_study.db')
    c = conn.cursor()
    
    # Таблица пользователей
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            username TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_active BOOLEAN DEFAULT TRUE,
            subscription_type TEXT DEFAULT 'free',
            last_login TIMESTAMP,
            profile_image TEXT
        )
    ''')
    
    # Добавляем колонку user_id в таблицу result если её нет
    try:
        c.execute('ALTER TABLE result ADD COLUMN user_id INTEGER')
        logger.info("Added user_id column to result table")
    except sqlite3.OperationalError:
        # Колонка уже существует
        pass
    
    # Добавляем колонку user_id в таблицу user_progress если её нет
    try:
        c.execute('ALTER TABLE user_progress ADD COLUMN user_id INTEGER')
        logger.info("Added user_id column to user_progress table")
    except sqlite3.OperationalError:
        # Колонка уже существует
        pass
    
    # Добавляем колонку user_id в таблицу chat_history если её нет
    try:
        c.execute('ALTER TABLE chat_history ADD COLUMN user_id INTEGER')
        logger.info("Added user_id column to chat_history table")
    except sqlite3.OperationalError:
        # Колонка уже существует
        pass
    
    # Таблица сессий (для "Запомнить меня")
    c.execute('''
        CREATE TABLE IF NOT EXISTS user_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            session_token TEXT UNIQUE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP NOT NULL,
            is_active BOOLEAN DEFAULT TRUE,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    
    # Таблица статистики пользователей
    c.execute('''
        CREATE TABLE IF NOT EXISTS user_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            total_files_processed INTEGER DEFAULT 0,
            total_flashcards_created INTEGER DEFAULT 0,
            total_study_time_minutes INTEGER DEFAULT 0,
            streak_days INTEGER DEFAULT 0,
            last_activity TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    
    conn.commit()
    conn.close()
    logger.info("Auth database initialized successfully")