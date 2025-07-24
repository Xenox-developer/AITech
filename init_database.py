#!/usr/bin/env python3
"""
Скрипт для инициализации базы данных с таблицами пользователей
"""
import sqlite3
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def init_complete_database():
    """Полная инициализация базы данных"""
    conn = sqlite3.connect('ai_study.db')
    c = conn.cursor()
    
    # Создаем таблицу пользователей
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
    logger.info("Users table created/verified")
    
    # Создаем таблицу результатов
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
    logger.info("Result table created/verified")
    
    # Создаем таблицу прогресса пользователей
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
    logger.info("User progress table created/verified")
    
    # Создаем таблицу истории чата
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
    logger.info("Chat history table created/verified")
    
    # Создаем таблицу сессий
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
    logger.info("User sessions table created/verified")
    
    # Создаем таблицу статистики пользователей
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
    logger.info("User stats table created/verified")
    
    conn.commit()
    conn.close()
    logger.info("Database initialization completed successfully!")

if __name__ == '__main__':
    init_complete_database()