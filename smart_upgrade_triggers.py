"""
Умные триггеры для мотивации апгрейдов подписки
"""
import sqlite3
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

@dataclass
class UpgradeOffer:
    """Предложение апгрейда"""
    title: str
    message: str
    discount: int  # Процент скидки
    urgency: str   # low, medium, high
    social_proof: str
    cta_text: str
    valid_until: datetime
    trigger_reason: str

class SmartUpgradeTriggers:
    """Система умных триггеров для апгрейдов"""
    
    def __init__(self, db_path: str = 'ai_study.db'):
        self.db_path = db_path
    
    def analyze_user_behavior(self, user_id: int) -> Dict:
        """Анализ поведения пользователя для определения готовности к апгрейду"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        # Получаем статистику пользователя за последние 30 дней
        since_date = datetime.now() - timedelta(days=30)
        
        # Основная активность
        c.execute('''
            SELECT 
                COUNT(*) as total_analyses,
                COUNT(DISTINCT DATE(created_at)) as active_days,
                AVG(LENGTH(full_text)) as avg_content_length
            FROM result 
            WHERE user_id = ? AND created_at >= ?
        ''', (user_id, since_date))
        
        activity = c.fetchone()
        
        # Использование AI чата
        c.execute('''
            SELECT COUNT(*) as chat_messages
            FROM chat_history 
            WHERE user_id = ? AND created_at >= ?
        ''', (user_id, since_date))
        
        chat_usage = c.fetchone()[0] or 0
        
        # Работа с флеш-картами
        c.execute('''
            SELECT 
                COUNT(*) as reviews,
                AVG(consecutive_correct) as avg_accuracy,
                COUNT(DISTINCT result_id) as unique_materials
            FROM user_progress 
            WHERE user_id = ? AND last_review >= ?
        ''', (user_id, since_date))
        
        flashcard_stats = c.fetchone()
        
        # Попытки превышения лимитов
        c.execute('''
            SELECT COUNT(*) as limit_hits
            FROM subscription_usage 
            WHERE user_id = ? AND created_at >= ? 
            AND resource_info LIKE '%limit_exceeded%'
        ''', (user_id, since_date))
        
        limit_hits = c.fetchone()[0] or 0
        
        # Текущий план и лимиты
        c.execute('''
            SELECT 
                subscription_type,
                monthly_analyses_used,
                ai_chat_messages_used,
                created_at as registration_date
            FROM users 
            WHERE id = ?
        ''', (user_id,))
        
        user_info = c.fetchone()
        
        conn.close()
        
        return {
            'total_analyses': activity[0] or 0,
            'active_days': activity[1] or 0,
            'avg_content_length': activity[2] or 0,
            'chat_messages': chat_usage,
            'flashcard_reviews': flashcard_stats[0] or 0,
            'flashcard_accuracy': flashcard_stats[1] or 0,
            'unique_materials': flashcard_stats[2] or 0,
            'limit_hits': limit_hits,
            'current_plan': user_info[0] if user_info else 'freemium',
            'analyses_used': user_info[1] if user_info else 0,
            'chat_used': user_info[2] if user_info else 0,
            'days_since_registration': (datetime.now() - datetime.fromisoformat(user_info[4])).days if user_info and len(user_info) > 4 and user_info[4] else 0
        }
    
    def calculate_upgrade_readiness_score(self, behavior: Dict) -> float:
        """Расчет готовности пользователя к апгрейду (0-1)"""
        score = 0.0
        
        # Активность использования (0-0.3)
        if behavior['active_days'] >= 20:
            score += 0.3
        elif behavior['active_days'] >= 10:
            score += 0.2
        elif behavior['active_days'] >= 5:
            score += 0.1
        
        # Интенсивность использования (0-0.25)
        if behavior['total_analyses'] >= 15:
            score += 0.25
        elif behavior['total_analyses'] >= 8:
            score += 0.15
        elif behavior['total_analyses'] >= 3:
            score += 0.1
        
        # Вовлеченность в обучение (0-0.2)
        if behavior['flashcard_reviews'] >= 50:
            score += 0.2
        elif behavior['flashcard_reviews'] >= 20:
            score += 0.15
        elif behavior['flashcard_reviews'] >= 5:
            score += 0.1
        
        # Использование AI чата (0-0.15)
        if behavior['chat_messages'] >= 30:
            score += 0.15
        elif behavior['chat_messages'] >= 10:
            score += 0.1
        elif behavior['chat_messages'] >= 3:
            score += 0.05
        
        # Попытки превышения лимитов (0-0.1)
        if behavior['limit_hits'] >= 5:
            score += 0.1
        elif behavior['limit_hits'] >= 2:
            score += 0.05
        
        return min(score, 1.0)
    
    def get_upgrade_triggers(self, user_id: int) -> List[UpgradeOffer]:
        """Получение списка триггеров для апгрейда"""
        behavior = self.analyze_user_behavior(user_id)
        readiness_score = self.calculate_upgrade_readiness_score(behavior)
        current_plan = behavior['current_plan']
        
        triggers = []
        
        # Триггеры для FREEMIUM → LITE
        if current_plan == 'freemium':
            triggers.extend(self._get_freemium_triggers(behavior, readiness_score))
        
        # Триггеры для LITE → STARTER
        elif current_plan == 'lite':
            triggers.extend(self._get_lite_triggers(behavior, readiness_score))
        
        # Триггеры для STARTER → BASIC
        elif current_plan == 'starter':
            triggers.extend(self._get_starter_triggers(behavior, readiness_score))
        
        # Триггеры для BASIC → PRO
        elif current_plan == 'basic':
            triggers.extend(self._get_basic_triggers(behavior, readiness_score))
        
        # Сортируем по приоритету (готовность * срочность)
        triggers.sort(key=lambda x: self._calculate_priority(x, readiness_score), reverse=True)
        
        return triggers[:3]  # Возвращаем топ-3 предложения
    
    def _get_freemium_triggers(self, behavior: Dict, readiness_score: float) -> List[UpgradeOffer]:
        """Триггеры для пользователей FREEMIUM"""
        triggers = []
        
        # Высокая активность
        if behavior['active_days'] >= 7 and behavior['total_analyses'] >= 2:
            triggers.append(UpgradeOffer(
                title="🚀 Вы активный пользователь!",
                message=f"За {behavior['active_days']} дней вы проанализировали {behavior['total_analyses']} документов. План LITE даст вам в 3 раза больше возможностей всего за ₽11/день!",
                discount=30,
                urgency="medium",
                social_proof="87% активных пользователей выбирают план LITE",
                cta_text="Попробовать LITE 3 дня бесплатно",
                valid_until=datetime.now() + timedelta(days=3),
                trigger_reason="high_activity"
            ))
        
        # Превышение лимитов
        if behavior['limit_hits'] >= 2:
            triggers.append(UpgradeOffer(
                title="⚡ Не ограничивайте себя!",
                message=f"Вы {behavior['limit_hits']} раз достигали лимитов. План LITE увеличит ваши возможности в 3 раза и откроет новые функции.",
                discount=40,
                urgency="high",
                social_proof="Пользователи LITE анализируют на 250% больше материалов",
                cta_text="Убрать ограничения за ₽79/неделя",
                valid_until=datetime.now() + timedelta(hours=24),
                trigger_reason="limit_exceeded"
            ))
        
        # Длительное использование без апгрейда
        if behavior['days_since_registration'] >= 14 and behavior['total_analyses'] >= 1:
            triggers.append(UpgradeOffer(
                title="🎁 Специальное предложение!",
                message=f"Вы с нами уже {behavior['days_since_registration']} дней! Как благодарность - скидка 50% на план LITE в первый месяц.",
                discount=50,
                urgency="low",
                social_proof="Только для лояльных пользователей",
                cta_text="Получить скидку 50%",
                valid_until=datetime.now() + timedelta(days=7),
                trigger_reason="loyalty_bonus"
            ))
        
        return triggers
    
    def _get_lite_triggers(self, behavior: Dict, readiness_score: float) -> List[UpgradeOffer]:
        """Триггеры для пользователей LITE"""
        triggers = []
        
        # Попытка использовать PPTX
        if behavior['limit_hits'] >= 1:
            triggers.append(UpgradeOffer(
                title="📊 Разблокируйте PPTX анализ!",
                message="Презентации содержат 40% больше визуальной информации. План STARTER откроет PPTX анализ и персональную аналитику.",
                discount=25,
                urgency="medium",
                social_proof="73% студентов используют PPTX анализ для лучшего понимания",
                cta_text="Открыть PPTX за ₹149/неделя",
                valid_until=datetime.now() + timedelta(days=2),
                trigger_reason="pptx_needed"
            ))
        
        # Высокое использование AI чата
        if behavior['chat_messages'] >= 40:
            triggers.append(UpgradeOffer(
                title="🤖 Нужно больше ответов от ИИ?",
                message=f"Вы задали {behavior['chat_messages']} вопросов! План STARTER даст вам 100 сообщений в месяц и персональную аналитику обучения.",
                discount=20,
                urgency="medium",
                social_proof="Студенты с расширенным чатом учатся на 60% эффективнее",
                cta_text="Получить больше ответов",
                valid_until=datetime.now() + timedelta(days=3),
                trigger_reason="chat_heavy_user"
            ))
        
        return triggers
    
    def _get_starter_triggers(self, behavior: Dict, readiness_score: float) -> List[UpgradeOffer]:
        """Триггеры для пользователей STARTER"""
        triggers = []
        
        # Высокое использование анализов
        if behavior['analyses_used'] >= 12:
            triggers.append(UpgradeOffer(
                title="📚 Готовы к большему?",
                message=f"Вы использовали {behavior['analyses_used']} из 15 анализов. План BASIC даст вам 40 анализов и расширенную аналитику.",
                discount=15,
                urgency="medium",
                social_proof="Топ-студенты анализируют 25+ документов в месяц",
                cta_text="Увеличить лимиты до 40",
                valid_until=datetime.now() + timedelta(days=5),
                trigger_reason="high_usage"
            ))
        
        # Активная работа с флеш-картами
        if behavior['flashcard_reviews'] >= 100 and behavior['flashcard_accuracy'] >= 0.8:
            triggers.append(UpgradeOffer(
                title="🎓 Вы прогрессируете!",
                message=f"Отличные результаты: {behavior['flashcard_reviews']} повторений с точностью {behavior['flashcard_accuracy']:.0%}! План BASIC откроет планы обучения и интеграции.",
                discount=20,
                urgency="low",
                social_proof="Студенты с планами обучения улучшают результаты на 45%",
                cta_text="Получить планы обучения",
                valid_until=datetime.now() + timedelta(days=7),
                trigger_reason="learning_progress"
            ))
        
        return triggers
    
    def _get_basic_triggers(self, behavior: Dict, readiness_score: float) -> List[UpgradeOffer]:
        """Триггеры для пользователей BASIC"""
        triggers = []
        
        # Достижение лимитов несколько раз
        if behavior['limit_hits'] >= 3:
            triggers.append(UpgradeOffer(
                title="🚀 Время для PRO!",
                message=f"Вы {behavior['limit_hits']} раз достигали лимитов. План PRO даст безлимитные возможности и API доступ.",
                discount=10,
                urgency="high",
                social_proof="PRO пользователи анализируют в 3 раза больше материалов",
                cta_text="Получить безлимит",
                valid_until=datetime.now() + timedelta(days=1),
                trigger_reason="power_user"
            ))
        
        # Корпоративное использование
        if behavior['total_analyses'] >= 30 and behavior['unique_materials'] >= 20:
            triggers.append(UpgradeOffer(
                title="💼 Корпоративные возможности",
                message="Ваша активность говорит о профессиональном использовании. PRO план включает API доступ и белый лейбл.",
                discount=15,
                urgency="low",
                social_proof="Выбор 89% корпоративных пользователей",
                cta_text="Получить корпоративные функции",
                valid_until=datetime.now() + timedelta(days=10),
                trigger_reason="corporate_usage"
            ))
        
        return triggers
    
    def _calculate_priority(self, offer: UpgradeOffer, readiness_score: float) -> float:
        """Расчет приоритета предложения"""
        urgency_weights = {'low': 0.3, 'medium': 0.6, 'high': 1.0}
        urgency_weight = urgency_weights.get(offer.urgency, 0.5)
        
        # Учитываем скидку как дополнительный фактор
        discount_factor = min(offer.discount / 100, 0.5)
        
        return readiness_score * urgency_weight + discount_factor
    
    def record_trigger_shown(self, user_id: int, trigger_reason: str, offer_details: Dict):
        """Запись показа триггера для аналитики"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        c.execute('''
            INSERT INTO upgrade_triggers_log 
            (user_id, trigger_reason, offer_details, shown_at)
            VALUES (?, ?, ?, ?)
        ''', (user_id, trigger_reason, json.dumps(offer_details), datetime.now()))
        
        conn.commit()
        conn.close()
    
    def record_trigger_action(self, user_id: int, trigger_reason: str, action: str):
        """Запись действия пользователя по триггеру"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        # Сначала находим ID последней записи
        c.execute('''
            SELECT id FROM upgrade_triggers_log 
            WHERE user_id = ? AND trigger_reason = ? AND action IS NULL
            ORDER BY shown_at DESC LIMIT 1
        ''', (user_id, trigger_reason))
        
        row = c.fetchone()
        if row:
            # Обновляем найденную запись
            c.execute('''
                UPDATE upgrade_triggers_log 
                SET action = ?, action_at = ?
                WHERE id = ?
            ''', (action, datetime.now(), row[0]))
        
        conn.commit()
        conn.close()
    
    def get_trigger_analytics(self, days: int = 30) -> Dict:
        """Аналитика эффективности триггеров"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        since_date = datetime.now() - timedelta(days=days)
        
        # Общая статистика
        c.execute('''
            SELECT 
                trigger_reason,
                COUNT(*) as shown_count,
                COUNT(CASE WHEN action = 'upgraded' THEN 1 END) as converted_count,
                COUNT(CASE WHEN action = 'dismissed' THEN 1 END) as dismissed_count,
                AVG(CASE WHEN action = 'upgraded' THEN 1.0 ELSE 0.0 END) as conversion_rate
            FROM upgrade_triggers_log 
            WHERE shown_at >= ?
            GROUP BY trigger_reason
            ORDER BY conversion_rate DESC
        ''', (since_date,))
        
        trigger_stats = []
        for row in c.fetchall():
            trigger_stats.append({
                'trigger_reason': row[0],
                'shown_count': row[1],
                'converted_count': row[2],
                'dismissed_count': row[3],
                'conversion_rate': row[4]
            })
        
        conn.close()
        
        return {
            'trigger_stats': trigger_stats,
            'period_days': days
        }

# Инициализация таблиц для логирования
def init_trigger_tables():
    """Инициализация таблиц для логирования триггеров"""
    conn = sqlite3.connect('ai_study.db')
    c = conn.cursor()
    
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
    
    # Индекс для быстрого поиска
    c.execute('CREATE INDEX IF NOT EXISTS idx_triggers_user_date ON upgrade_triggers_log(user_id, shown_at)')
    
    conn.commit()
    conn.close()

# Глобальный экземпляр
smart_triggers = SmartUpgradeTriggers()

# Инициализация при импорте
try:
    init_trigger_tables()
except Exception as e:
    logger.warning(f"Could not initialize trigger tables: {e}")