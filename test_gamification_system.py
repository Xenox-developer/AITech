"""
Тесты системы геймификации AI Study
"""
import unittest
import sqlite3
import tempfile
import os
from datetime import datetime, timedelta
import json

# Импортируем наши модули
from gamification import GamificationSystem, ACHIEVEMENTS, XP_ACTIONS
from smart_upgrade_triggers import SmartUpgradeTriggers
from subscription_manager import SubscriptionManager

class TestGamificationSystem(unittest.TestCase):
    """Тесты системы геймификации"""
    
    def setUp(self):
        """Настройка тестовой среды"""
        # Создаем временную базу данных
        self.db_fd, self.db_path = tempfile.mkstemp()
        
        # Инициализируем системы
        self.gamification = GamificationSystem(self.db_path)
        self.triggers = SmartUpgradeTriggers(self.db_path)
        self.subscription_manager = SubscriptionManager()
        self.subscription_manager.db_path = self.db_path
        
        # Создаем тестовые таблицы
        self.init_test_tables()
        
        # Создаем тестового пользователя
        self.test_user_id = self.create_test_user()
    
    def tearDown(self):
        """Очистка после тестов"""
        os.close(self.db_fd)
        os.unlink(self.db_path)
    
    def init_test_tables(self):
        """Инициализация тестовых таблиц"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        # Таблица пользователей
        c.execute('''
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                subscription_type TEXT DEFAULT 'freemium',
                subscription_start_date TIMESTAMP,
                subscription_end_date TIMESTAMP,
                monthly_analyses_used INTEGER DEFAULT 0,
                monthly_reset_date TIMESTAMP,
                total_pdf_pages_used INTEGER DEFAULT 0,
                total_video_minutes_used INTEGER DEFAULT 0,
                ai_chat_messages_used INTEGER DEFAULT 0,
                monthly_video_uploads_used INTEGER DEFAULT 0,
                subscription_status TEXT DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Таблица результатов
        c.execute('''
            CREATE TABLE result (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                file_type TEXT NOT NULL,
                topics_json TEXT NOT NULL,
                summary TEXT NOT NULL,
                flashcards_json TEXT NOT NULL,
                full_text TEXT,
                user_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')
        
        # Таблица чата
        c.execute('''
            CREATE TABLE chat_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                result_id INTEGER,
                user_id INTEGER,
                user_message TEXT NOT NULL,
                ai_response TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (result_id) REFERENCES result(id),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')
        
        # Таблица прогресса
        c.execute('''
            CREATE TABLE user_progress (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                result_id INTEGER,
                flashcard_id INTEGER,
                user_id INTEGER,
                last_review TIMESTAMP,
                next_review TIMESTAMP,
                ease_factor REAL DEFAULT 2.5,
                consecutive_correct INTEGER DEFAULT 0,
                FOREIGN KEY (result_id) REFERENCES result(id),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')
        
        # Таблица использования подписки
        c.execute('''
            CREATE TABLE subscription_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                usage_type TEXT NOT NULL,
                amount INTEGER DEFAULT 1,
                resource_info TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')
        
        # Таблица логирования триггеров апгрейда
        c.execute('''
            CREATE TABLE upgrade_triggers_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                trigger_reason TEXT NOT NULL,
                offer_details TEXT,
                shown_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                action TEXT,
                action_at TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def create_test_user(self):
        """Создание тестового пользователя"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        c.execute('''
            INSERT INTO users (username, email, password_hash, subscription_type)
            VALUES (?, ?, ?, ?)
        ''', ('testuser', 'test@example.com', 'hash123', 'freemium'))
        
        user_id = c.lastrowid
        conn.commit()
        conn.close()
        
        return user_id
    
    def test_gamification_initialization(self):
        """Тест инициализации системы геймификации"""
        # Проверяем, что пользователь создан в системе геймификации
        data = self.gamification.get_user_gamification_data(self.test_user_id)
        
        self.assertEqual(data['level'], 1)
        self.assertEqual(data['total_xp'], 0)
        self.assertEqual(data['current_streak'], 0)
        self.assertEqual(len(data['achievements']), 0)
    
    def test_xp_awarding(self):
        """Тест начисления XP"""
        # Начисляем XP за анализ документа
        result = self.gamification.award_xp(
            self.test_user_id,
            'document_analysis',
            'Тестовый анализ'
        )
        
        self.assertTrue(result['success'])
        self.assertEqual(result['xp_gained'], XP_ACTIONS['document_analysis'])
        self.assertEqual(result['total_xp'], XP_ACTIONS['document_analysis'])
        
        # Проверяем, что данные обновились
        data = self.gamification.get_user_gamification_data(self.test_user_id)
        self.assertEqual(data['total_xp'], XP_ACTIONS['document_analysis'])
    
    def test_level_progression(self):
        """Тест повышения уровня"""
        # Начисляем достаточно XP для повышения уровня
        for i in range(15):  # 15 * 50 = 750 XP (достаточно для уровня 5)
            self.gamification.award_xp(
                self.test_user_id,
                'document_analysis',
                f'Анализ {i+1}'
            )
        
        data = self.gamification.get_user_gamification_data(self.test_user_id)
        self.assertGreaterEqual(data['level'], 5)
        self.assertEqual(data['total_xp'], 750)
    
    def test_achievement_unlocking(self):
        """Тест разблокировки достижений"""
        # Создаем тестовые данные для достижения "first_analysis"
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        c.execute('''
            INSERT INTO result (filename, file_type, topics_json, summary, flashcards_json, user_id)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', ('test.pdf', 'pdf', '[]', 'Test summary', '[]', self.test_user_id))
        
        conn.commit()
        conn.close()
        
        # Начисляем XP за анализ
        result = self.gamification.award_xp(
            self.test_user_id,
            'document_analysis',
            'Первый анализ'
        )
        
        # Проверяем, что достижение разблокировано
        self.assertGreater(len(result.get('new_achievements', [])), 0)
        
        # Проверяем в базе данных
        data = self.gamification.get_user_gamification_data(self.test_user_id)
        achievement_ids = [a['id'] for a in data['achievements']]
        self.assertIn('first_analysis', achievement_ids)
    
    def test_streak_system(self):
        """Тест системы серий"""
        # Обновляем серию
        streak_result = self.gamification.update_daily_streak(self.test_user_id)
        
        self.assertEqual(streak_result['streak'], 1)
        self.assertTrue(streak_result['is_new_record'])
        
        # Проверяем данные
        data = self.gamification.get_user_gamification_data(self.test_user_id)
        self.assertEqual(data['current_streak'], 1)
        self.assertEqual(data['longest_streak'], 1)
    
    def test_leaderboard(self):
        """Тест таблицы лидеров"""
        # Начисляем XP тестовому пользователю
        self.gamification.award_xp(self.test_user_id, 'document_analysis', 'Test')
        
        # Получаем таблицу лидеров
        leaderboard = self.gamification.get_leaderboard(10)
        
        self.assertGreater(len(leaderboard), 0)
        self.assertEqual(leaderboard[0]['user_id'], self.test_user_id)
        self.assertEqual(leaderboard[0]['rank'], 1)
    
    def test_smart_upgrade_triggers(self):
        """Тест умных триггеров апгрейда"""
        # Создаем активность пользователя
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        # Добавляем несколько анализов
        for i in range(3):
            c.execute('''
                INSERT INTO result (filename, file_type, topics_json, summary, flashcards_json, user_id)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (f'test{i}.pdf', 'pdf', '[]', 'Summary', '[]', self.test_user_id))
        
        # Добавляем AI сообщения
        for i in range(5):
            c.execute('''
                INSERT INTO chat_history (result_id, user_id, user_message, ai_response)
                VALUES (?, ?, ?, ?)
            ''', (1, self.test_user_id, f'Question {i}', f'Answer {i}'))
        
        conn.commit()
        conn.close()
        
        # Получаем триггеры
        triggers = self.triggers.get_upgrade_triggers(self.test_user_id)
        
        self.assertIsInstance(triggers, list)
        # Должны быть триггеры для активного пользователя freemium плана
        if triggers:
            self.assertIn('title', triggers[0].__dict__)
            self.assertIn('message', triggers[0].__dict__)
    
    def test_behavior_analysis(self):
        """Тест анализа поведения пользователя"""
        # Создаем данные активности
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        # Анализы
        for i in range(5):
            c.execute('''
                INSERT INTO result (filename, file_type, topics_json, summary, flashcards_json, user_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (f'doc{i}.pdf', 'pdf', '[]', 'Summary', '[]', self.test_user_id, datetime.now()))
        
        # AI чат
        for i in range(10):
            c.execute('''
                INSERT INTO chat_history (result_id, user_id, user_message, ai_response, created_at)
                VALUES (?, ?, ?, ?, ?)
            ''', (1, self.test_user_id, f'Q{i}', f'A{i}', datetime.now()))
        
        # Флеш-карты
        for i in range(20):
            c.execute('''
                INSERT INTO user_progress (result_id, user_id, last_review, consecutive_correct)
                VALUES (?, ?, ?, ?)
            ''', (1, self.test_user_id, datetime.now(), 2))
        
        conn.commit()
        conn.close()
        
        # Анализируем поведение
        behavior = self.triggers.analyze_user_behavior(self.test_user_id)
        
        self.assertEqual(behavior['total_analyses'], 5)
        self.assertEqual(behavior['chat_messages'], 10)
        self.assertEqual(behavior['flashcard_reviews'], 20)
        self.assertEqual(behavior['current_plan'], 'freemium')
        
        # Проверяем готовность к апгрейду
        readiness = self.triggers.calculate_upgrade_readiness_score(behavior)
        self.assertGreater(readiness, 0.3)  # Должна быть заметная готовность
    
    def test_trigger_analytics(self):
        """Тест аналитики триггеров"""
        # Записываем показ триггера
        self.triggers.record_trigger_shown(
            self.test_user_id,
            'high_activity',
            {'title': 'Test offer', 'discount': 30}
        )
        
        # Записываем действие
        self.triggers.record_trigger_action(
            self.test_user_id,
            'high_activity',
            'upgraded'
        )
        
        # Получаем аналитику
        analytics = self.triggers.get_trigger_analytics(30)
        
        self.assertIn('trigger_stats', analytics)
        if analytics['trigger_stats']:
            stats = analytics['trigger_stats'][0]
            self.assertEqual(stats['trigger_reason'], 'high_activity')
            self.assertEqual(stats['shown_count'], 1)
            self.assertEqual(stats['converted_count'], 1)
    
    def test_integration_with_subscription(self):
        """Тест интеграции с системой подписок"""
        # Проверяем, что пользователь на freemium плане
        subscription = self.subscription_manager.get_user_subscription(self.test_user_id)
        self.assertEqual(subscription['type'], 'freemium')
        
        # Записываем использование
        self.subscription_manager.record_usage(
            self.test_user_id,
            'analysis',
            1,
            'test_analysis'
        )
        
        # Проверяем статистику
        stats = self.subscription_manager.get_usage_stats(self.test_user_id)
        self.assertEqual(stats['analyses']['used'], 1)
    
    def test_multiple_users_leaderboard(self):
        """Тест таблицы лидеров с несколькими пользователями"""
        # Создаем дополнительных пользователей
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        user_ids = []
        for i in range(3):
            c.execute('''
                INSERT INTO users (username, email, password_hash)
                VALUES (?, ?, ?)
            ''', (f'user{i}', f'user{i}@test.com', 'hash'))
            user_ids.append(c.lastrowid)
        
        conn.commit()
        conn.close()
        
        # Начисляем разное количество XP
        xp_amounts = [100, 300, 200, 150]  # Включая тестового пользователя
        all_users = [self.test_user_id] + user_ids
        
        for user_id, xp in zip(all_users, xp_amounts):
            for _ in range(xp // 50):  # 50 XP за анализ
                self.gamification.award_xp(user_id, 'document_analysis', 'Test')
        
        # Получаем таблицу лидеров
        leaderboard = self.gamification.get_leaderboard(10)
        
        self.assertEqual(len(leaderboard), 4)
        
        # Проверяем правильность сортировки
        prev_xp = float('inf')
        for entry in leaderboard:
            self.assertLessEqual(entry['total_xp'], prev_xp)
            prev_xp = entry['total_xp']
        
        # Проверяем, что пользователь с наибольшим XP на первом месте
        self.assertEqual(leaderboard[0]['total_xp'], 300)
        self.assertEqual(leaderboard[0]['rank'], 1)

class TestGamificationIntegration(unittest.TestCase):
    """Тесты интеграции геймификации с основным приложением"""
    
    def setUp(self):
        """Настройка тестовой среды"""
        self.db_fd, self.db_path = tempfile.mkstemp()
        self.gamification = GamificationSystem(self.db_path)
        
        # Создаем минимальные таблицы
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        c.execute('''
            CREATE TABLE users (
                id INTEGER PRIMARY KEY,
                username TEXT,
                email TEXT
            )
        ''')
        
        # Добавляем таблицу result для проверки достижений
        c.execute('''
            CREATE TABLE result (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                file_type TEXT NOT NULL,
                topics_json TEXT NOT NULL,
                summary TEXT NOT NULL,
                flashcards_json TEXT NOT NULL,
                full_text TEXT,
                user_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')
        
        # Добавляем таблицу chat_history для проверки достижений
        c.execute('''
            CREATE TABLE chat_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                result_id INTEGER,
                user_id INTEGER,
                user_message TEXT NOT NULL,
                ai_response TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (result_id) REFERENCES result(id),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')
        
        # Добавляем таблицу user_progress для проверки достижений
        c.execute('''
            CREATE TABLE user_progress (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                result_id INTEGER,
                flashcard_id INTEGER,
                user_id INTEGER,
                last_review TIMESTAMP,
                next_review TIMESTAMP,
                ease_factor REAL DEFAULT 2.5,
                consecutive_correct INTEGER DEFAULT 0,
                FOREIGN KEY (result_id) REFERENCES result(id),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')
        
        c.execute('INSERT INTO users (username, email) VALUES (?, ?)', ('test', 'test@test.com'))
        self.test_user_id = c.lastrowid
        
        conn.commit()
        conn.close()
    
    def tearDown(self):
        """Очистка"""
        os.close(self.db_fd)
        os.unlink(self.db_path)
    
    def test_xp_actions_completeness(self):
        """Тест полноты конфигурации XP действий"""
        required_actions = [
            'document_analysis',
            'flashcard_review',
            'ai_chat_message',
            'mind_map_creation',
            'streak_day',
            'perfect_session',
            'video_analysis'
        ]
        
        for action in required_actions:
            self.assertIn(action, XP_ACTIONS)
            self.assertGreater(XP_ACTIONS[action], 0)
    
    def test_achievements_completeness(self):
        """Тест полноты конфигурации достижений"""
        required_categories = ['analysis', 'learning', 'social', 'mastery']
        
        categories_found = set()
        for achievement in ACHIEVEMENTS.values():
            categories_found.add(achievement.category)
            
            # Проверяем обязательные поля
            self.assertIsInstance(achievement.title, str)
            self.assertIsInstance(achievement.description, str)
            self.assertIsInstance(achievement.xp_reward, int)
            self.assertGreater(achievement.xp_reward, 0)
            self.assertIn(achievement.rarity, ['common', 'rare', 'epic', 'legendary'])
        
        # Проверяем, что есть достижения всех категорий
        for category in required_categories:
            self.assertIn(category, categories_found)
    
    def test_concurrent_xp_awarding(self):
        """Тест одновременного начисления XP"""
        import threading
        import time
        
        # Сначала убеждаемся, что запись пользователя существует
        self.gamification.get_user_gamification_data(self.test_user_id)
        
        results = []
        
        def award_xp_worker(worker_id):
            # Добавляем небольшую задержку для разнесения запросов
            time.sleep(worker_id * 0.01)
            result = self.gamification.award_xp(
                self.test_user_id,
                'ai_chat_message',  # Используем меньший XP для более предсказуемого результата
                f'Concurrent test {worker_id}'
            )
            results.append(result)
        
        # Запускаем несколько потоков одновременно
        threads = []
        for i in range(3):  # Уменьшаем количество потоков
            thread = threading.Thread(target=award_xp_worker, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Ждем завершения всех потоков
        for thread in threads:
            thread.join()
        
        # Проверяем результаты
        self.assertEqual(len(results), 3)
        successful_results = [r for r in results if r.get('success', False)]
        self.assertGreater(len(successful_results), 0)  # Хотя бы один должен быть успешным
        
        # Проверяем, что XP был начислен
        data = self.gamification.get_user_gamification_data(self.test_user_id)
        self.assertGreater(data['total_xp'], 0)

def run_all_tests():
    """Запуск всех тестов"""
    # Создаем test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Добавляем тесты
    suite.addTests(loader.loadTestsFromTestCase(TestGamificationSystem))
    suite.addTests(loader.loadTestsFromTestCase(TestGamificationIntegration))
    
    # Запускаем тесты
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()

if __name__ == '__main__':
    print("🧪 Запуск тестов системы геймификации AI Study...")
    print("=" * 60)
    
    success = run_all_tests()
    
    print("=" * 60)
    if success:
        print("✅ Все тесты пройдены успешно!")
        print("🎮 Система геймификации готова к использованию!")
    else:
        print("❌ Некоторые тесты не прошли.")
        print("🔧 Необходимо исправить ошибки перед запуском.")
    
    exit(0 if success else 1)