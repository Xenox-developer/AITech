"""
Тесты системы аналитики по планам подписки
"""
import unittest
import sqlite3
import tempfile
import os
from datetime import datetime, timedelta
import json

# Импортируем наши модули
from analytics_manager import AnalyticsManager
from subscription_manager import SubscriptionManager

class TestAnalyticsByPlans(unittest.TestCase):
    """Тесты аналитики по планам подписки"""
    
    def setUp(self):
        """Настройка тестовой среды"""
        # Создаем временную базу данных
        self.db_fd, self.db_path = tempfile.mkstemp()
        
        # Инициализируем системы
        self.analytics_manager = AnalyticsManager(self.db_path)
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
                monthly_analyses_used INTEGER DEFAULT 0,
                ai_chat_messages_used INTEGER DEFAULT 0,
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
        
        conn.commit()
        conn.close()
    
    def create_test_user(self, subscription_type='lite', email_suffix=''):
        """Создание тестового пользователя"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        # Генерируем уникальный email
        import time
        unique_email = f'test{email_suffix}{int(time.time() * 1000)}@example.com'
        
        c.execute('''
            INSERT INTO users (username, email, password_hash, subscription_type)
            VALUES (?, ?, ?, ?)
        ''', (f'testuser{email_suffix}', unique_email, 'hash123', subscription_type))
        
        user_id = c.lastrowid
        conn.commit()
        conn.close()
        
        return user_id
    
    def create_test_data(self, user_id):
        """Создание тестовых данных для аналитики"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        # Создаем результаты анализа
        for i in range(5):
            c.execute('''
                INSERT INTO result (filename, file_type, topics_json, summary, flashcards_json, user_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (f'test{i}.pdf', '.pdf', '[]', f'Summary {i}', '[]', user_id, 
                  datetime.now() - timedelta(days=i)))
        
        # Создаем AI чат сообщения
        for i in range(10):
            c.execute('''
                INSERT INTO chat_history (result_id, user_id, user_message, ai_response, created_at)
                VALUES (?, ?, ?, ?, ?)
            ''', (1, user_id, f'Question {i}', f'Answer {i}', 
                  datetime.now() - timedelta(hours=i)))
        
        # Создаем прогресс по флеш-картам
        for i in range(15):
            c.execute('''
                INSERT INTO user_progress (result_id, user_id, last_review, consecutive_correct)
                VALUES (?, ?, ?, ?)
            ''', (1, user_id, datetime.now() - timedelta(hours=i), i % 4))
        
        conn.commit()
        conn.close()
    
    def test_lite_learning_stats(self):
        """Тест базовой статистики для плана LITE"""
        # Создаем тестовые данные
        self.create_test_data(self.test_user_id)
        
        # Получаем статистику
        stats = self.analytics_manager.get_learning_stats(self.test_user_id)
        
        # Проверяем структуру ответа
        self.assertEqual(stats['type'], 'learning_stats')
        self.assertIn('total_documents', stats)
        self.assertIn('active_days', stats)
        self.assertIn('file_types', stats)
        self.assertIn('estimated_study_time', stats)
        
        # Проверяем данные
        self.assertEqual(stats['total_documents'], 5)
        self.assertGreater(stats['estimated_study_time'], 0)
        self.assertEqual(stats['file_types']['pdf'], 5)
    
    def test_starter_learning_progress(self):
        """Тест прогресса обучения для плана STARTER"""
        # Создаем тестовые данные
        self.create_test_data(self.test_user_id)
        
        # Получаем прогресс
        progress = self.analytics_manager.get_learning_progress(self.test_user_id)
        
        # Проверяем структуру ответа
        self.assertEqual(progress['type'], 'learning_progress')
        self.assertIn('flashcard_progress', progress)
        self.assertIn('chat_activity', progress)
        self.assertIn('recommendations', progress)
        self.assertIn('weak_areas', progress)
        
        # Проверяем данные флеш-карт
        flashcard_progress = progress['flashcard_progress']
        self.assertIn('total_reviews', flashcard_progress)
        self.assertIn('mastery_rate', flashcard_progress)
        
        # Проверяем рекомендации
        self.assertIsInstance(progress['recommendations'], list)
        self.assertGreater(len(progress['recommendations']), 0)
    
    def test_basic_detailed_analytics(self):
        """Тест детальной аналитики для плана BASIC"""
        # Создаем тестовые данные
        self.create_test_data(self.test_user_id)
        
        # Создаем дополнительного пользователя для сравнения
        other_user_id = self.create_test_user('basic', '_other')
        self.create_test_data(other_user_id)
        
        # Получаем детальную аналитику
        analytics = self.analytics_manager.get_detailed_analytics(self.test_user_id)
        
        # Проверяем структуру ответа
        self.assertEqual(analytics['type'], 'detailed_analytics')
        self.assertIn('comparison', analytics)
        self.assertIn('performance_trend', analytics)
        self.assertIn('optimal_study_hours', analytics)
        self.assertIn('predictions', analytics)
        
        # Проверяем сравнение
        comparison = analytics['comparison']
        self.assertIn('analyses_vs_average', comparison)
        self.assertIn('performance_percentile', comparison)
        
        # Проверяем прогнозы
        predictions = analytics['predictions']
        self.assertIn('next_week_performance', predictions)
        self.assertIn('improvement_trend', predictions)
    
    def test_pro_full_analytics(self):
        """Тест полной аналитики для плана PRO"""
        # Создаем тестовые данные
        self.create_test_data(self.test_user_id)
        
        # Получаем полную аналитику
        analytics = self.analytics_manager.get_full_analytics(self.test_user_id)
        
        # Проверяем структуру ответа
        self.assertEqual(analytics['type'], 'full_analytics')
        self.assertIn('monthly_trends', analytics)
        self.assertIn('team_statistics', analytics)
        
        # Проверяем новые PRO функции
        self.assertIn('learning_velocity', analytics)
        self.assertIn('retention_forecast', analytics)
        self.assertIn('content_analysis', analytics)
        self.assertIn('productivity_by_hour', analytics)
        self.assertIn('complexity_analysis', analytics)
        self.assertIn('usage_statistics', analytics)
        self.assertIn('pro_features', analytics)
        
        # Проверяем скорость обучения
        velocity = analytics['learning_velocity']
        self.assertIn('documents_per_week', velocity)
        self.assertIn('velocity_trend', velocity)
        self.assertIn('learning_consistency', velocity)
        
        # Проверяем прогноз удержания
        retention = analytics['retention_forecast']
        self.assertIn('retention_rate_7_days', retention)
        self.assertIn('forgetting_curve', retention)
        self.assertIn('recommended_review_frequency', retention)
        
        # Проверяем PRO функции
        pro_features = analytics['pro_features']
        self.assertTrue(pro_features['deep_content_analysis'])
        self.assertTrue(pro_features['productivity_insights'])
        self.assertTrue(pro_features['learning_velocity_tracking'])
        
        # Проверяем статистику (командная статистика убрана)
        team_stats = analytics['team_statistics']
        self.assertIn('team_size', team_stats)
        self.assertEqual(team_stats['team_size'], 0)  # Должно быть 0 так как командная работа отключена
        
        # Экспорт убран из PRO плана
        
        # Проверяем флаги PRO функций
        self.assertTrue(analytics['custom_dashboards'])
        self.assertTrue(analytics['advanced_filters'])
    
    def test_recommendations_generation(self):
        """Тест генерации персональных рекомендаций"""
        # Создаем пользователя с низкой активностью
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        # Создаем минимальные данные
        c.execute('''
            INSERT INTO result (filename, file_type, topics_json, summary, flashcards_json, user_id)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', ('test.pdf', 'pdf', '[]', 'Summary', '[]', self.test_user_id))
        
        conn.commit()
        conn.close()
        
        # Получаем рекомендации
        progress = self.analytics_manager.get_learning_progress(self.test_user_id)
        recommendations = progress['recommendations']
        
        # Проверяем, что рекомендации генерируются
        self.assertIsInstance(recommendations, list)
        self.assertGreater(len(recommendations), 0)
        
        # Проверяем, что рекомендации содержат полезную информацию
        for rec in recommendations:
            self.assertIsInstance(rec, str)
            self.assertGreater(len(rec), 10)  # Не пустые рекомендации
    
    def test_performance_percentile_calculation(self):
        """Тест расчета процентиля производительности"""
        # Создаем несколько пользователей с разной производительностью
        users = []
        for i in range(5):
            user_id = self.create_test_user('basic', f'_perf{i}')
            users.append(user_id)
            
            # Создаем данные с разной точностью
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            
            c.execute('''
                INSERT INTO result (filename, file_type, topics_json, summary, flashcards_json, user_id)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (f'test{i}.pdf', 'pdf', '[]', 'Summary', '[]', user_id))
            
            result_id = c.lastrowid
            
            # Создаем прогресс с разной точностью
            for j in range(10):
                accuracy = (i + 1)  # Пользователи с разной точностью
                c.execute('''
                    INSERT INTO user_progress (result_id, user_id, consecutive_correct)
                    VALUES (?, ?, ?)
                ''', (result_id, user_id, accuracy))
            
            conn.commit()
            conn.close()
        
        # Получаем аналитику для пользователя со средней производительностью
        analytics = self.analytics_manager.get_detailed_analytics(users[2])
        percentile = analytics['comparison']['performance_percentile']
        
        # Проверяем, что процентиль в разумных пределах
        self.assertGreaterEqual(percentile, 0)
        self.assertLessEqual(percentile, 100)
    
    def test_study_optimization_recommendations(self):
        """Тест рекомендаций по оптимизации обучения"""
        # Создаем данные с активностью в разные дни
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        # Создаем результаты в разные дни недели
        for i in range(7):
            date = datetime.now() - timedelta(days=i)
            c.execute('''
                INSERT INTO result (filename, file_type, topics_json, summary, flashcards_json, user_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (f'test{i}.pdf', 'pdf', '[]', 'Summary', '[]', self.test_user_id, date))
            
            result_id = c.lastrowid
            
            # Создаем прогресс с разной производительностью по дням
            performance = 3 if i % 2 == 0 else 1  # Лучше в четные дни
            c.execute('''
                INSERT INTO user_progress (result_id, user_id, consecutive_correct, last_review)
                VALUES (?, ?, ?, ?)
            ''', (result_id, self.test_user_id, performance, date))
        
        conn.commit()
        conn.close()
        
        # Получаем рекомендации по оптимизации
        analytics = self.analytics_manager.get_detailed_analytics(self.test_user_id)
        optimization = analytics['study_optimization']
        
        # Проверяем структуру рекомендаций
        self.assertIn('optimal_study_day', optimization)
        self.assertIn('recommended_session_length', optimization)
        self.assertIn('break_frequency', optimization)
        self.assertIn('review_schedule', optimization)
    
    def test_monthly_trends_analysis(self):
        """Тест анализа месячных трендов для PRO плана"""
        # Создаем данные за несколько месяцев
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        for month_offset in range(6):
            date = datetime.now() - timedelta(days=30 * month_offset)
            
            # Создаем несколько результатов в каждом месяце
            for i in range(3):
                c.execute('''
                    INSERT INTO result (filename, file_type, topics_json, summary, flashcards_json, user_id, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (f'test{month_offset}_{i}.pdf', 'pdf', '[]', f'Summary {i}', '[]', 
                      self.test_user_id, date))
        
        conn.commit()
        conn.close()
        
        # Получаем полную аналитику
        analytics = self.analytics_manager.get_full_analytics(self.test_user_id)
        monthly_trends = analytics['monthly_trends']
        
        # Проверяем, что тренды генерируются
        self.assertIsInstance(monthly_trends, list)
        self.assertGreater(len(monthly_trends), 0)
        
        # Проверяем структуру трендов
        for trend in monthly_trends:
            self.assertIn('month', trend)
            self.assertIn('documents', trend)
            self.assertIn('file_types', trend)

def run_analytics_tests():
    """Запуск всех тестов аналитики"""
    # Создаем test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Добавляем тесты
    suite.addTests(loader.loadTestsFromTestCase(TestAnalyticsByPlans))
    
    # Запускаем тесты
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()

if __name__ == '__main__':
    print("🧪 Запуск тестов системы аналитики по планам подписки...")
    print("=" * 60)
    
    success = run_analytics_tests()
    
    print("=" * 60)
    if success:
        print("✅ Все тесты аналитики пройдены успешно!")
        print("📊 Система аналитики по планам готова к использованию!")
    else:
        print("❌ Некоторые тесты не прошли.")
        print("🔧 Необходимо исправить ошибки перед запуском.")
    
    exit(0 if success else 1)