import sqlite3
from datetime import datetime, timedelta
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)

class UsageTracker:
    """Система отслеживания использования для разных тарифных планов"""
    
    PLAN_LIMITS = {
        'free': {
            'monthly_analyses': 3,
            'max_pdf_pages': 5,
            'max_video_minutes': 10,
            'max_flashcards': 10,
            'chat_messages': 0,
            'has_watermark': True
        },
        'basic': {
            'monthly_analyses': 25,
            'max_pdf_pages': 20,
            'max_video_minutes': 60,
            'max_flashcards': 50,
            'chat_messages': 50,
            'has_watermark': False
        },
        'pro': {
            'monthly_analyses': -1,  # Безлимит
            'max_pdf_pages': 100,
            'max_video_minutes': 120,
            'max_flashcards': -1,  # Безлимит
            'chat_messages': -1,  # Безлимит
            'has_watermark': False
        },
        'business': {
            'monthly_analyses': -1,  # Безлимит
            'max_pdf_pages': -1,  # Безлимит
            'max_video_minutes': -1,  # Безлимит
            'max_flashcards': -1,  # Безлимит
            'chat_messages': -1,  # Безлимит
            'has_watermark': False
        }
    }
    
    def __init__(self, db_path: str = 'ai_study.db'):
        self.db_path = db_path
        self.init_usage_tables()
    
    def init_usage_tables(self):
        """Инициализация таблиц для отслеживания использования"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        # Таблица пользователей и их планов
        c.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                plan TEXT DEFAULT 'free',
                subscription_start DATE,
                subscription_end DATE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Таблица использования
        c.execute('''
            CREATE TABLE IF NOT EXISTS usage_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                action_type TEXT NOT NULL,
                resource_used INTEGER DEFAULT 1,
                metadata TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')
        
        # Индексы для быстрого поиска
        c.execute('CREATE INDEX IF NOT EXISTS idx_usage_user_date ON usage_stats(user_id, created_at)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_usage_action ON usage_stats(action_type)')
        
        conn.commit()
        conn.close()
    
    def get_user_plan(self, user_id: int) -> str:
        """Получение плана пользователя"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        c.execute('SELECT plan FROM users WHERE id = ?', (user_id,))
        result = c.fetchone()
        conn.close()
        
        return result[0] if result else 'free'
    
    def get_monthly_usage(self, user_id: int, action_type: str = None) -> int:
        """Получение использования за текущий месяц"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        # Начало текущего месяца
        now = datetime.now()
        month_start = datetime(now.year, now.month, 1)
        
        if action_type:
            c.execute('''
                SELECT COALESCE(SUM(resource_used), 0)
                FROM usage_stats 
                WHERE user_id = ? AND action_type = ? AND created_at >= ?
            ''', (user_id, action_type, month_start))
        else:
            c.execute('''
                SELECT COALESCE(SUM(resource_used), 0)
                FROM usage_stats 
                WHERE user_id = ? AND created_at >= ?
            ''', (user_id, month_start))
        
        result = c.fetchone()
        conn.close()
        
        return result[0] if result else 0
    
    def can_perform_action(self, user_id: int, action_type: str, resource_amount: int = 1) -> Dict:
        """Проверка возможности выполнения действия"""
        plan = self.get_user_plan(user_id)
        limits = self.PLAN_LIMITS.get(plan, self.PLAN_LIMITS['free'])
        
        # Маппинг действий к лимитам
        action_limits = {
            'analysis': 'monthly_analyses',
            'chat_message': 'chat_messages',
            'pdf_pages': 'max_pdf_pages',
            'video_minutes': 'max_video_minutes'
        }
        
        limit_key = action_limits.get(action_type)
        if not limit_key:
            return {'allowed': True, 'reason': 'Unknown action type'}
        
        limit = limits.get(limit_key, 0)
        
        # Безлимитный план
        if limit == -1:
            return {'allowed': True, 'remaining': -1}
        
        # Проверка текущего использования
        if action_type in ['analysis', 'chat_message']:
            current_usage = self.get_monthly_usage(user_id, action_type)
        else:
            current_usage = 0  # Для разовых проверок (страницы, минуты)
        
        remaining = limit - current_usage
        allowed = remaining >= resource_amount
        
        return {
            'allowed': allowed,
            'remaining': remaining,
            'limit': limit,
            'current_usage': current_usage,
            'plan': plan
        }
    
    def record_usage(self, user_id: int, action_type: str, resource_used: int = 1, metadata: str = None):
        """Запись использования ресурса"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        c.execute('''
            INSERT INTO usage_stats (user_id, action_type, resource_used, metadata)
            VALUES (?, ?, ?, ?)
        ''', (user_id, action_type, resource_used, metadata))
        
        conn.commit()
        conn.close()
        
        logger.info(f"Recorded usage: user_id={user_id}, action={action_type}, amount={resource_used}")
    
    def get_usage_analytics(self, user_id: int) -> Dict:
        """Получение аналитики использования"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        # Использование за текущий месяц
        now = datetime.now()
        month_start = datetime(now.year, now.month, 1)
        
        c.execute('''
            SELECT action_type, SUM(resource_used) as total
            FROM usage_stats 
            WHERE user_id = ? AND created_at >= ?
            GROUP BY action_type
        ''', (user_id, month_start))
        
        monthly_usage = dict(c.fetchall())
        
        # Использование за все время
        c.execute('''
            SELECT action_type, SUM(resource_used) as total
            FROM usage_stats 
            WHERE user_id = ?
            GROUP BY action_type
        ''', (user_id,))
        
        total_usage = dict(c.fetchall())
        
        # Активность по дням (последние 30 дней)
        thirty_days_ago = now - timedelta(days=30)
        c.execute('''
            SELECT DATE(created_at) as date, COUNT(*) as actions
            FROM usage_stats 
            WHERE user_id = ? AND created_at >= ?
            GROUP BY DATE(created_at)
            ORDER BY date
        ''', (user_id, thirty_days_ago))
        
        daily_activity = dict(c.fetchall())
        
        conn.close()
        
        plan = self.get_user_plan(user_id)
        limits = self.PLAN_LIMITS.get(plan, self.PLAN_LIMITS['free'])
        
        return {
            'plan': plan,
            'limits': limits,
            'monthly_usage': monthly_usage,
            'total_usage': total_usage,
            'daily_activity': daily_activity,
            'month_start': month_start.isoformat()
        }
    
    def create_user(self, email: str, plan: str = 'free') -> int:
        """Создание нового пользователя"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        try:
            c.execute('''
                INSERT INTO users (email, plan, subscription_start)
                VALUES (?, ?, ?)
            ''', (email, plan, datetime.now()))
            
            user_id = c.lastrowid
            conn.commit()
            
            logger.info(f"Created user: {email} with plan {plan}")
            return user_id
            
        except sqlite3.IntegrityError:
            # Пользователь уже существует
            c.execute('SELECT id FROM users WHERE email = ?', (email,))
            user_id = c.fetchone()[0]
            return user_id
        finally:
            conn.close()
    
    def upgrade_user_plan(self, user_id: int, new_plan: str):
        """Обновление плана пользователя"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        c.execute('''
            UPDATE users 
            SET plan = ?, subscription_start = ?
            WHERE id = ?
        ''', (new_plan, datetime.now(), user_id))
        
        conn.commit()
        conn.close()
        
        logger.info(f"Upgraded user {user_id} to plan {new_plan}")

# Глобальный экземпляр трекера
usage_tracker = UsageTracker()