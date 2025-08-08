"""
Миграция для добавления токенов доступа к существующим результатам
"""
import sqlite3
import secrets
import logging

logger = logging.getLogger(__name__)

def up(conn):
    """Добавляет токены доступа к существующим результатам"""
    try:
        c = conn.cursor()
        
        # Проверяем, есть ли колонка access_token
        c.execute("PRAGMA table_info(result)")
        columns = [column[1] for column in c.fetchall()]
        
        if 'access_token' not in columns:
            logger.info("Adding access_token column to result table")
            c.execute('ALTER TABLE result ADD COLUMN access_token TEXT UNIQUE')
        
        # Находим все записи без токенов доступа
        c.execute('SELECT id FROM result WHERE access_token IS NULL')
        results_without_tokens = c.fetchall()
        
        logger.info(f"Found {len(results_without_tokens)} results without access tokens")
        
        # Добавляем токены к существующим записям
        for (result_id,) in results_without_tokens:
            access_token = secrets.token_urlsafe(32)
            c.execute('UPDATE result SET access_token = ? WHERE id = ?', (access_token, result_id))
            logger.info(f"Added access token to result {result_id}")
        
        logger.info(f"Migration completed: added access tokens to {len(results_without_tokens)} results")
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