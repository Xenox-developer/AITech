"""
Миграция для добавления поля monthly_video_uploads_used в таблицу users
"""
import sqlite3
import logging

logger = logging.getLogger(__name__)

def up(conn):
    """Добавляет поле для отслеживания использования видео загрузок"""
    try:
        c = conn.cursor()
        
        # Проверяем текущую структуру таблицы users
        c.execute("PRAGMA table_info(users)")
        columns = [column[1] for column in c.fetchall()]
        
        # Добавляем недостающие поля
        fields_to_add = [
            ('monthly_pdf_pages_used', 'INTEGER DEFAULT 0'),
            ('monthly_video_uploads_used', 'INTEGER DEFAULT 0'),
            ('ai_chat_messages_used', 'INTEGER DEFAULT 0')
        ]
        
        for field_name, field_definition in fields_to_add:
            if field_name not in columns:
                logger.info(f"Adding {field_name} column to users table")
                c.execute(f'ALTER TABLE users ADD COLUMN {field_name} {field_definition}')
                
                # Устанавливаем значение по умолчанию для существующих записей
                c.execute(f'UPDATE users SET {field_name} = 0 WHERE {field_name} IS NULL')
        
        logger.info("Migration completed: added video uploads tracking fields")
        return True
        
    except Exception as e:
        logger.error(f"Migration failed: {str(e)}")
        return False

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    conn = sqlite3.connect('ai_study.db')
    up(conn)
    conn.commit()
    conn.close()