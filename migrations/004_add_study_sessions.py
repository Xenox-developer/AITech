"""
Миграция для добавления таблиц учебных сессий
"""

import sqlite3
import logging

logger = logging.getLogger(__name__)

def up(conn):
    """Применение миграции - создание таблиц учебных сессий"""
    c = conn.cursor()
    
    try:
        # Таблица учебных сессий пользователей
        c.execute('''
            CREATE TABLE IF NOT EXISTS study_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                result_id INTEGER,
                session_type TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                phase TEXT NOT NULL,
                difficulty TEXT NOT NULL,
                duration_minutes INTEGER DEFAULT 45,
                status TEXT DEFAULT 'available',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                started_at TIMESTAMP,
                completed_at TIMESTAMP,
                progress INTEGER DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (result_id) REFERENCES result(id)
            )
        ''')
        
        # Таблица активности в учебных сессиях
        c.execute('''
            CREATE TABLE IF NOT EXISTS session_activities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                activity_type TEXT NOT NULL,
                duration_seconds INTEGER,
                cards_reviewed INTEGER DEFAULT 0,
                cards_mastered INTEGER DEFAULT 0,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES study_sessions(id),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')
        
        # Индексы для быстрого поиска
        c.execute('CREATE INDEX IF NOT EXISTS idx_study_sessions_user ON study_sessions(user_id)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_study_sessions_status ON study_sessions(user_id, status)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_session_activities_session ON session_activities(session_id)')
        
        logger.info("Study sessions tables created successfully")
        return True
        
    except Exception as e:
        logger.error(f"Error creating study sessions tables: {e}")
        return False

def down(db_path: str = 'ai_study.db'):
    """Откат миграции - удаление таблиц учебных сессий"""
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    try:
        # Удаляем индексы
        c.execute('DROP INDEX IF EXISTS idx_study_sessions_user')
        c.execute('DROP INDEX IF EXISTS idx_study_sessions_status')
        c.execute('DROP INDEX IF EXISTS idx_session_activities_session')
        
        # Удаляем таблицы
        c.execute('DROP TABLE IF EXISTS session_activities')
        c.execute('DROP TABLE IF EXISTS study_sessions')
        
        conn.commit()
        logger.info("Study sessions tables dropped successfully")
        return True
        
    except Exception as e:
        logger.error(f"Error dropping study sessions tables: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    up()