"""
Миграция 006: Добавление таблиц геймификации
"""
import sqlite3
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

def up(conn):
    """Выполнение миграции 006"""
    c = conn.cursor()
    
    try:
        logger.info("Running migration 006: Adding gamification tables")
        
        # Таблица пользовательского прогресса геймификации
        c.execute('''
            CREATE TABLE IF NOT EXISTS user_gamification (
                user_id INTEGER PRIMARY KEY,
                level INTEGER DEFAULT 1,
                total_xp INTEGER DEFAULT 0,
                current_streak INTEGER DEFAULT 0,
                longest_streak INTEGER DEFAULT 0,
                last_activity_date DATE,
                achievements_json TEXT DEFAULT '[]',
                weekly_goals_json TEXT DEFAULT '{}',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')
        
        # Таблица истории XP
        c.execute('''
            CREATE TABLE IF NOT EXISTS xp_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                action_type TEXT NOT NULL,
                xp_gained INTEGER NOT NULL,
                description TEXT,
                metadata_json TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')
        
        # Таблица достижений пользователей
        c.execute('''
            CREATE TABLE IF NOT EXISTS user_achievements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                achievement_id TEXT NOT NULL,
                unlocked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, achievement_id),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')
        
        # Таблица еженедельных целей
        c.execute('''
            CREATE TABLE IF NOT EXISTS weekly_challenges (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                week_start DATE NOT NULL,
                challenge_type TEXT NOT NULL,
                target_value INTEGER NOT NULL,
                current_progress INTEGER DEFAULT 0,
                completed BOOLEAN DEFAULT FALSE,
                reward_xp INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')
        
        # Таблица логирования триггеров апгрейда
        c.execute('''
            CREATE TABLE IF NOT EXISTS upgrade_triggers_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                trigger_reason TEXT NOT NULL,
                offer_details TEXT,
                shown_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                action TEXT,  -- 'upgraded', 'dismissed', 'clicked'
                action_at TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')
        
        # Индексы для быстрого поиска
        c.execute('CREATE INDEX IF NOT EXISTS idx_xp_history_user ON xp_history(user_id, created_at)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_achievements_user ON user_achievements(user_id)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_challenges_user_week ON weekly_challenges(user_id, week_start)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_triggers_user_date ON upgrade_triggers_log(user_id, shown_at)')
        
        # Добавляем колонку monthly_video_uploads_used в таблицу users если её нет
        try:
            c.execute('ALTER TABLE users ADD COLUMN monthly_video_uploads_used INTEGER DEFAULT 0')
            logger.info("Added monthly_video_uploads_used column to users table")
        except sqlite3.OperationalError as e:
            if "duplicate column name" not in str(e):
                logger.warning(f"Could not add monthly_video_uploads_used column: {e}")
        
        # Создаем записи геймификации для существующих пользователей
        c.execute('''
            INSERT OR IGNORE INTO user_gamification (user_id, level, total_xp)
            SELECT id, 1, 0 FROM users
        ''')
        
        # Начисляем ретроспективный XP существующим пользователям
        logger.info("Awarding retroactive XP to existing users...")
        
        # XP за существующие анализы
        c.execute('''
            SELECT user_id, COUNT(*) as analyses_count
            FROM result 
            WHERE user_id IS NOT NULL
            GROUP BY user_id
        ''')
        
        for user_id, count in c.fetchall():
            if user_id:
                xp_amount = count * 50  # 50 XP за анализ
                c.execute('''
                    UPDATE user_gamification 
                    SET total_xp = total_xp + ?
                    WHERE user_id = ?
                ''', (xp_amount, user_id))
                
                # Записываем в историю
                c.execute('''
                    INSERT INTO xp_history (user_id, action_type, xp_gained, description)
                    VALUES (?, 'retroactive_analyses', ?, ?)
                ''', (user_id, xp_amount, f'Ретроспективный XP за {count} анализов'))
        
        # XP за существующие AI сообщения
        c.execute('''
            SELECT user_id, COUNT(*) as messages_count
            FROM chat_history 
            WHERE user_id IS NOT NULL
            GROUP BY user_id
        ''')
        
        for user_id, count in c.fetchall():
            if user_id:
                xp_amount = count * 5  # 5 XP за сообщение
                c.execute('''
                    UPDATE user_gamification 
                    SET total_xp = total_xp + ?
                    WHERE user_id = ?
                ''', (xp_amount, user_id))
                
                # Записываем в историю
                c.execute('''
                    INSERT INTO xp_history (user_id, action_type, xp_gained, description)
                    VALUES (?, 'retroactive_chat', ?, ?)
                ''', (user_id, xp_amount, f'Ретроспективный XP за {count} AI сообщений'))
        
        # XP за работу с флеш-картами
        c.execute('''
            SELECT user_id, COUNT(*) as reviews_count
            FROM user_progress 
            WHERE user_id IS NOT NULL
            GROUP BY user_id
        ''')
        
        for user_id, count in c.fetchall():
            if user_id:
                xp_amount = count * 10  # 10 XP за повторение
                c.execute('''
                    UPDATE user_gamification 
                    SET total_xp = total_xp + ?
                    WHERE user_id = ?
                ''', (xp_amount, user_id))
                
                # Записываем в историю
                c.execute('''
                    INSERT INTO xp_history (user_id, action_type, xp_gained, description)
                    VALUES (?, 'retroactive_flashcards', ?, ?)
                ''', (user_id, xp_amount, f'Ретроспективный XP за {count} повторений'))
        
        # Обновляем уровни на основе накопленного XP
        c.execute('SELECT user_id, total_xp FROM user_gamification')
        for user_id, total_xp in c.fetchall():
            # Определяем уровень на основе XP
            level = 1
            if total_xp >= 40000: level = 100
            elif total_xp >= 25000: level = 75
            elif total_xp >= 16000: level = 50
            elif total_xp >= 10000: level = 35
            elif total_xp >= 6000: level = 25
            elif total_xp >= 3000: level = 15
            elif total_xp >= 1500: level = 10
            elif total_xp >= 500: level = 5
            
            c.execute('UPDATE user_gamification SET level = ? WHERE user_id = ?', (level, user_id))
        
        conn.commit()
        logger.info("Migration 006 completed successfully")
        
        conn.commit()
        logger.info("Migration 006 completed successfully")
        
    except Exception as e:
        conn.rollback()
        logger.error(f"Error in migration 006: {e}")
        raise

def run_migration(db_path: str = 'ai_study.db'):
    """Запуск миграции напрямую"""
    conn = sqlite3.connect(db_path)
    try:
        up(conn)
    finally:
        conn.close()

if __name__ == '__main__':
    run_migration()