"""
Модуль оптимизации затрат на API для снижения себестоимости
"""
import hashlib
import json
import sqlite3
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class CostOptimizer:
    """Класс для оптимизации затрат на API запросы"""
    
    def __init__(self, db_path='ai_study.db'):
        self.db_path = db_path
        self.init_cache_db()
    
    def init_cache_db(self):
        """Инициализация таблицы кэша"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        c.execute('''
            CREATE TABLE IF NOT EXISTS api_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content_hash TEXT UNIQUE NOT NULL,
                request_type TEXT NOT NULL,
                response_data TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP,
                usage_count INTEGER DEFAULT 1
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def get_content_hash(self, content: str, request_type: str) -> str:
        """Генерация хэша для контента"""
        combined = f"{request_type}:{content}"
        return hashlib.sha256(combined.encode()).hexdigest()
    
    def get_cached_response(self, content: str, request_type: str) -> Optional[Dict]:
        """Получение кэшированного ответа"""
        content_hash = self.get_content_hash(content, request_type)
        
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        c.execute('''
            SELECT response_data, expires_at FROM api_cache 
            WHERE content_hash = ? AND request_type = ?
            AND (expires_at IS NULL OR expires_at > datetime('now'))
        ''', (content_hash, request_type))
        
        result = c.fetchone()
        
        if result:
            # Увеличиваем счетчик использования
            c.execute('''
                UPDATE api_cache SET usage_count = usage_count + 1 
                WHERE content_hash = ? AND request_type = ?
            ''', (content_hash, request_type))
            conn.commit()
            
            logger.info(f"Cache hit for {request_type}: {content_hash[:8]}...")
            conn.close()
            return json.loads(result[0])
        
        conn.close()
        return None 
   
    def cache_response(self, content: str, request_type: str, response_data: Dict, 
                      cache_duration_hours: int = 24):
        """Кэширование ответа API"""
        content_hash = self.get_content_hash(content, request_type)
        expires_at = datetime.now() + timedelta(hours=cache_duration_hours)
        
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        try:
            c.execute('''
                INSERT OR REPLACE INTO api_cache 
                (content_hash, request_type, response_data, expires_at)
                VALUES (?, ?, ?, ?)
            ''', (content_hash, request_type, json.dumps(response_data), expires_at))
            
            conn.commit()
            logger.info(f"Cached response for {request_type}: {content_hash[:8]}...")
            
        except Exception as e:
            logger.error(f"Error caching response: {e}")
        finally:
            conn.close()
    
    def clean_expired_cache(self):
        """Очистка устаревшего кэша"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        c.execute('''
            DELETE FROM api_cache 
            WHERE expires_at IS NOT NULL AND expires_at < datetime('now')
        ''')
        
        deleted_count = c.rowcount
        conn.commit()
        conn.close()
        
        if deleted_count > 0:
            logger.info(f"Cleaned {deleted_count} expired cache entries")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Статистика кэша"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        # Общая статистика
        c.execute('SELECT COUNT(*), SUM(usage_count) FROM api_cache')
        total_entries, total_usage = c.fetchone()
        
        # Статистика по типам запросов
        c.execute('''
            SELECT request_type, COUNT(*), SUM(usage_count), AVG(usage_count)
            FROM api_cache GROUP BY request_type
        ''')
        by_type = c.fetchall()
        
        conn.close()
        
        return {
            'total_entries': total_entries or 0,
            'total_usage': total_usage or 0,
            'cache_hit_rate': (total_usage - total_entries) / max(total_usage, 1) * 100,
            'by_type': {
                row[0]: {
                    'entries': row[1],
                    'usage': row[2],
                    'avg_reuse': row[3]
                } for row in by_type
            }
        }

# Глобальный экземпляр оптимизатора
cost_optimizer = CostOptimizer()