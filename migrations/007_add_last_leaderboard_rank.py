"""
Миграция 007: Добавление отслеживания позиции в рейтинге
"""

def up(conn):
    """Добавляем колонку для отслеживания последней позиции в рейтинге"""
    c = conn.cursor()
    
    # Добавляем колонку для последней позиции в рейтинге
    c.execute('''
        ALTER TABLE users 
        ADD COLUMN last_leaderboard_rank INTEGER DEFAULT NULL
    ''')
    
    # Добавляем колонку для времени последнего обновления рейтинга
    c.execute('''
        ALTER TABLE users 
        ADD COLUMN last_rank_update TIMESTAMP DEFAULT NULL
    ''')
    
    conn.commit()
    print("✅ Добавлены колонки для отслеживания позиции в рейтинге")

def downgrade(conn):
    """Откат миграции"""
    # SQLite не поддерживает DROP COLUMN, поэтому создаем новую таблицу
    c = conn.cursor()
    
    # Создаем временную таблицу без новых колонок
    c.execute('''
        CREATE TABLE users_temp AS 
        SELECT id, email, plan, subscription_start, subscription_end, created_at,
               username, password_hash, is_active, subscription_type, last_login,
               profile_image, subscription_start_date, subscription_end_date,
               monthly_analyses_used, monthly_reset_date, total_pdf_pages_used,
               total_video_minutes_used, ai_chat_messages_used, subscription_status,
               monthly_video_uploads_used, monthly_pdf_pages_used
        FROM users
    ''')
    
    # Удаляем старую таблицу
    c.execute('DROP TABLE users')
    
    # Переименовываем временную таблицу
    c.execute('ALTER TABLE users_temp RENAME TO users')
    
    conn.commit()
    print("✅ Откат миграции: удалены колонки отслеживания рейтинга")