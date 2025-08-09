"""
Миграция 008: Добавление таблицы для отслеживания задач анализа
"""

def up(conn):
    """Применение миграции"""
    c = conn.cursor()
    
    # Создаем таблицу для отслеживания задач анализа
    c.execute('''
        CREATE TABLE IF NOT EXISTS analysis_tasks (
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
    
    # Создаем индексы для быстрого поиска
    c.execute('CREATE INDEX IF NOT EXISTS idx_analysis_tasks_user_id ON analysis_tasks(user_id)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_analysis_tasks_status ON analysis_tasks(status)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_analysis_tasks_created_at ON analysis_tasks(created_at)')
    
    conn.commit()
    print("✅ Миграция 008: Таблица analysis_tasks создана")

def downgrade(conn):
    """Откат миграции"""
    c = conn.cursor()
    c.execute('DROP TABLE IF EXISTS analysis_tasks')
    conn.commit()
    print("✅ Откат миграции 008: Таблица analysis_tasks удалена")