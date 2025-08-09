"""
Миграция 009: Добавление поля прогресса в таблицу analysis_tasks
"""

def up(conn):
    """Применение миграции"""
    c = conn.cursor()
    
    # Добавляем поля для отслеживания прогресса
    c.execute('''
        ALTER TABLE analysis_tasks 
        ADD COLUMN progress INTEGER DEFAULT 0
    ''')
    
    c.execute('''
        ALTER TABLE analysis_tasks 
        ADD COLUMN current_stage TEXT DEFAULT 'Подготовка'
    ''')
    
    c.execute('''
        ALTER TABLE analysis_tasks 
        ADD COLUMN stage_details TEXT DEFAULT ''
    ''')
    
    conn.commit()
    print("✅ Миграция 009: Добавлены поля прогресса в analysis_tasks")

def downgrade(conn):
    """Откат миграции"""
    c = conn.cursor()
    
    # SQLite не поддерживает DROP COLUMN, поэтому пересоздаем таблицу
    c.execute('''
        CREATE TABLE analysis_tasks_backup AS 
        SELECT id, user_id, filename, status, created_at, completed_at, cancelled_at, result_id
        FROM analysis_tasks
    ''')
    
    c.execute('DROP TABLE analysis_tasks')
    
    c.execute('''
        CREATE TABLE analysis_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            filename TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'processing',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP NULL,
            cancelled_at TIMESTAMP NULL,
            result_id INTEGER NULL,
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (result_id) REFERENCES result (id)
        )
    ''')
    
    c.execute('''
        INSERT INTO analysis_tasks (id, user_id, filename, status, created_at, completed_at, cancelled_at, result_id)
        SELECT id, user_id, filename, status, created_at, completed_at, cancelled_at, result_id
        FROM analysis_tasks_backup
    ''')
    
    c.execute('DROP TABLE analysis_tasks_backup')
    
    conn.commit()
    print("✅ Откат миграции 009: Удалены поля прогресса из analysis_tasks")