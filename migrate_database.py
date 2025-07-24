#!/usr/bin/env python3
"""
Скрипт для миграции базы данных
"""
import sqlite3
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def migrate_database():
    """Миграция базы данных для добавления системы аутентификации"""
    conn = sqlite3.connect('ai_study.db')
    c = conn.cursor()
    
    try:
        # Проверяем существующую структуру таблицы users
        c.execute("PRAGMA table_info(users)")
        columns = [column[1] for column in c.fetchall()]
        logger.info(f"Existing columns in users table: {columns}")
        
        # Если таблица users существует, но не имеет нужных колонок, пересоздаем её
        if 'username' not in columns or 'password_hash' not in columns:
            logger.info("Recreating users table with new structure...")
            
            # Сохраняем существующие данные (если есть)
            c.execute("SELECT * FROM users")
            existing_users = c.fetchall()
            
            # Удаляем старую таблицу
            c.execute("DROP TABLE IF EXISTS users")
            
            # Создаем новую таблицу с правильной структурой
            c.execute('''
                CREATE TABLE users (
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
            logger.info("New users table created")
            
            # Если были существующие пользователи, можно добавить логику для их миграции
            # Но пока оставим таблицу пустой для чистого старта
            
        # Обновляем таблицу result для добавления user_id если её нет
        c.execute("PRAGMA table_info(result)")
        result_columns = [column[1] for column in c.fetchall()]
        
        if 'user_id' not in result_columns:
            c.execute('ALTER TABLE result ADD COLUMN user_id INTEGER')
            logger.info("Added user_id column to result table")
        
        # Обновляем таблицу user_progress для добавления user_id если её нет
        c.execute("PRAGMA table_info(user_progress)")
        progress_columns = [column[1] for column in c.fetchall()]
        
        if 'user_id' not in progress_columns:
            c.execute('ALTER TABLE user_progress ADD COLUMN user_id INTEGER')
            logger.info("Added user_id column to user_progress table")
        
        # Обновляем таблицу chat_history для добавления user_id если её нет
        c.execute("PRAGMA table_info(chat_history)")
        chat_columns = [column[1] for column in c.fetchall()]
        
        if 'user_id' not in chat_columns:
            c.execute('ALTER TABLE chat_history ADD COLUMN user_id INTEGER')
            logger.info("Added user_id column to chat_history table")
        
        # Создаем дополнительные таблицы если их нет
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
        logger.info("Database migration completed successfully!")
        
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()

if __name__ == '__main__':
    migrate_database()