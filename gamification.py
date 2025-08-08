"""
Система геймификации для AI Study
"""
import sqlite3
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

@dataclass
class Achievement:
    """Достижение пользователя"""
    id: str
    title: str
    description: str
    icon: str
    category: str
    xp_reward: int
    unlock_condition: Dict
    rarity: str  # common, rare, epic, legendary

@dataclass
class UserLevel:
    """Уровень пользователя"""
    level: int
    title: str
    xp_required: int
    xp_total: int
    benefits: List[str]
    badge_color: str

# Конфигурация системы опыта
XP_ACTIONS = {
    'document_analysis': 50,      # Анализ документа
    'flashcard_review': 10,       # Повторение карточки
    'ai_chat_message': 5,         # Сообщение в AI чате
    'mind_map_creation': 30,      # Создание mind map
    'streak_day': 20,             # День подряд активности
    'perfect_session': 100,       # Идеальная сессия повторений (95%+)
    'share_content': 25,          # Поделиться результатом
    'feedback_given': 15,         # Оставить отзыв
    'referral_signup': 200,       # Привести друга
    'course_completion': 500,     # Завершение курса
    'first_pptx': 75,            # Первый PPTX анализ
    'video_analysis': 60,        # Анализ видео
    'long_study_session': 40,    # Сессия изучения 30+ минут
    'weekly_goal_complete': 150, # Выполнение недельной цели
}

# Система уровней
LEVEL_SYSTEM = {
    1: UserLevel(1, "🌱 Новичок", 0, 100, ["Доступ к базовым функциям"], "secondary"),
    5: UserLevel(5, "📚 Ученик", 500, 800, ["Бонус +1 анализ в месяц"], "info"),
    10: UserLevel(10, "🚀 Исследователь", 1500, 1200, ["Скидка 10% на LITE план"], "primary"),
    15: UserLevel(15, "🎓 Студент", 3000, 1500, ["Бесплатный PPTX анализ"], "warning"),
    25: UserLevel(25, "🔬 Аналитик", 6000, 2000, ["Скидка 15% на STARTER план"], "success"),
    35: UserLevel(35, "🧠 Эксперт", 10000, 2500, ["Персональная статистика"], "danger"),
    50: UserLevel(50, "⭐ Мастер", 16000, 3000, ["Скидка 20% на BASIC план"], "dark"),
    75: UserLevel(75, "👑 Гуру", 25000, 4000, ["Эксклюзивные функции"], "warning"),
    100: UserLevel(100, "🏆 Легенда", 40000, 5000, ["Максимальные привилегии"], "success"),
}

# Достижения
ACHIEVEMENTS = {
    # Категория: Анализ документов
    'first_analysis': Achievement(
        'first_analysis', '🔍 Первые шаги', 'Проанализируйте первый документ',
        'fas fa-search', 'analysis', 50, {'analyses_count': 1}, 'common'
    ),
    'pdf_lover': Achievement(
        'pdf_lover', '📄 Книжный червь', 'Проанализируйте 10 PDF файлов',
        'fas fa-file-pdf', 'analysis', 200, {'pdf_analyses': 10}, 'rare'
    ),
    'video_master': Achievement(
        'video_master', '🎬 Киноман', 'Проанализируйте 5 видео',
        'fas fa-video', 'analysis', 300, {'video_analyses': 5}, 'rare'
    ),
    'pptx_expert': Achievement(
        'pptx_expert', '📊 Презентатор', 'Проанализируйте 10 PPTX файлов',
        'fas fa-file-powerpoint', 'analysis', 400, {'pptx_analyses': 10}, 'epic'
    ),
    'analysis_machine': Achievement(
        'analysis_machine', '🚀 Машина анализа', 'Проанализируйте 100 документов',
        'fas fa-rocket', 'analysis', 1000, {'analyses_count': 100}, 'legendary'
    ),
    
    # Категория: Обучение
    'memory_champion': Achievement(
        'memory_champion', '🧠 Чемпион памяти', 'Повторите 100 карточек',
        'fas fa-brain', 'learning', 300, {'flashcard_reviews': 100}, 'rare'
    ),
    'speed_learner': Achievement(
        'speed_learner', '⚡ Скоростное обучение', 'Изучите 50 карточек за день',
        'fas fa-bolt', 'learning', 250, {'daily_flashcards': 50}, 'epic'
    ),
    'streak_master': Achievement(
        'streak_master', '🔥 Мастер серий', '7 дней подряд повторений',
        'fas fa-fire', 'learning', 350, {'streak_days': 7}, 'epic'
    ),
    'perfect_student': Achievement(
        'perfect_student', '🎯 Идеальный студент', '95% правильных ответов в сессии',
        'fas fa-bullseye', 'learning', 200, {'session_accuracy': 0.95}, 'rare'
    ),
    'knowledge_seeker': Achievement(
        'knowledge_seeker', '📚 Искатель знаний', 'Изучите материалы 5 разных предметов',
        'fas fa-graduation-cap', 'learning', 400, {'subjects_studied': 5}, 'epic'
    ),
    
    # Категория: Социальная активность
    'first_share': Achievement(
        'first_share', '🎁 Щедрый', 'Поделитесь первым результатом',
        'fas fa-share', 'social', 100, {'shares_count': 1}, 'common'
    ),
    'influencer': Achievement(
        'influencer', '🌟 Влиятельный', 'Пригласите 5 друзей',
        'fas fa-users', 'social', 500, {'referrals_count': 5}, 'legendary'
    ),
    'helpful': Achievement(
        'helpful', '💬 Помощник', 'Оставьте 10 отзывов',
        'fas fa-comment', 'social', 200, {'reviews_count': 10}, 'rare'
    ),
    
    # Категория: Мастерство
    'mind_mapper': Achievement(
        'mind_mapper', '🗺️ Картограф знаний', 'Создайте 20 mind maps',
        'fas fa-project-diagram', 'mastery', 400, {'mind_maps_created': 20}, 'epic'
    ),
    'ai_whisperer': Achievement(
        'ai_whisperer', '🤖 Заклинатель ИИ', 'Задайте 100 вопросов AI чату',
        'fas fa-robot', 'mastery', 300, {'ai_messages': 100}, 'rare'
    ),
    'study_planner': Achievement(
        'study_planner', '📅 Планировщик', 'Создайте 5 планов обучения',
        'fas fa-calendar-alt', 'mastery', 350, {'study_plans_created': 5}, 'epic'
    ),
}

class GamificationSystem:
    """Система геймификации"""
    
    def __init__(self, db_path: str = 'ai_study.db'):
        self.db_path = db_path
        self.init_gamification_tables()
    
    def init_gamification_tables(self):
        """Инициализация таблиц геймификации"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        # Таблица пользовательского прогресса
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
        
        # Индексы для быстрого поиска
        c.execute('CREATE INDEX IF NOT EXISTS idx_xp_history_user ON xp_history(user_id, created_at)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_achievements_user ON user_achievements(user_id)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_challenges_user_week ON weekly_challenges(user_id, week_start)')
        
        conn.commit()
        conn.close()
    
    def get_user_gamification_data(self, user_id: int) -> Dict:
        """Получение данных геймификации пользователя"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        # Получаем или создаем запись пользователя
        c.execute('SELECT * FROM user_gamification WHERE user_id = ?', (user_id,))
        user_data = c.fetchone()
        
        if not user_data:
            # Создаем новую запись
            c.execute('''
                INSERT INTO user_gamification (user_id, level, total_xp)
                VALUES (?, 1, 0)
            ''', (user_id,))
            conn.commit()
            user_data = (user_id, 1, 0, 0, 0, None, '[]', '{}', datetime.now(), datetime.now())
        
        # Получаем достижения пользователя
        c.execute('SELECT achievement_id, unlocked_at FROM user_achievements WHERE user_id = ?', (user_id,))
        achievements = c.fetchall()
        
        # Получаем недавнюю историю XP
        c.execute('''
            SELECT action_type, xp_gained, description, created_at
            FROM xp_history 
            WHERE user_id = ? 
            ORDER BY created_at DESC 
            LIMIT 10
        ''', (user_id,))
        recent_xp = c.fetchall()
        
        conn.close()
        
        # Определяем текущий уровень
        current_level_info = self.get_level_info(user_data[2])  # total_xp
        
        return {
            'user_id': user_data[0],
            'level': user_data[1],
            'total_xp': user_data[2],
            'current_streak': user_data[3],
            'longest_streak': user_data[4],
            'last_activity_date': user_data[5],
            'achievements': [{'id': a[0], 'unlocked_at': a[1]} for a in achievements],
            'recent_xp': [{'action': r[0], 'xp': r[1], 'description': r[2], 'date': r[3]} for r in recent_xp],
            'level_info': current_level_info,
            'achievements_count': len(achievements),
            'next_level_xp': current_level_info['xp_to_next'] if current_level_info else 0
        }
    
    def get_level_info(self, total_xp: int) -> Dict:
        """Получение информации об уровне по XP"""
        current_level = 1
        current_level_data = LEVEL_SYSTEM[1]
        
        # Находим текущий уровень
        for level, data in sorted(LEVEL_SYSTEM.items()):
            if total_xp >= data.xp_required:
                current_level = level
                current_level_data = data
            else:
                break
        
        # Находим следующий уровень
        next_level = None
        next_level_data = None
        for level, data in sorted(LEVEL_SYSTEM.items()):
            if level > current_level:
                next_level = level
                next_level_data = data
                break
        
        xp_to_next = next_level_data.xp_required - total_xp if next_level_data else 0
        progress_percent = 0
        if next_level_data:
            level_xp_range = next_level_data.xp_required - current_level_data.xp_required
            current_progress = total_xp - current_level_data.xp_required
            progress_percent = min(100, (current_progress / level_xp_range) * 100) if level_xp_range > 0 else 100
        
        return {
            'current_level': current_level,
            'current_title': current_level_data.title,
            'current_benefits': current_level_data.benefits,
            'badge_color': current_level_data.badge_color,
            'next_level': next_level,
            'next_title': next_level_data.title if next_level_data else "Максимальный уровень",
            'xp_to_next': max(0, xp_to_next),
            'progress_percent': progress_percent,
            'total_xp': total_xp
        }
    
    def award_xp(self, user_id: int, action_type: str, description: str = None, metadata: Dict = None) -> Dict:
        """Начисление XP за действие"""
        if action_type not in XP_ACTIONS:
            logger.warning(f"Unknown action type: {action_type}")
            return {'success': False, 'error': 'Unknown action type'}
        
        xp_amount = XP_ACTIONS[action_type]
        
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        try:
            # Получаем текущие данные пользователя
            c.execute('SELECT level, total_xp FROM user_gamification WHERE user_id = ?', (user_id,))
            user_data = c.fetchone()
            
            if not user_data:
                # Создаем запись если её нет
                c.execute('''
                    INSERT INTO user_gamification (user_id, level, total_xp)
                    VALUES (?, 1, ?)
                ''', (user_id, xp_amount))
                old_level = 1
                new_total_xp = xp_amount
            else:
                old_level, old_xp = user_data
                new_total_xp = old_xp + xp_amount
                
                # Обновляем XP
                c.execute('''
                    UPDATE user_gamification 
                    SET total_xp = ?, updated_at = ?
                    WHERE user_id = ?
                ''', (new_total_xp, datetime.now(), user_id))
            
            # Записываем в историю XP
            c.execute('''
                INSERT INTO xp_history (user_id, action_type, xp_gained, description, metadata_json)
                VALUES (?, ?, ?, ?, ?)
            ''', (user_id, action_type, xp_amount, description, json.dumps(metadata) if metadata else None))
            
            # Проверяем повышение уровня
            old_level_info = self.get_level_info(new_total_xp - xp_amount)
            new_level_info = self.get_level_info(new_total_xp)
            
            level_up = new_level_info['current_level'] > old_level_info['current_level']
            
            if level_up:
                # Обновляем уровень в базе
                c.execute('''
                    UPDATE user_gamification 
                    SET level = ?
                    WHERE user_id = ?
                ''', (new_level_info['current_level'], user_id))
            
            # Проверяем новые достижения
            new_achievements = self.check_achievements(user_id, c)
            
            conn.commit()
            
            return {
                'success': True,
                'xp_gained': xp_amount,
                'total_xp': new_total_xp,
                'level_up': level_up,
                'new_level': new_level_info['current_level'] if level_up else None,
                'new_level_title': new_level_info['current_title'] if level_up else None,
                'new_achievements': new_achievements,
                'level_info': new_level_info
            }
            
        except Exception as e:
            conn.rollback()
            logger.error(f"Error awarding XP: {e}")
            return {'success': False, 'error': str(e)}
        finally:
            conn.close()
    
    def check_achievements(self, user_id: int, cursor) -> List[Dict]:
        """Проверка и разблокировка достижений"""
        new_achievements = []
        
        # Получаем уже разблокированные достижения
        cursor.execute('SELECT achievement_id FROM user_achievements WHERE user_id = ?', (user_id,))
        unlocked = set(row[0] for row in cursor.fetchall())
        
        # Получаем статистику пользователя для проверки условий
        stats = self.get_user_stats_for_achievements(user_id, cursor)
        
        for achievement_id, achievement in ACHIEVEMENTS.items():
            if achievement_id in unlocked:
                continue
            
            # Проверяем условие достижения
            if self.check_achievement_condition(achievement.unlock_condition, stats):
                # Разблокируем достижение
                cursor.execute('''
                    INSERT INTO user_achievements (user_id, achievement_id)
                    VALUES (?, ?)
                ''', (user_id, achievement_id))
                
                # Начисляем XP за достижение
                cursor.execute('''
                    INSERT INTO xp_history (user_id, action_type, xp_gained, description)
                    VALUES (?, 'achievement_unlocked', ?, ?)
                ''', (user_id, achievement.xp_reward, f'Достижение: {achievement.title}'))
                
                # Обновляем общий XP
                cursor.execute('''
                    UPDATE user_gamification 
                    SET total_xp = total_xp + ?
                    WHERE user_id = ?
                ''', (achievement.xp_reward, user_id))
                
                new_achievements.append({
                    'id': achievement_id,
                    'title': achievement.title,
                    'description': achievement.description,
                    'icon': achievement.icon,
                    'xp_reward': achievement.xp_reward,
                    'rarity': achievement.rarity
                })
        
        return new_achievements
    
    def get_user_stats_for_achievements(self, user_id: int, cursor) -> Dict:
        """Получение статистики пользователя для проверки достижений"""
        stats = {}
        
        # Общее количество анализов
        cursor.execute('SELECT COUNT(*) FROM result WHERE user_id = ?', (user_id,))
        stats['analyses_count'] = cursor.fetchone()[0]
        
        # Анализы по типам файлов
        cursor.execute('SELECT file_type, COUNT(*) FROM result WHERE user_id = ? GROUP BY file_type', (user_id,))
        file_types = cursor.fetchall()
        for file_type, count in file_types:
            if file_type == 'pdf':
                stats['pdf_analyses'] = count
            elif file_type == 'video':
                stats['video_analyses'] = count
            elif file_type == 'pptx':
                stats['pptx_analyses'] = count
        
        # Повторения флеш-карт
        cursor.execute('SELECT COUNT(*) FROM user_progress WHERE user_id = ?', (user_id,))
        stats['flashcard_reviews'] = cursor.fetchone()[0]
        
        # AI сообщения
        cursor.execute('SELECT COUNT(*) FROM chat_history WHERE user_id = ?', (user_id,))
        stats['ai_messages'] = cursor.fetchone()[0]
        
        # Текущая серия
        cursor.execute('SELECT current_streak FROM user_gamification WHERE user_id = ?', (user_id,))
        streak_data = cursor.fetchone()
        stats['streak_days'] = streak_data[0] if streak_data else 0
        
        return stats
    
    def check_achievement_condition(self, condition: Dict, stats: Dict) -> bool:
        """Проверка условия достижения"""
        for key, required_value in condition.items():
            if key not in stats:
                return False
            if stats[key] < required_value:
                return False
        return True
    
    def update_daily_streak(self, user_id: int):
        """Обновление ежедневной серии активности"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        try:
            today = datetime.now().date()
            
            c.execute('SELECT current_streak, longest_streak, last_activity_date FROM user_gamification WHERE user_id = ?', (user_id,))
            data = c.fetchone()
            
            if not data:
                # Создаем запись
                c.execute('''
                    INSERT INTO user_gamification (user_id, current_streak, longest_streak, last_activity_date)
                    VALUES (?, 1, 1, ?)
                ''', (user_id, today))
                conn.commit()
                return {'streak': 1, 'is_new_record': True}
            
            current_streak, longest_streak, last_activity = data
            last_date = datetime.strptime(last_activity, '%Y-%m-%d').date() if last_activity else None
            
            if last_date == today:
                # Уже активен сегодня
                return {'streak': current_streak, 'is_new_record': False}
            elif last_date == today - timedelta(days=1):
                # Продолжаем серию
                new_streak = current_streak + 1
                new_longest = max(longest_streak, new_streak)
                is_record = new_streak > longest_streak
                
                c.execute('''
                    UPDATE user_gamification 
                    SET current_streak = ?, longest_streak = ?, last_activity_date = ?
                    WHERE user_id = ?
                ''', (new_streak, new_longest, today, user_id))
                
                # Начисляем XP за день серии
                self.award_xp(user_id, 'streak_day', f'День {new_streak} серии активности')
                
                conn.commit()
                return {'streak': new_streak, 'is_new_record': is_record}
            else:
                # Серия прервана, начинаем заново
                c.execute('''
                    UPDATE user_gamification 
                    SET current_streak = 1, last_activity_date = ?
                    WHERE user_id = ?
                ''', (today, user_id))
                
                conn.commit()
                return {'streak': 1, 'is_new_record': False}
                
        except Exception as e:
            conn.rollback()
            logger.error(f"Error updating streak: {e}")
            return {'streak': 0, 'is_new_record': False}
        finally:
            conn.close()
    
    def get_leaderboard(self, limit: int = 10) -> List[Dict]:
        """Получение таблицы лидеров"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        c.execute('''
            SELECT 
                ug.user_id,
                u.username,
                ug.level,
                ug.total_xp,
                ug.current_streak,
                COUNT(ua.achievement_id) as achievements_count
            FROM user_gamification ug
            JOIN users u ON ug.user_id = u.id
            LEFT JOIN user_achievements ua ON ug.user_id = ua.user_id
            GROUP BY ug.user_id, u.username, ug.level, ug.total_xp, ug.current_streak
            ORDER BY ug.total_xp DESC, ug.level DESC
            LIMIT ?
        ''', (limit,))
        
        leaderboard = []
        for i, row in enumerate(c.fetchall(), 1):
            user_id, username, level, total_xp, streak, achievements = row
            level_info = self.get_level_info(total_xp)
            
            leaderboard.append({
                'rank': i,
                'user_id': user_id,
                'username': username,
                'level': level,
                'level_title': level_info['current_title'],
                'total_xp': total_xp,
                'current_streak': streak,
                'achievements_count': achievements,
                'badge_color': level_info['badge_color']
            })
        
        conn.close()
        return leaderboard

# Глобальный экземпляр системы геймификации
gamification = GamificationSystem()

# Инициализация при импорте
try:
    gamification.init_gamification_tables()
except Exception as e:
    logger.warning(f"Could not initialize gamification tables: {e}")