"""
Модуль управления подписками и ограничениями
"""
import sqlite3
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class SubscriptionLimits:
    """Ограничения плана подписки"""
    monthly_analyses: int  # Количество анализов в месяц (-1 = безлимитно)
    max_pdf_pages: int     # Максимум страниц PDF (-1 = безлимитно)
    max_video_minutes: int # Максимум минут видео (-1 = безлимитно)
    max_video_uploads: int # Максимум загрузок видео в месяц (-1 = безлимитно)
    ai_chat_messages: int  # Сообщения в AI чате (-1 = безлимитно)
    pptx_support: bool     # Поддержка PPTX файлов
    features: list         # Доступные функции
    export_watermark: bool # Водяной знак при экспорте
    priority_processing: bool # Приоритетная обработка
    api_access: bool       # Доступ к API

# Конфигурация планов подписки - ОПТИМИЗИРОВАННАЯ 5-УРОВНЕВАЯ МОДЕЛЬ
SUBSCRIPTION_PLANS = {
    'freemium': SubscriptionLimits(
        monthly_analyses=3,  # Увеличено с 1 до 3 для лучшего знакомства
        max_pdf_pages=5,     # Увеличено с 3 до 5
        max_video_minutes=10, # Увеличено с 5 до 10
        max_video_uploads=1,
        ai_chat_messages=10,  # Увеличено с 2 до 10
        pptx_support=False,
        features=['basic_flashcards', 'basic_mind_maps_preview'],
        export_watermark=True,
        priority_processing=False,
        api_access=False
    ),
    'lite': SubscriptionLimits(  # НОВЫЙ ПЛАН - мягкий переход
        monthly_analyses=8,   # Себестоимость: ₽25/неделя, цена: ₽79/неделя (216% маржа)
        max_pdf_pages=15,
        max_video_minutes=20,
        max_video_uploads=3,
        ai_chat_messages=50,
        pptx_support=False,   # Пока без PPTX для мотивации апгрейда
        features=['basic_flashcards', 'full_mind_maps', 'learning_stats'],
        export_watermark=False,
        priority_processing=False,
        api_access=False
    ),
    'starter': SubscriptionLimits(
        monthly_analyses=15,  # Увеличено с 5 до 15
        max_pdf_pages=25,     # Увеличено с 10 до 25
        max_video_minutes=30, # Увеличено с 20 до 30
        max_video_uploads=5,  # Увеличено с 3 до 5
        ai_chat_messages=100, # Увеличено с 50 до 100
        pptx_support=True,    # ТЕПЕРЬ ДОСТУПЕН PPTX!
        features=['basic_flashcards', 'advanced_flashcards', 'interactive_mind_maps', 
                 'learning_progress', 'spaced_repetition'],
        export_watermark=False,
        priority_processing=False,
        api_access=False
    ),
    'basic': SubscriptionLimits(
        monthly_analyses=40,  # Увеличено с 20 до 40
        max_pdf_pages=50,     # Увеличено с 30 до 50
        max_video_minutes=60, # Уменьшено с 90 до 60 для четкой градации
        max_video_uploads=15, # Увеличено с 10 до 15
        ai_chat_messages=500, # Увеличено с 300 до 500
        pptx_support=True,
        features=['basic_flashcards', 'advanced_flashcards', 'interactive_mind_maps', 
                 'study_plans', 'advanced_analytics', 'calendar_integration', 'advanced_export'],
        export_watermark=False,
        priority_processing=False,
        api_access=False
    ),
    'pro': SubscriptionLimits(
        monthly_analyses=-1,
        max_pdf_pages=-1,
        max_video_minutes=-1,
        max_video_uploads=-1,
        ai_chat_messages=-1,
        pptx_support=True,
        features=['basic_flashcards', 'advanced_flashcards', 'interactive_mind_maps', 
                 'study_plans', 'advanced_analytics', 'calendar_integration', 'advanced_export',
                 'priority_processing', 'api_access', 'white_label', 'premium_support'],
        export_watermark=False,
        priority_processing=True,
        api_access=True
    )
}

class SubscriptionManager:
    """Менеджер подписок и ограничений"""
    
    def __init__(self):
        self.db_path = 'ai_study.db'
    
    def get_user_subscription(self, user_id: int) -> Dict:
        """Получение информации о подписке пользователя"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        c.execute('''
            SELECT subscription_type, subscription_start_date, subscription_end_date,
                   monthly_analyses_used, monthly_reset_date, total_pdf_pages_used,
                   total_video_minutes_used, ai_chat_messages_used, subscription_status
            FROM users WHERE id = ?
        ''', (user_id,))
        
        row = c.fetchone()
        conn.close()
        
        if not row:
            return None
        
        subscription_type = row[0] or 'starter'
        limits = SUBSCRIPTION_PLANS.get(subscription_type, SUBSCRIPTION_PLANS['starter'])
        
        return {
            'type': subscription_type,
            'limits': limits,
            'start_date': row[1],
            'end_date': row[2],
            'monthly_analyses_used': row[3] or 0,
            'monthly_reset_date': row[4],
            'total_pdf_pages_used': row[5] or 0,
            'total_video_minutes_used': row[6] or 0,
            'ai_chat_messages_used': row[7] or 0,
            'status': row[8] or 'active'
        }
    
    def check_analysis_limit(self, user_id: int) -> Tuple[bool, str]:
        """Проверка лимита на анализы"""
        subscription = self.get_user_subscription(user_id)
        if not subscription:
            return False, "Подписка не найдена"
        
        limits = subscription['limits']
        
        # Безлимитный план
        if limits.monthly_analyses == -1:
            return True, ""
        
        # Проверяем сброс месячного лимита
        self._reset_monthly_limits_if_needed(user_id)
        
        # Обновляем данные после возможного сброса
        subscription = self.get_user_subscription(user_id)
        used = subscription['monthly_analyses_used']
        
        if used >= limits.monthly_analyses:
            return False, f"Достигнут лимит анализов ({limits.monthly_analyses}/месяц). Обновите план для продолжения."
        
        return True, ""
    
    def check_pdf_pages_limit(self, user_id: int, pages_count: int) -> Tuple[bool, str]:
        """Проверка лимита на страницы PDF"""
        subscription = self.get_user_subscription(user_id)
        if not subscription:
            return False, "Подписка не найдена"
        
        limits = subscription['limits']
        
        # Безлимитный план
        if limits.max_pdf_pages == -1:
            return True, ""
        
        if pages_count > limits.max_pdf_pages:
            return False, f"Файл содержит {pages_count} страниц. Максимум для вашего плана: {limits.max_pdf_pages}"
        
        return True, ""
    
    def check_video_duration_limit(self, user_id: int, duration_minutes: int) -> Tuple[bool, str]:
        """Проверка лимита на длительность видео"""
        subscription = self.get_user_subscription(user_id)
        if not subscription:
            return False, "Подписка не найдена"
        
        limits = subscription['limits']
        
        # Безлимитный план
        if limits.max_video_minutes == -1:
            return True, ""
        
        if duration_minutes > limits.max_video_minutes:
            return False, f"Видео длится {duration_minutes} минут. Максимум для вашего плана: {limits.max_video_minutes} минут"
        
        return True, ""
    
    def check_video_uploads_limit(self, user_id: int) -> Tuple[bool, str]:
        """Проверка лимита на количество загрузок видео"""
        subscription = self.get_user_subscription(user_id)
        if not subscription:
            return False, "Подписка не найдена"
        
        limits = subscription['limits']
        
        # Безлимитный план
        if limits.max_video_uploads == -1:
            return True, ""
        
        # Проверяем сброс месячного лимита
        self._reset_monthly_limits_if_needed(user_id)
        
        # Получаем количество загруженных видео в этом месяце
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        try:
            c.execute('''
                SELECT monthly_video_uploads_used FROM users WHERE id = ?
            ''', (user_id,))
            
            row = c.fetchone()
            used = row[0] if row and row[0] else 0
            
            if used >= limits.max_video_uploads:
                return False, f"Достигнут лимит загрузок видео ({limits.max_video_uploads}/месяц). Обновите план для продолжения."
            
            return True, ""
            
        except Exception as e:
            logger.error(f"Error checking video uploads limit: {e}")
            return False, "Ошибка проверки лимита"
        finally:
            conn.close()
    
    def check_ai_chat_limit(self, user_id: int) -> Tuple[bool, str]:
        """Проверка лимита на AI чат"""
        subscription = self.get_user_subscription(user_id)
        if not subscription:
            return False, "Подписка не найдена"
        
        limits = subscription['limits']
        
        # Безлимитный план
        if limits.ai_chat_messages == -1:
            return True, ""
        
        used = subscription['ai_chat_messages_used']
        
        if used >= limits.ai_chat_messages:
            return False, f"Достигнут лимит сообщений в AI чате ({limits.ai_chat_messages}/месяц)"
        
        return True, ""
    
    def check_pptx_support(self, user_id: int) -> Tuple[bool, str]:
        """Проверка поддержки PPTX файлов"""
        subscription = self.get_user_subscription(user_id)
        if not subscription:
            return False, "Подписка не найдена"
        
        limits = subscription['limits']
        
        if not limits.pptx_support:
            return False, "Загрузка PPTX файлов доступна только в планах BASIC и PRO. Обновите план для продолжения."
        
        return True, ""
    
    def check_feature_access(self, user_id: int, feature: str) -> bool:
        """Проверка доступа к функции"""
        subscription = self.get_user_subscription(user_id)
        if not subscription:
            return False
        
        return feature in subscription['limits'].features
    
    def record_usage(self, user_id: int, usage_type: str, amount: int = 1, resource_info: str = None):
        """Запись использования ресурсов"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        try:
            # Записываем в историю использования
            c.execute('''
                INSERT INTO subscription_usage (user_id, usage_type, amount, resource_info)
                VALUES (?, ?, ?, ?)
            ''', (user_id, usage_type, amount, resource_info))
            
            # Обновляем счетчики пользователя
            if usage_type == 'analysis':
                c.execute('''
                    UPDATE users 
                    SET monthly_analyses_used = monthly_analyses_used + ?
                    WHERE id = ?
                ''', (amount, user_id))
            
            elif usage_type == 'pdf_pages':
                c.execute('''
                    UPDATE users 
                    SET total_pdf_pages_used = total_pdf_pages_used + ?
                    WHERE id = ?
                ''', (amount, user_id))
            
            elif usage_type == 'video_minutes':
                c.execute('''
                    UPDATE users 
                    SET total_video_minutes_used = total_video_minutes_used + ?
                    WHERE id = ?
                ''', (amount, user_id))
            
            elif usage_type == 'video_upload':
                c.execute('''
                    UPDATE users 
                    SET monthly_video_uploads_used = monthly_video_uploads_used + ?
                    WHERE id = ?
                ''', (amount, user_id))
            
            elif usage_type == 'ai_chat':
                c.execute('''
                    UPDATE users 
                    SET ai_chat_messages_used = ai_chat_messages_used + ?
                    WHERE id = ?
                ''', (amount, user_id))
            
            conn.commit()
            logger.info(f"Recorded usage for user {user_id}: {usage_type} = {amount}")
            
        except Exception as e:
            conn.rollback()
            logger.error(f"Error recording usage: {e}")
            raise
        finally:
            conn.close()
    
    def upgrade_subscription(self, user_id: int, new_plan: str) -> bool:
        """Обновление плана подписки"""
        if new_plan not in SUBSCRIPTION_PLANS:
            return False
        
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        try:
            # Получаем текущий план
            c.execute('SELECT subscription_type FROM users WHERE id = ?', (user_id,))
            current_plan = c.fetchone()
            current_plan = current_plan[0] if current_plan else 'starter'
            
            # Обновляем план
            c.execute('''
                UPDATE users 
                SET subscription_type = ?,
                    subscription_start_date = datetime('now'),
                    subscription_end_date = datetime('now', '+1 month'),
                    monthly_reset_date = datetime('now', '+1 month')
                WHERE id = ?
            ''', (new_plan, user_id))
            
            # Записываем в историю
            c.execute('''
                INSERT INTO subscription_history (user_id, old_plan, new_plan, change_reason)
                VALUES (?, ?, ?, ?)
            ''', (user_id, current_plan, new_plan, 'upgrade'))
            
            conn.commit()
            logger.info(f"User {user_id} upgraded from {current_plan} to {new_plan}")
            return True
            
        except Exception as e:
            conn.rollback()
            logger.error(f"Error upgrading subscription: {e}")
            return False
        finally:
            conn.close()
    
    def _reset_monthly_limits_if_needed(self, user_id: int):
        """Сброс месячных лимитов при необходимости"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        try:
            c.execute('''
                SELECT monthly_reset_date FROM users WHERE id = ?
            ''', (user_id,))
            
            row = c.fetchone()
            if not row or not row[0]:
                # Устанавливаем дату сброса, если её нет
                c.execute('''
                    UPDATE users 
                    SET monthly_reset_date = datetime('now', '+1 month')
                    WHERE id = ?
                ''', (user_id,))
                conn.commit()
                return
            
            reset_date = datetime.fromisoformat(row[0])
            
            if datetime.now() >= reset_date:
                # Сбрасываем месячные счетчики
                c.execute('''
                    UPDATE users 
                    SET monthly_analyses_used = 0,
                        ai_chat_messages_used = 0,
                        monthly_video_uploads_used = 0,
                        monthly_reset_date = datetime('now', '+1 month')
                    WHERE id = ?
                ''', (user_id,))
                
                conn.commit()
                logger.info(f"Reset monthly limits for user {user_id}")
                
        except Exception as e:
            logger.error(f"Error resetting monthly limits: {e}")
        finally:
            conn.close()
    
    def reset_monthly_limits(self, user_id: int):
        """Принудительный сброс месячных лимитов (для тестирования)"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        try:
            # Сбрасываем месячные счетчики
            c.execute('''
                UPDATE users 
                SET monthly_analyses_used = 0,
                    ai_chat_messages_used = 0,
                    monthly_video_uploads_used = 0,
                    monthly_reset_date = datetime('now', '+1 month')
                WHERE id = ?
            ''', (user_id,))
            
            conn.commit()
            logger.info(f"Manually reset monthly limits for user {user_id}")
            
        except Exception as e:
            logger.error(f"Error manually resetting monthly limits: {e}")
        finally:
            conn.close()
    
    def get_usage_stats(self, user_id: int) -> Dict:
        """Получение статистики использования"""
        subscription = self.get_user_subscription(user_id)
        if not subscription:
            return {}
        
        limits = subscription['limits']
        
        # Получаем статистику загрузок видео
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        try:
            c.execute('SELECT monthly_video_uploads_used FROM users WHERE id = ?', (user_id,))
            video_uploads_used = c.fetchone()
            video_uploads_used = video_uploads_used[0] if video_uploads_used and video_uploads_used[0] else 0
        except:
            video_uploads_used = 0
        finally:
            conn.close()

        stats = {
            'plan': subscription['type'],
            'status': subscription['status'],
            'analyses': {
                'used': subscription['monthly_analyses_used'],
                'limit': limits.monthly_analyses,
                'unlimited': limits.monthly_analyses == -1
            },
            'pdf_pages': {
                'limit': limits.max_pdf_pages,
                'unlimited': limits.max_pdf_pages == -1
            },
            'video_minutes': {
                'limit': limits.max_video_minutes,
                'unlimited': limits.max_video_minutes == -1
            },
            'video_uploads': {
                'used': video_uploads_used,
                'limit': limits.max_video_uploads,
                'unlimited': limits.max_video_uploads == -1
            },
            'ai_chat': {
                'used': subscription['ai_chat_messages_used'],
                'limit': limits.ai_chat_messages,
                'unlimited': limits.ai_chat_messages == -1
            },
            'features': limits.features,
            'reset_date': subscription['monthly_reset_date']
        }
        
        return stats

# Глобальный экземпляр менеджера
subscription_manager = SubscriptionManager()