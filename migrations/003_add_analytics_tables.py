"""
Миграция для добавления таблиц аналитики элементов интерфейса
"""

import sqlite3
import logging

logger = logging.getLogger(__name__)

def up(conn):
    """Применение миграции - создание таблиц аналитики"""
    c = conn.cursor()
    
    try:
        # Таблица событий взаимодействия с элементами
        c.execute('''
            CREATE TABLE IF NOT EXISTS element_interactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                session_id TEXT,
                element_type TEXT NOT NULL,
                element_id TEXT,
                action_type TEXT NOT NULL,
                page_url TEXT,
                page_title TEXT,
                metadata TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')
        
        # Таблица аналитических сессий пользователей
        c.execute('''
            CREATE TABLE IF NOT EXISTS analytics_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT UNIQUE NOT NULL,
                user_id INTEGER,
                start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                end_time TIMESTAMP,
                page_views INTEGER DEFAULT 0,
                total_interactions INTEGER DEFAULT 0,
                user_agent TEXT,
                ip_address TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')
        
        # Таблица популярности элементов
        c.execute('''
            CREATE TABLE IF NOT EXISTS element_popularity (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                element_type TEXT NOT NULL,
                element_id TEXT,
                action_type TEXT NOT NULL,
                total_interactions INTEGER DEFAULT 0,
                unique_users INTEGER DEFAULT 0,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(element_type, element_id, action_type)
            )
        ''')
        
        # Индексы для быстрого поиска
        c.execute('CREATE INDEX IF NOT EXISTS idx_interactions_user_time ON element_interactions(user_id, timestamp)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_interactions_element ON element_interactions(element_type, element_id)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_interactions_session ON element_interactions(session_id)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_sessions_user ON analytics_sessions(user_id)')
        
        logger.info("Analytics tables created successfully")
        return True
        
    except Exception as e:
        logger.error(f"Error creating analytics tables: {e}")
        return False

def down(db_path: str = 'ai_study.db'):
    """Откат миграции - удаление таблиц аналитики"""
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    try:
        # Удаляем индексы
        c.execute('DROP INDEX IF EXISTS idx_interactions_user_time')
        c.execute('DROP INDEX IF EXISTS idx_interactions_element')
        c.execute('DROP INDEX IF EXISTS idx_interactions_session')
        c.execute('DROP INDEX IF EXISTS idx_sessions_user')
        
        # Удаляем таблицы
        c.execute('DROP TABLE IF EXISTS element_popularity')
        c.execute('DROP TABLE IF EXISTS element_interactions')
        c.execute('DROP TABLE IF EXISTS analytics_sessions')
        
        conn.commit()
        logger.info("Analytics tables dropped successfully")
        return True
        
    except Exception as e:
        logger.error(f"Error dropping analytics tables: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    up()