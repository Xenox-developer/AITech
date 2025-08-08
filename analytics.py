import sqlite3
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)

class ElementAnalytics:
    """Система аналитики использования элементов интерфейса"""
    
    def __init__(self, db_path: str = 'ai_study.db'):
        self.db_path = db_path
        self.init_analytics_tables()
    
    def init_analytics_tables(self):
        """Инициализация таблиц для аналитики"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
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
        
        conn.commit()
        conn.close()
    
    def record_interaction(self, user_id: Optional[int], session_id: str, 
                          element_type: str, element_id: str, action_type: str,
                          page_url: str = None, page_title: str = None, 
                          metadata: Dict = None):
        """Запись взаимодействия с элементом"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        # Записываем взаимодействие
        c.execute('''
            INSERT INTO element_interactions 
            (user_id, session_id, element_type, element_id, action_type, 
             page_url, page_title, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, session_id, element_type, element_id, action_type,
              page_url, page_title, json.dumps(metadata) if metadata else None))
        
        # Обновляем популярность элемента
        c.execute('''
            INSERT OR REPLACE INTO element_popularity 
            (element_type, element_id, action_type, total_interactions, unique_users, last_updated)
            VALUES (?, ?, ?, 
                COALESCE((SELECT total_interactions FROM element_popularity 
                         WHERE element_type = ? AND element_id = ? AND action_type = ?), 0) + 1,
                (SELECT COUNT(DISTINCT user_id) FROM element_interactions 
                 WHERE element_type = ? AND element_id = ? AND action_type = ?),
                ?)
        ''', (element_type, element_id, action_type, 
              element_type, element_id, action_type,
              element_type, element_id, action_type,
              datetime.now()))
        
        # Обновляем счетчик взаимодействий в сессии
        c.execute('''
            UPDATE analytics_sessions 
            SET total_interactions = total_interactions + 1
            WHERE session_id = ?
        ''', (session_id,))
        
        conn.commit()
        conn.close()
        
        logger.info(f"Recorded interaction: {element_type}.{element_id} - {action_type}")
    
    def start_session(self, session_id: str, user_id: Optional[int] = None,
                     user_agent: str = None, ip_address: str = None):
        """Начало пользовательской сессии"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        c.execute('''
            INSERT OR IGNORE INTO analytics_sessions 
            (session_id, user_id, user_agent, ip_address)
            VALUES (?, ?, ?, ?)
        ''', (session_id, user_id, user_agent, ip_address))
        
        conn.commit()
        conn.close()
    
    def end_session(self, session_id: str):
        """Завершение пользовательской сессии"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        c.execute('''
            UPDATE analytics_sessions 
            SET end_time = ?
            WHERE session_id = ? AND end_time IS NULL
        ''', (datetime.now(), session_id))
        
        conn.commit()
        conn.close()
    
    def get_popular_elements(self, limit: int = 20, days: int = 30) -> List[Dict]:
        """Получение самых популярных элементов"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        since_date = datetime.now() - timedelta(days=days)
        
        c.execute('''
            SELECT 
                element_type,
                element_id,
                action_type,
                COUNT(*) as total_interactions,
                COUNT(DISTINCT user_id) as unique_users,
                COUNT(DISTINCT session_id) as unique_sessions
            FROM element_interactions 
            WHERE timestamp >= ?
            GROUP BY element_type, element_id, action_type
            ORDER BY total_interactions DESC
            LIMIT ?
        ''', (since_date, limit))
        
        results = []
        for row in c.fetchall():
            results.append({
                'element_type': row[0],
                'element_id': row[1],
                'action_type': row[2],
                'total_interactions': row[3],
                'unique_users': row[4],
                'unique_sessions': row[5]
            })
        
        conn.close()
        return results
    
    def get_element_usage_stats(self, element_type: str = None, 
                               element_id: str = None, days: int = 30) -> Dict:
        """Получение статистики использования элементов"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        since_date = datetime.now() - timedelta(days=days)
        
        # Базовый запрос
        where_conditions = ['timestamp >= ?']
        params = [since_date]
        
        if element_type:
            where_conditions.append('element_type = ?')
            params.append(element_type)
        
        if element_id:
            where_conditions.append('element_id = ?')
            params.append(element_id)
        
        where_clause = ' AND '.join(where_conditions)
        
        # Общая статистика
        c.execute(f'''
            SELECT 
                COUNT(*) as total_interactions,
                COUNT(DISTINCT user_id) as unique_users,
                COUNT(DISTINCT session_id) as unique_sessions,
                COUNT(DISTINCT DATE(timestamp)) as active_days
            FROM element_interactions 
            WHERE {where_clause}
        ''', params)
        
        stats = c.fetchone()
        
        # Статистика по дням
        c.execute(f'''
            SELECT 
                DATE(timestamp) as date,
                COUNT(*) as interactions,
                COUNT(DISTINCT user_id) as unique_users
            FROM element_interactions 
            WHERE {where_clause}
            GROUP BY DATE(timestamp)
            ORDER BY date
        ''', params)
        
        daily_stats = [{'date': row[0], 'interactions': row[1], 'unique_users': row[2]} 
                      for row in c.fetchall()]
        
        # Статистика по типам действий
        c.execute(f'''
            SELECT 
                action_type,
                COUNT(*) as interactions,
                COUNT(DISTINCT user_id) as unique_users
            FROM element_interactions 
            WHERE {where_clause}
            GROUP BY action_type
            ORDER BY interactions DESC
        ''', params)
        
        action_stats = [{'action_type': row[0], 'interactions': row[1], 'unique_users': row[2]} 
                       for row in c.fetchall()]
        
        # Статистика по элементам (если не указан конкретный)
        element_stats = []
        if not element_id:
            c.execute(f'''
                SELECT 
                    element_type,
                    element_id,
                    COUNT(*) as interactions,
                    COUNT(DISTINCT user_id) as unique_users
                FROM element_interactions 
                WHERE {where_clause}
                GROUP BY element_type, element_id
                ORDER BY interactions DESC
                LIMIT 50
            ''', params)
            
            element_stats = [{'element_type': row[0], 'element_id': row[1], 
                            'interactions': row[2], 'unique_users': row[3]} 
                           for row in c.fetchall()]
        
        conn.close()
        
        return {
            'total_interactions': stats[0] if stats else 0,
            'unique_users': stats[1] if stats else 0,
            'unique_sessions': stats[2] if stats else 0,
            'active_days': stats[3] if stats else 0,
            'daily_stats': daily_stats,
            'action_stats': action_stats,
            'element_stats': element_stats,
            'period_days': days
        }
    
    def get_user_behavior_patterns(self, user_id: int = None, days: int = 30) -> Dict:
        """Анализ паттернов поведения пользователей"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        since_date = datetime.now() - timedelta(days=days)
        
        # Если указан конкретный пользователь
        if user_id:
            where_clause = 'WHERE user_id = ? AND timestamp >= ?'
            params = [user_id, since_date]
        else:
            where_clause = 'WHERE timestamp >= ?'
            params = [since_date]
        
        # Самые активные пользователи
        c.execute(f'''
            SELECT 
                user_id,
                COUNT(*) as total_interactions,
                COUNT(DISTINCT element_type) as element_types_used,
                COUNT(DISTINCT DATE(timestamp)) as active_days,
                MIN(timestamp) as first_interaction,
                MAX(timestamp) as last_interaction
            FROM element_interactions 
            {where_clause}
            GROUP BY user_id
            ORDER BY total_interactions DESC
            LIMIT 20
        ''', params)
        
        active_users = []
        for row in c.fetchall():
            active_users.append({
                'user_id': row[0],
                'total_interactions': row[1],
                'element_types_used': row[2],
                'active_days': row[3],
                'first_interaction': row[4],
                'last_interaction': row[5]
            })
        
        # Популярные последовательности действий (упрощенная версия)
        c.execute(f'''
            SELECT 
                element_type || '.' || action_type as current_action,
                COUNT(*) as frequency
            FROM element_interactions 
            {where_clause}
            GROUP BY element_type, action_type
            ORDER BY frequency DESC
            LIMIT 20
        ''', params)
        
        sequences = []
        for row in c.fetchall():
            sequences.append({
                'action': row[0],
                'frequency': row[1]
            })
        
        conn.close()
        
        return {
            'active_users': active_users,
            'common_sequences': sequences,
            'period_days': days
        }
    
    def get_detailed_user_stats(self, days: int = 30) -> Dict:
        """Получение детальной статистики по пользователям"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        since_date = datetime.now() - timedelta(days=days)
        
        # Статистика по пользователям с их данными
        c.execute('''
            SELECT 
                u.id,
                u.username,
                u.email,
                u.created_at as registration_date,
                COUNT(ei.id) as total_interactions,
                COUNT(DISTINCT ei.session_id) as unique_sessions,
                COUNT(DISTINCT DATE(ei.timestamp)) as active_days,
                COUNT(DISTINCT ei.page_url) as pages_visited,
                MIN(ei.timestamp) as first_interaction,
                MAX(ei.timestamp) as last_interaction,
                COUNT(DISTINCT ei.element_type) as element_types_used
            FROM users u
            LEFT JOIN element_interactions ei ON u.id = ei.user_id 
                AND ei.timestamp >= ?
            GROUP BY u.id, u.username, u.email, u.created_at
            ORDER BY total_interactions DESC
        ''', (since_date,))
        
        user_stats = []
        for row in c.fetchall():
            user_stats.append({
                'user_id': row[0],
                'username': row[1],
                'email': row[2],
                'registration_date': row[3],
                'total_interactions': row[4],
                'unique_sessions': row[5],
                'active_days': row[6],
                'pages_visited': row[7],
                'first_interaction': row[8],
                'last_interaction': row[9],
                'element_types_used': row[10]
            })
        
        # Статистика по новым пользователям
        c.execute('''
            SELECT 
                DATE(created_at) as date,
                COUNT(*) as new_users
            FROM users 
            WHERE created_at >= ?
            GROUP BY DATE(created_at)
            ORDER BY date
        ''', (since_date,))
        
        new_users_daily = [{'date': row[0], 'new_users': row[1]} for row in c.fetchall()]
        
        # Активность пользователей по дням
        c.execute('''
            SELECT 
                DATE(ei.timestamp) as date,
                COUNT(DISTINCT ei.user_id) as active_users,
                COUNT(ei.id) as total_interactions
            FROM element_interactions ei
            WHERE ei.timestamp >= ? AND ei.user_id IS NOT NULL
            GROUP BY DATE(ei.timestamp)
            ORDER BY date
        ''', (since_date,))
        
        daily_activity = [{'date': row[0], 'active_users': row[1], 'interactions': row[2]} 
                         for row in c.fetchall()]
        
        # Топ страниц по пользователям
        c.execute('''
            SELECT 
                ei.page_url,
                ei.page_title,
                COUNT(DISTINCT ei.user_id) as unique_users,
                COUNT(ei.id) as total_interactions
            FROM element_interactions ei
            WHERE ei.timestamp >= ? AND ei.user_id IS NOT NULL
            GROUP BY ei.page_url, ei.page_title
            ORDER BY unique_users DESC
            LIMIT 20
        ''', (since_date,))
        
        popular_pages = []
        for row in c.fetchall():
            avg_interactions = round(row[3] / row[2], 2) if row[2] > 0 else 0
            popular_pages.append({
                'page_url': row[0],
                'page_title': row[1],
                'unique_users': row[2],
                'total_interactions': row[3],
                'avg_interactions_per_user': avg_interactions
            })
        
        # Общая статистика
        c.execute('''
            SELECT 
                COUNT(DISTINCT u.id) as total_users,
                COUNT(DISTINCT CASE WHEN ei.timestamp >= ? THEN u.id END) as active_users,
                COUNT(DISTINCT CASE WHEN u.created_at >= ? THEN u.id END) as new_users
            FROM users u
            LEFT JOIN element_interactions ei ON u.id = ei.user_id
        ''', (since_date, since_date))
        
        overview = c.fetchone()
        
        conn.close()
        
        return {
            'overview': {
                'total_users': overview[0] if overview else 0,
                'active_users': overview[1] if overview else 0,
                'new_users': overview[2] if overview else 0,
                'period_days': days
            },
            'user_stats': user_stats,
            'new_users_daily': new_users_daily,
            'daily_activity': daily_activity,
            'popular_pages': popular_pages
        }
    
    def get_user_engagement_metrics(self, days: int = 30) -> Dict:
        """Получение метрик вовлеченности пользователей"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        since_date = datetime.now() - timedelta(days=days)
        
        # Сегментация пользователей по активности
        c.execute('''
            SELECT 
                activity_segment,
                COUNT(*) as user_count
            FROM (
                SELECT 
                    u.id,
                    CASE 
                        WHEN COUNT(ei.id) = 0 THEN 'Неактивные'
                        WHEN COUNT(ei.id) BETWEEN 1 AND 10 THEN 'Низкая активность'
                        WHEN COUNT(ei.id) BETWEEN 11 AND 50 THEN 'Средняя активность'
                        WHEN COUNT(ei.id) BETWEEN 51 AND 100 THEN 'Высокая активность'
                        ELSE 'Очень высокая активность'
                    END as activity_segment
                FROM users u
                LEFT JOIN element_interactions ei ON u.id = ei.user_id 
                    AND ei.timestamp >= ?
                GROUP BY u.id
            ) user_segments
            GROUP BY activity_segment
            ORDER BY user_count DESC
        ''', (since_date,))
        
        activity_segments = [{'segment': row[0], 'user_count': row[1]} for row in c.fetchall()]
        
        # Время сессий пользователей
        c.execute('''
            SELECT 
                u.username,
                s.session_id,
                s.start_time,
                s.end_time,
                s.total_interactions,
                CASE 
                    WHEN s.end_time IS NOT NULL 
                    THEN (julianday(s.end_time) - julianday(s.start_time)) * 24 * 60
                    ELSE NULL 
                END as session_duration_minutes
            FROM analytics_sessions s
            JOIN users u ON s.user_id = u.id
            WHERE s.start_time >= ?
            ORDER BY s.start_time DESC
            LIMIT 50
        ''', (since_date,))
        
        recent_sessions = []
        for row in c.fetchall():
            recent_sessions.append({
                'username': row[0],
                'session_id': row[1],
                'start_time': row[2],
                'end_time': row[3],
                'total_interactions': row[4],
                'duration_minutes': round(row[5], 2) if row[5] else None
            })
        
        # Средние метрики
        c.execute('''
            SELECT 
                AVG(CAST(interactions_per_user AS FLOAT)) as avg_interactions,
                AVG(CAST(sessions_per_user AS FLOAT)) as avg_sessions,
                AVG(CAST(pages_per_user AS FLOAT)) as avg_pages
            FROM (
                SELECT 
                    u.id,
                    COUNT(ei.id) as interactions_per_user,
                    COUNT(DISTINCT ei.session_id) as sessions_per_user,
                    COUNT(DISTINCT ei.page_url) as pages_per_user
                FROM users u
                LEFT JOIN element_interactions ei ON u.id = ei.user_id 
                    AND ei.timestamp >= ?
                GROUP BY u.id
            ) user_metrics
        ''', (since_date,))
        
        averages = c.fetchone()
        
        conn.close()
        
        return {
            'activity_segments': activity_segments,
            'recent_sessions': recent_sessions,
            'averages': {
                'interactions_per_user': round(averages[0], 2) if averages[0] else 0,
                'sessions_per_user': round(averages[1], 2) if averages[1] else 0,
                'pages_per_user': round(averages[2], 2) if averages[2] else 0
            },
            'period_days': days
        }
    
    def get_page_analytics(self, page_url: str = None, days: int = 30) -> Dict:
        """Аналитика по страницам"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        since_date = datetime.now() - timedelta(days=days)
        
        if page_url:
            where_clause = 'WHERE page_url = ? AND timestamp >= ?'
            params = [page_url, since_date]
        else:
            where_clause = 'WHERE timestamp >= ?'
            params = [since_date]
        
        # Статистика по страницам
        c.execute(f'''
            SELECT 
                page_url,
                page_title,
                COUNT(*) as total_interactions,
                COUNT(DISTINCT user_id) as unique_users,
                COUNT(DISTINCT session_id) as unique_sessions
            FROM element_interactions 
            {where_clause}
            GROUP BY page_url, page_title
            ORDER BY total_interactions DESC
        ''', params)
        
        page_stats = []
        for row in c.fetchall():
            page_stats.append({
                'page_url': row[0],
                'page_title': row[1],
                'total_interactions': row[2],
                'unique_users': row[3],
                'unique_sessions': row[4]
            })
        
        conn.close()
        
        return {
            'page_stats': page_stats,
            'period_days': days
        }

# Глобальный экземпляр аналитики
element_analytics = ElementAnalytics()