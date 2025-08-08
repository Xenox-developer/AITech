"""
Менеджер аналитики по планам подписки
"""
import sqlite3
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)

class AnalyticsManager:
    """Менеджер различных видов аналитики для планов подписки"""
    
    def __init__(self, db_path: str = 'ai_study.db'):
        self.db_path = db_path
    
    def get_learning_stats(self, user_id: int) -> Dict:
        """LITE план - Базовая статистика изучения"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        # Основная статистика
        c.execute('''
            SELECT 
                COUNT(*) as total_documents,
                COUNT(DISTINCT DATE(created_at)) as active_days,
                SUM(CASE WHEN file_type LIKE '%.pdf' THEN 1 ELSE 0 END) as pdf_count,
                SUM(CASE WHEN file_type LIKE '%.mp4' OR file_type LIKE '%.avi' OR file_type LIKE '%.mov' THEN 1 ELSE 0 END) as video_count,
                SUM(CASE WHEN file_type LIKE '%.pptx' OR file_type LIKE '%.ppt' THEN 1 ELSE 0 END) as pptx_count
            FROM result 
            WHERE user_id = ? AND created_at >= date('now', '-30 days')
        ''', (user_id,))
        
        stats = c.fetchone()
        
        # Активность по дням (последние 7 дней)
        c.execute('''
            SELECT 
                DATE(created_at) as date,
                COUNT(*) as documents
            FROM result 
            WHERE user_id = ? AND created_at >= date('now', '-7 days')
            GROUP BY DATE(created_at)
            ORDER BY date
        ''', (user_id,))
        
        daily_activity = [{'date': row[0], 'documents': row[1]} for row in c.fetchall()]
        
        # Общее время изучения (приблизительно)
        total_study_time = (stats[0] or 0) * 15  # 15 минут на документ в среднем
        
        conn.close()
        
        return {
            'type': 'learning_stats',
            'total_documents': stats[0] or 0,
            'active_days': stats[1] or 0,
            'file_types': {
                'pdf': stats[2] or 0,
                'video': stats[3] or 0,
                'pptx': stats[4] or 0
            },
            'daily_activity': daily_activity,
            'estimated_study_time': total_study_time,
            'period': '30 дней'
        }
    
    def get_learning_progress(self, user_id: int) -> Dict:
        """STARTER план - Прогресс обучения с персональными рекомендациями"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        # Базовая статистика
        basic_stats = self.get_learning_stats(user_id)
        
        # Прогресс по флеш-картам
        c.execute('''
            SELECT 
                COUNT(*) as total_reviews,
                AVG(consecutive_correct) as avg_accuracy,
                COUNT(CASE WHEN consecutive_correct >= 3 THEN 1 END) as mastered_cards,
                COUNT(DISTINCT result_id) as unique_materials
            FROM user_progress 
            WHERE user_id = ?
        ''', (user_id,))
        
        flashcard_stats = c.fetchone()
        
        # AI чат активность
        c.execute('''
            SELECT 
                COUNT(*) as total_messages,
                COUNT(DISTINCT result_id) as materials_discussed,
                AVG(LENGTH(user_message)) as avg_question_length
            FROM chat_history 
            WHERE user_id = ? AND created_at >= date('now', '-30 days')
        ''', (user_id,))
        
        chat_stats = c.fetchone()
        
        # Слабые места (материалы с низкой точностью)
        c.execute('''
            SELECT 
                r.filename,
                r.file_type,
                AVG(up.consecutive_correct) as avg_accuracy,
                COUNT(up.id) as review_count
            FROM result r
            JOIN user_progress up ON r.id = up.result_id
            WHERE r.user_id = ? AND up.consecutive_correct < 2
            GROUP BY r.id, r.filename, r.file_type
            ORDER BY avg_accuracy ASC, review_count DESC
            LIMIT 5
        ''', (user_id,))
        
        weak_areas = []
        for row in c.fetchall():
            weak_areas.append({
                'filename': row[0],
                'file_type': row[1],
                'accuracy': round(row[2], 1),
                'reviews': row[3]
            })
        
        # Рекомендации
        recommendations = self._generate_recommendations(user_id, flashcard_stats, chat_stats)
        
        # Прогресс по категориям
        mastery_rate = 0
        if flashcard_stats[0] and flashcard_stats[0] > 0:
            mastery_rate = (flashcard_stats[2] or 0) / flashcard_stats[0] * 100
        
        conn.close()
        
        # Копируем базовую статистику, но меняем тип
        result = dict(basic_stats)
        result['type'] = 'learning_progress'
        result.update({
            'flashcard_progress': {
                'total_reviews': flashcard_stats[0] or 0,
                'avg_accuracy': round(flashcard_stats[1] or 0, 1),
                'mastered_cards': flashcard_stats[2] or 0,
                'unique_materials': flashcard_stats[3] or 0,
                'mastery_rate': round(mastery_rate, 1)
            },
            'chat_activity': {
                'total_messages': chat_stats[0] or 0,
                'materials_discussed': chat_stats[1] or 0,
                'avg_question_length': round(chat_stats[2] or 0, 1)
            },
            'weak_areas': weak_areas,
            'recommendations': recommendations
        })
        
        return result
    
    def get_detailed_analytics(self, user_id: int) -> Dict:
        """BASIC план - Детальная аналитика с сравнениями"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        # Получаем прогресс обучения
        progress_data = self.get_learning_progress(user_id)
        
        # Сравнение с другими пользователями
        c.execute('''
            SELECT 
                AVG(monthly_analyses_used) as avg_analyses,
                AVG(ai_chat_messages_used) as avg_chat_messages
            FROM users 
            WHERE subscription_type IN ('starter', 'basic', 'pro')
            AND monthly_analyses_used > 0
        ''', ())
        
        avg_stats = c.fetchone()
        
        # Получаем статистику пользователя
        c.execute('''
            SELECT monthly_analyses_used, ai_chat_messages_used
            FROM users WHERE id = ?
        ''', (user_id,))
        
        user_stats = c.fetchone()
        
        # Прогнозирование результатов
        c.execute('''
            SELECT 
                DATE(created_at) as date,
                COUNT(*) as documents,
                AVG(CASE WHEN up.consecutive_correct IS NOT NULL 
                    THEN up.consecutive_correct ELSE 0 END) as avg_performance
            FROM result r
            LEFT JOIN user_progress up ON r.id = up.result_id
            WHERE r.user_id = ? AND r.created_at >= date('now', '-14 days')
            GROUP BY DATE(created_at)
            ORDER BY date
        ''', (user_id,))
        
        performance_trend = []
        for row in c.fetchall():
            performance_trend.append({
                'date': row[0],
                'documents': row[1],
                'performance': round(row[2], 2)
            })
        
        # Оптимальное время для повторений
        c.execute('''
            SELECT 
                strftime('%H', last_review) as hour,
                AVG(consecutive_correct) as avg_accuracy,
                COUNT(*) as review_count
            FROM user_progress 
            WHERE user_id = ? AND last_review IS NOT NULL
            GROUP BY strftime('%H', last_review)
            HAVING review_count >= 3
            ORDER BY avg_accuracy DESC
            LIMIT 3
        ''', (user_id,))
        
        optimal_hours = []
        for row in c.fetchall():
            optimal_hours.append({
                'hour': f"{row[0]}:00",
                'accuracy': round(row[1], 1),
                'reviews': row[2]
            })
        
        # Сравнение с пользователями
        user_analyses = user_stats[0] if user_stats and user_stats[0] else 0
        user_chat = user_stats[1] if user_stats and user_stats[1] else 0
        avg_analyses = avg_stats[0] if avg_stats and avg_stats[0] else 1
        avg_chat = avg_stats[1] if avg_stats and avg_stats[1] else 1
        
        comparison = {
            'analyses_vs_average': round((user_analyses / max(avg_analyses, 1) - 1) * 100, 1),
            'chat_vs_average': round((user_chat / max(avg_chat, 1) - 1) * 100, 1),
            'performance_percentile': self._calculate_percentile(user_id)
        }
        
        conn.close()
        
        # Копируем данные прогресса, но меняем тип
        result = dict(progress_data)
        result['type'] = 'detailed_analytics'
        result.update({
            'comparison': comparison,
            'performance_trend': performance_trend,
            'optimal_study_hours': optimal_hours,
            'predictions': self._generate_predictions(performance_trend),
            'study_optimization': self._generate_study_optimization(user_id)
        })
        
        return result
    
    def get_full_analytics(self, user_id: int) -> Dict:
        """PRO план - Полная аналитика с расширенными возможностями"""
        # Получаем детальную аналитику
        detailed_data = self.get_detailed_analytics(user_id)
        
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        # Расширенная статистика по времени (12 месяцев)
        c.execute('''
            SELECT 
                strftime('%Y-%m', created_at) as month,
                COUNT(*) as documents,
                COUNT(DISTINCT file_type) as file_types,
                AVG(LENGTH(summary)) as avg_summary_length,
                COUNT(DISTINCT DATE(created_at)) as active_days
            FROM result 
            WHERE user_id = ? AND created_at >= date('now', '-12 months')
            GROUP BY strftime('%Y-%m', created_at)
            ORDER BY month
        ''', (user_id,))
        
        monthly_trends = []
        for row in c.fetchall():
            monthly_trends.append({
                'month': row[0],
                'documents': row[1],
                'file_types': row[2],
                'avg_summary_length': round(row[3] or 0, 1),
                'active_days': row[4] or 0
            })
        
        # Детальная статистика по типам контента
        c.execute('''
            SELECT 
                file_type,
                COUNT(*) as count,
                AVG(LENGTH(summary)) as avg_summary_length,
                AVG(LENGTH(full_text)) as avg_content_length
            FROM result 
            WHERE user_id = ? AND created_at >= date('now', '-12 months')
            GROUP BY file_type
            ORDER BY count DESC
        ''', (user_id,))
        
        content_analysis = []
        for row in c.fetchall():
            content_analysis.append({
                'file_type': row[0],
                'count': row[1],
                'avg_summary_length': round(row[2] or 0, 1),
                'avg_content_length': round(row[3] or 0, 1)
            })
        
        # Анализ эффективности обучения по времени
        c.execute('''
            SELECT 
                strftime('%H', r.created_at) as hour,
                COUNT(*) as documents_processed,
                AVG(up.consecutive_correct) as avg_performance,
                COUNT(DISTINCT r.id) as unique_sessions
            FROM result r
            LEFT JOIN user_progress up ON r.id = up.result_id
            WHERE r.user_id = ? AND r.created_at >= date('now', '-90 days')
            GROUP BY strftime('%H', r.created_at)
            HAVING documents_processed >= 2
            ORDER BY avg_performance DESC
        ''', (user_id,))
        
        productivity_by_hour = []
        for row in c.fetchall():
            productivity_by_hour.append({
                'hour': f"{row[0]}:00",
                'documents': row[1],
                'performance': round(row[2] or 0, 2),
                'sessions': row[3]
            })
        
        # Анализ сложности материалов
        c.execute('''
            SELECT 
                CASE 
                    WHEN LENGTH(full_text) < 1000 THEN 'Простой'
                    WHEN LENGTH(full_text) < 5000 THEN 'Средний'
                    ELSE 'Сложный'
                END as complexity,
                COUNT(*) as count,
                AVG(up.consecutive_correct) as avg_mastery
            FROM result r
            LEFT JOIN user_progress up ON r.id = up.result_id
            WHERE r.user_id = ? AND r.created_at >= date('now', '-90 days')
            GROUP BY complexity
        ''', (user_id,))
        
        complexity_analysis = []
        for row in c.fetchall():
            complexity_analysis.append({
                'complexity': row[0],
                'count': row[1],
                'avg_mastery': round(row[2] or 0, 2)
            })
        
        # Персональная статистика (убрана командная статистика)
        team_stats = (0, 0, 0)  # Заглушка для совместимости
        
        # Статистика использования функций
        c.execute('''
            SELECT 
                COUNT(DISTINCT r.id) as total_analyses,
                COUNT(DISTINCT ch.id) as chat_interactions,
                COUNT(DISTINCT up.id) as flashcard_reviews,
                AVG(LENGTH(ch.user_message)) as avg_question_length
            FROM result r
            LEFT JOIN chat_history ch ON r.id = ch.result_id
            LEFT JOIN user_progress up ON r.id = up.result_id
            WHERE r.user_id = ? AND r.created_at >= date('now', '-30 days')
        ''', (user_id,))
        
        usage_stats = c.fetchone()
        
        # Прогнозы и рекомендации на основе данных
        learning_velocity = self._calculate_learning_velocity(user_id)
        retention_forecast = self._calculate_retention_forecast(user_id)
        
        conn.close()
        
        # Копируем детальные данные, но меняем тип
        result = dict(detailed_data)
        result['type'] = 'full_analytics'
        result.update({
            'monthly_trends': monthly_trends,
            'content_analysis': content_analysis,
            'productivity_by_hour': productivity_by_hour,
            'complexity_analysis': complexity_analysis,
            'learning_velocity': learning_velocity,
            'retention_forecast': retention_forecast,
            'team_statistics': {
                'team_size': team_stats[0] if team_stats else 0,
                'team_avg_analyses': round(team_stats[1] or 0, 1),
                'total_team_analyses': team_stats[2] if team_stats else 0
            },
            'usage_statistics': {
                'total_analyses': usage_stats[0] if usage_stats else 0,
                'chat_interactions': usage_stats[1] if usage_stats else 0,
                'flashcard_reviews': usage_stats[2] if usage_stats else 0,
                'avg_question_length': round(usage_stats[3] or 0, 1) if usage_stats else 0
            },

            'custom_dashboards': True,
            'advanced_filters': True,
            'pro_features': {
                'deep_content_analysis': True,
                'productivity_insights': True,
                'learning_velocity_tracking': True,
                'retention_forecasting': True,
                'complexity_analysis': True
            }
        })
        
        return result
    
    def _generate_recommendations(self, user_id: int, flashcard_stats: tuple, chat_stats: tuple) -> List[str]:
        """Генерация персональных рекомендаций"""
        recommendations = []
        
        total_reviews = flashcard_stats[0] or 0
        avg_accuracy = flashcard_stats[1] or 0
        mastered_cards = flashcard_stats[2] or 0
        
        if total_reviews == 0:
            recommendations.append("Начните работать с флеш-картами для лучшего запоминания")
        elif avg_accuracy < 1.5:
            recommendations.append("Уделите больше времени повторению сложных карточек")
        elif mastered_cards < total_reviews * 0.3:
            recommendations.append("Увеличьте частоту повторений для лучшего усвоения")
        
        chat_messages = chat_stats[0] or 0
        if chat_messages < 5:
            recommendations.append("Задавайте больше вопросов AI чату для глубокого понимания")
        elif chat_messages > 50:
            recommendations.append("Отличная активность в чате! Продолжайте исследовать материал")
        
        if not recommendations:
            recommendations.append("Отличный прогресс! Продолжайте в том же духе")
        
        return recommendations
    
    def _calculate_percentile(self, user_id: int) -> int:
        """Расчет процентиля производительности пользователя"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        # Получаем среднюю точность пользователя
        c.execute('''
            SELECT AVG(consecutive_correct) as user_accuracy
            FROM user_progress 
            WHERE user_id = ?
        ''', (user_id,))
        
        user_accuracy = c.fetchone()[0] or 0
        
        # Получаем точность всех пользователей
        c.execute('''
            SELECT AVG(consecutive_correct) as accuracy
            FROM user_progress 
            GROUP BY user_id
            HAVING COUNT(*) >= 5
        ''', ())
        
        all_accuracies = [row[0] for row in c.fetchall() if row[0] is not None]
        
        if not all_accuracies:
            return 50
        
        # Считаем процентиль
        better_count = sum(1 for acc in all_accuracies if user_accuracy > acc)
        percentile = int((better_count / len(all_accuracies)) * 100)
        
        conn.close()
        return percentile
    
    def _generate_predictions(self, performance_trend: List[Dict]) -> Dict:
        """Генерация прогнозов на основе тренда"""
        if len(performance_trend) < 3:
            return {
                'next_week_performance': 'Недостаточно данных',
                'improvement_trend': 'Нейтральный',
                'recommended_focus': 'Продолжайте активное изучение'
            }
        
        # Простой анализ тренда
        recent_performance = [p['performance'] for p in performance_trend[-5:]]
        avg_performance = sum(recent_performance) / len(recent_performance)
        
        if avg_performance > 2.0:
            trend = 'Отличный'
            prediction = 'Высокая производительность'
        elif avg_performance > 1.5:
            trend = 'Хороший'
            prediction = 'Стабильный прогресс'
        else:
            trend = 'Требует внимания'
            prediction = 'Рекомендуется больше повторений'
        
        return {
            'next_week_performance': prediction,
            'improvement_trend': trend,
            'recommended_focus': 'Повторение сложных тем' if avg_performance < 1.5 else 'Изучение нового материала'
        }
    
    def _generate_study_optimization(self, user_id: int) -> Dict:
        """Генерация рекомендаций по оптимизации обучения"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        # Анализ паттернов активности
        c.execute('''
            SELECT 
                strftime('%w', created_at) as day_of_week,
                COUNT(*) as activity_count,
                AVG(CASE WHEN up.consecutive_correct IS NOT NULL 
                    THEN up.consecutive_correct ELSE 0 END) as avg_performance
            FROM result r
            LEFT JOIN user_progress up ON r.id = up.result_id
            WHERE r.user_id = ? AND r.created_at >= date('now', '-30 days')
            GROUP BY strftime('%w', created_at)
            ORDER BY avg_performance DESC
        ''', (user_id,))
        
        day_performance = c.fetchall()
        
        best_day = None
        if day_performance:
            days = ['Воскресенье', 'Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота']
            best_day_num = day_performance[0][0]
            best_day = days[int(best_day_num)]
        
        conn.close()
        
        return {
            'optimal_study_day': best_day or 'Недостаточно данных',
            'recommended_session_length': '25-30 минут',
            'break_frequency': 'Каждые 45 минут',
            'review_schedule': 'Через 1, 3, 7 дней после изучения'
        }
    
    def _calculate_learning_velocity(self, user_id: int) -> Dict:
        """Расчет скорости обучения пользователя"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        # Анализ скорости освоения материала за последние 30 дней
        c.execute('''
            SELECT 
                DATE(r.created_at) as date,
                COUNT(DISTINCT r.id) as documents_processed,
                COUNT(DISTINCT up.id) as cards_reviewed,
                AVG(up.consecutive_correct) as avg_mastery
            FROM result r
            LEFT JOIN user_progress up ON r.id = up.result_id
            WHERE r.user_id = ? AND r.created_at >= date('now', '-30 days')
            GROUP BY DATE(r.created_at)
            ORDER BY date
        ''', (user_id,))
        
        daily_progress = c.fetchall()
        
        if len(daily_progress) < 7:
            conn.close()
            return {
                'documents_per_week': 0,
                'mastery_improvement_rate': 0,
                'learning_consistency': 'Недостаточно данных',
                'velocity_trend': 'Нейтральный'
            }
        
        # Расчет средних показателей
        total_documents = sum(row[1] for row in daily_progress)
        total_cards = sum(row[2] for row in daily_progress)
        avg_mastery = sum(row[3] or 0 for row in daily_progress) / len(daily_progress)
        
        # Анализ тренда (первая vs вторая половина периода)
        mid_point = len(daily_progress) // 2
        first_half_mastery = sum(row[3] or 0 for row in daily_progress[:mid_point]) / mid_point
        second_half_mastery = sum(row[3] or 0 for row in daily_progress[mid_point:]) / (len(daily_progress) - mid_point)
        
        improvement_rate = ((second_half_mastery - first_half_mastery) / max(first_half_mastery, 0.1)) * 100
        
        # Определение тренда
        if improvement_rate > 10:
            velocity_trend = 'Ускоряется'
        elif improvement_rate < -10:
            velocity_trend = 'Замедляется'
        else:
            velocity_trend = 'Стабильный'
        
        # Оценка консистентности (процент дней с активностью)
        active_days = len([row for row in daily_progress if row[1] > 0])
        consistency_rate = (active_days / 30) * 100
        
        if consistency_rate > 80:
            consistency = 'Высокая'
        elif consistency_rate > 50:
            consistency = 'Средняя'
        else:
            consistency = 'Низкая'
        
        conn.close()
        
        return {
            'documents_per_week': round(total_documents / 4.3, 1),  # 30 дней / 7 дней
            'cards_per_week': round(total_cards / 4.3, 1),
            'mastery_improvement_rate': round(improvement_rate, 1),
            'learning_consistency': consistency,
            'velocity_trend': velocity_trend,
            'avg_mastery_level': round(avg_mastery, 2)
        }
    
    def _calculate_retention_forecast(self, user_id: int) -> Dict:
        """Прогноз удержания знаний на основе паттернов повторений"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        # Анализ паттернов забывания
        c.execute('''
            SELECT 
                up.consecutive_correct,
                julianday('now') - julianday(up.last_review) as days_since_review,
                COUNT(*) as count
            FROM user_progress up
            WHERE up.user_id = ? AND up.last_review IS NOT NULL
            GROUP BY up.consecutive_correct, CAST(days_since_review AS INTEGER)
            ORDER BY days_since_review
        ''', (user_id,))
        
        retention_data = c.fetchall()
        
        if not retention_data:
            conn.close()
            return {
                'retention_rate_7_days': 0,
                'retention_rate_30_days': 0,
                'forgetting_curve': 'Недостаточно данных',
                'recommended_review_frequency': 'Ежедневно'
            }
        
        # Расчет кривой забывания
        retention_by_days = {}
        for mastery, days, count in retention_data:
            day_key = int(days)
            if day_key not in retention_by_days:
                retention_by_days[day_key] = {'total': 0, 'retained': 0}
            retention_by_days[day_key]['total'] += count
            if mastery >= 2:  # Считаем удержанным если точность >= 2
                retention_by_days[day_key]['retained'] += count
        
        # Прогноз на 7 и 30 дней
        retention_7_days = 0
        retention_30_days = 0
        
        if 7 in retention_by_days and retention_by_days[7]['total'] > 0:
            retention_7_days = (retention_by_days[7]['retained'] / retention_by_days[7]['total']) * 100
        
        if 30 in retention_by_days and retention_by_days[30]['total'] > 0:
            retention_30_days = (retention_by_days[30]['retained'] / retention_by_days[30]['total']) * 100
        
        # Определение кривой забывания
        if retention_7_days > 80:
            forgetting_curve = 'Медленная'
            review_frequency = 'Раз в неделю'
        elif retention_7_days > 60:
            forgetting_curve = 'Умеренная'
            review_frequency = 'Каждые 3-4 дня'
        else:
            forgetting_curve = 'Быстрая'
            review_frequency = 'Ежедневно'
        
        # Анализ материалов требующих повторения
        c.execute('''
            SELECT COUNT(*) as materials_need_review
            FROM user_progress up
            WHERE up.user_id = ? 
            AND up.consecutive_correct < 3
            AND julianday('now') - julianday(up.last_review) > 3
        ''', (user_id,))
        
        materials_need_review = c.fetchone()[0] or 0
        
        conn.close()
        
        return {
            'retention_rate_7_days': round(retention_7_days, 1),
            'retention_rate_30_days': round(retention_30_days, 1),
            'forgetting_curve': forgetting_curve,
            'recommended_review_frequency': review_frequency,
            'materials_need_review': materials_need_review,
            'retention_strength': 'Высокая' if retention_7_days > 75 else ('Средняя' if retention_7_days > 50 else 'Низкая')
        }

# Глобальный экземпляр
analytics_manager = AnalyticsManager()