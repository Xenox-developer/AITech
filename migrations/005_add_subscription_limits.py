"""
Миграция 005: Добавление системы ограничений подписки
"""
import sqlite3
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

def up(conn):
    """Применение миграции"""
    c = conn.cursor()
    
    try:
        # Добавляем колонки для подписки в таблицу users
        columns_to_add = [
            ('subscription_type', 'TEXT DEFAULT "starter"'),
            ('subscription_start_date', 'TIMESTAMP'),
            ('subscription_end_date', 'TIMESTAMP'),
            ('monthly_analyses_used', 'INTEGER DEFAULT 0'),
            ('monthly_reset_date', 'TIMESTAMP'),
            ('total_pdf_pages_used', 'INTEGER DEFAULT 0'),
            ('total_video_minutes_used', 'INTEGER DEFAULT 0'),
            ('ai_chat_messages_used', 'INTEGER DEFAULT 0'),
            ('subscription_status', 'TEXT DEFAULT "active"')
        ]
        
        for column_name, column_def in columns_to_add:
            try:
                c.execute(f'ALTER TABLE users ADD COLUMN {column_name} {column_def}')
                logger.info(f"Added column {column_name} to users table")
            except sqlite3.OperationalError as e:
                if "duplicate column name" not in str(e):
                    logger.warning(f"Could not add column {column_name}: {e}")
        
        # Создаем таблицу для отслеживания использования
        c.execute('''
            CREATE TABLE IF NOT EXISTS subscription_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                usage_type TEXT NOT NULL,
                amount INTEGER DEFAULT 1,
                resource_info TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')
        
        # Создаем таблицу для истории подписок
        c.execute('''
            CREATE TABLE IF NOT EXISTS subscription_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                old_plan TEXT,
                new_plan TEXT,
                change_reason TEXT,
                changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')
        
        # Инициализируем существующих пользователей с планом starter
        c.execute('''
            UPDATE users 
            SET subscription_type = 'starter',
                monthly_reset_date = datetime('now', '+1 month'),
                subscription_start_date = datetime('now'),
                subscription_status = 'active'
            WHERE subscription_type IS NULL OR subscription_type = 'free'
        ''')
        
        logger.info("Migration 005 completed successfully")
        
    except Exception as e:
        logger.error(f"Migration 005 failed: {e}")
        raise

def downgrade():
    """Откат миграции"""
    conn = sqlite3.connect('ai_study.db')
    c = conn.cursor()
    
    try:
        # Удаляем созданные таблицы
        c.execute('DROP TABLE IF EXISTS subscription_usage')
        c.execute('DROP TABLE IF EXISTS subscription_history')
        
        # Примечание: SQLite не поддерживает DROP COLUMN, 
        # поэтому колонки останутся в таблице users
        
        conn.commit()
        logger.info("Migration 005 downgrade completed")
        
    except Exception as e:
        conn.rollback()
        logger.error(f"Migration 005 downgrade failed: {e}")
        raise
    finally:
        conn.close()

if __name__ == '__main__':
    conn = sqlite3.connect('ai_study.db')
    up(conn)
    conn.commit()
    conn.close()