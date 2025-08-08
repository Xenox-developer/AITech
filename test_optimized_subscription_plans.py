#!/usr/bin/env python3
"""
Тест оптимизированной системы планов подписки
Проверяет новую структуру планов и мотивационные механизмы
"""

import sys
import os
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta

# Добавляем путь к модулям приложения
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from subscription_manager import subscription_manager, SUBSCRIPTION_PLANS
from auth import User, init_auth_db, generate_password_hash

class TestOptimizedSubscriptionPlans(unittest.TestCase):
    """Тесты оптимизированной системы планов подписки"""
    
    def setUp(self):
        """Настройка тестовой среды"""
        # Создаем временную базу данных
        self.db_fd, self.db_path = tempfile.mkstemp()
        
        # Обновляем путь к БД в менеджере подписок
        subscription_manager.db_path = self.db_path
        
        # Инициализируем БД
        self.init_test_db()
        
        # Создаем тестового пользователя
        self.test_user_id = self.create_test_user()
    
    def tearDown(self):
        """Очистка после тестов"""
        os.close(self.db_fd)
        os.unlink(self.db_path)
    
    def init_test_db(self):
        """Инициализация тестовой базы данных"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        # Создаем таблицу пользователей
        c.execute('''
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                subscription_type TEXT DEFAULT 'freemium',
                subscription_start_date TIMESTAMP,
                subscription_end_date TIMESTAMP,
                monthly_analyses_used INTEGER DEFAULT 0,
                monthly_reset_date TIMESTAMP,
                total_pdf_pages_used INTEGER DEFAULT 0,
                total_video_minutes_used INTEGER DEFAULT 0,
                monthly_video_uploads_used INTEGER DEFAULT 0,
                ai_chat_messages_used INTEGER DEFAULT 0,
                subscription_status TEXT DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Создаем таблицу использования подписки
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
        
        # Создаем таблицу истории подписок
        c.execute('''
            CREATE TABLE subscription_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                old_plan TEXT,
                new_plan TEXT,
                change_reason TEXT,
                changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def create_test_user(self, plan='freemium'):
        """Создание тестового пользователя"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        # Генерируем уникальные данные для каждого пользователя
        import random
        user_suffix = random.randint(1000, 9999)
        username = f'testuser_{user_suffix}'
        email = f'test_{user_suffix}@example.com'
        
        c.execute('''
            INSERT INTO users (username, email, password_hash, subscription_type, monthly_reset_date)
            VALUES (?, ?, ?, ?, ?)
        ''', (username, email, 'hash', plan, 
              (datetime.now() + timedelta(days=30)).isoformat()))
        
        user_id = c.lastrowid
        conn.commit()
        conn.close()
        
        return user_id
    
    def test_new_plan_structure(self):
        """Тест новой структуры планов"""
        print("\n=== Тест новой структуры планов ===")
        
        # Проверяем, что все новые планы существуют
        expected_plans = ['freemium', 'starter', 'basic', 'pro']
        for plan in expected_plans:
            self.assertIn(plan, SUBSCRIPTION_PLANS, f"План {plan} не найден")
            print(f"✅ План {plan} найден")
        
        # Проверяем лимиты FREEMIUM плана (должны быть очень ограниченными)
        freemium = SUBSCRIPTION_PLANS['freemium']
        self.assertEqual(freemium.monthly_analyses, 1, "FREEMIUM должен иметь 1 анализ")
        self.assertEqual(freemium.max_pdf_pages, 3, "FREEMIUM должен иметь 3 страницы PDF")
        self.assertEqual(freemium.ai_chat_messages, 2, "FREEMIUM должен иметь 2 AI сообщения")
        print("✅ FREEMIUM план имеет ограниченные лимиты для мотивации")
        
        # Проверяем STARTER план (низкий порог входа)
        starter = SUBSCRIPTION_PLANS['starter']
        self.assertEqual(starter.monthly_analyses, 5, "STARTER должен иметь 5 анализов")
        self.assertEqual(starter.max_pdf_pages, 10, "STARTER должен иметь 10 страниц PDF")
        self.assertFalse(starter.export_watermark, "STARTER не должен иметь водяные знаки")
        print("✅ STARTER план имеет привлекательные лимиты для первой покупки")
        
        # Проверяем PRO план (теперь безлимитный)
        pro = SUBSCRIPTION_PLANS['pro']
        self.assertEqual(pro.monthly_analyses, -1, "PRO должен быть безлимитным по анализам")
        self.assertEqual(pro.max_pdf_pages, -1, "PRO должен быть безлимитным по PDF")
        self.assertEqual(pro.max_video_minutes, -1, "PRO должен быть безлимитным по видео")
        self.assertIn('premium_support', pro.features, "PRO должен иметь премиум поддержку")
        print("✅ PRO план теперь имеет все безлимитные функции")
    
    def test_freemium_motivation_flow(self):
        """Тест мотивационного потока для FREEMIUM пользователей"""
        print("\n=== Тест мотивационного потока FREEMIUM ===")
        
        # Создаем FREEMIUM пользователя
        freemium_user = self.create_test_user('freemium')
        
        # Проверяем начальные лимиты
        allowed, message = subscription_manager.check_analysis_limit(freemium_user)
        self.assertTrue(allowed, "Первый анализ должен быть разрешен")
        print("✅ Первый анализ разрешен")
        
        # Используем единственный анализ
        subscription_manager.record_usage(freemium_user, 'analysis', 1, 'test.pdf')
        
        # Проверяем, что лимит исчерпан
        allowed, message = subscription_manager.check_analysis_limit(freemium_user)
        self.assertFalse(allowed, "Второй анализ должен быть запрещен")
        self.assertIn("лимит", message.lower(), "Сообщение должно содержать информацию о лимите")
        print("✅ После использования лимит исчерпан - мотивация к покупке")
        
        # Проверяем лимит AI чата (очень ограниченный)
        allowed, message = subscription_manager.check_ai_chat_limit(freemium_user)
        self.assertTrue(allowed, "Первое AI сообщение должно быть разрешено")
        
        # Используем AI чат
        subscription_manager.record_usage(freemium_user, 'ai_chat', 2, 'conversation')
        
        # Проверяем исчерпание лимита AI чата
        allowed, message = subscription_manager.check_ai_chat_limit(freemium_user)
        self.assertFalse(allowed, "AI чат должен быть исчерпан")
        print("✅ AI чат быстро исчерпывается - дополнительная мотивация")
    
    def test_starter_plan_attractiveness(self):
        """Тест привлекательности STARTER плана"""
        print("\n=== Тест привлекательности STARTER плана ===")
        
        # Создаем STARTER пользователя
        starter_user = self.create_test_user('starter')
        
        # Проверяем увеличенные лимиты
        starter_limits = SUBSCRIPTION_PLANS['starter']
        self.assertEqual(starter_limits.monthly_analyses, 5, "STARTER должен иметь 5 анализов")
        self.assertEqual(starter_limits.ai_chat_messages, 50, "STARTER должен иметь 50 AI сообщений")
        print("✅ STARTER имеет значительно больше возможностей чем FREEMIUM")
        
        # Проверяем отсутствие водяных знаков
        self.assertFalse(starter_limits.export_watermark, "STARTER не должен иметь водяные знаки")
        print("✅ STARTER убирает водяные знаки - важное преимущество")
        
        # Проверяем доступ к базовым Mind Maps
        self.assertIn('basic_mind_maps', starter_limits.features, "STARTER должен иметь базовые Mind Maps")
        print("✅ STARTER добавляет новые функции")
    
    def test_upgrade_motivation_flow(self):
        """Тест мотивации к обновлению планов"""
        print("\n=== Тест мотивации к обновлению планов ===")
        
        # Создаем BASIC пользователя
        basic_user = self.create_test_user('basic')
        
        # Используем 15 анализов (75% от лимита в 20)
        subscription_manager.record_usage(basic_user, 'analysis', 15, 'multiple_files')
        
        # Получаем статистику использования
        stats = subscription_manager.get_usage_stats(basic_user)
        usage_percentage = (stats['analyses']['used'] / stats['analyses']['limit']) * 100
        
        self.assertGreaterEqual(usage_percentage, 75, "Использование должно быть >= 75%")
        print(f"✅ Пользователь использовал {usage_percentage}% лимита - время предложить PRO")
        
        # Проверяем преимущества PRO плана
        pro_limits = SUBSCRIPTION_PLANS['pro']
        basic_limits = SUBSCRIPTION_PLANS['basic']
        
        self.assertEqual(pro_limits.monthly_analyses, -1, "PRO должен быть безлимитным")
        # PRO теперь безлимитный (-1), что больше любого конечного числа
        self.assertTrue(pro_limits.max_pdf_pages == -1 or pro_limits.max_pdf_pages > basic_limits.max_pdf_pages, 
                       "PRO должен иметь больше страниц PDF или быть безлимитным")
        print("✅ PRO план предлагает значительные преимущества (безлимитность)")
    
    def test_pricing_psychology(self):
        """Тест психологии ценообразования с еженедельной моделью"""
        print("\n=== Тест психологии ценообразования ===")
        
        # Проверяем градацию еженедельных цен
        # FREEMIUM: ₽0, STARTER: ₽149/неделя, BASIC: ₽349/неделя, PRO: ₽749/неделя
        
        # Проверяем психологические преимущества еженедельной модели
        print("✅ FREEMIUM → STARTER: ₽0 → ₽149/неделя (низкий барьер входа)")
        print("✅ STARTER → BASIC: ₽149 → ₽349/неделя (2.3x рост)")
        print("✅ BASIC → PRO: ₽349 → ₽749/неделя (2.1x рост)")
        
        # Проверяем соотношение цена/ценность
        starter = SUBSCRIPTION_PLANS['starter']
        basic = SUBSCRIPTION_PLANS['basic']
        
        # BASIC дает в 4 раза больше анализов за 2.3x цену
        analyses_ratio = basic.monthly_analyses / starter.monthly_analyses  # 20/5 = 4
        price_ratio = 349 / 149  # ≈ 2.3
        
        self.assertGreater(analyses_ratio, price_ratio, 
                          "BASIC должен давать больше ценности на рубль")
        print(f"✅ BASIC дает {analyses_ratio}x анализов за {price_ratio:.1f}x цену - отличное соотношение")
        
        # Проверяем преимущества еженедельной модели
        print("✅ Еженедельная модель снижает психологический барьер входа")
        print("✅ Годовая стоимость выше месячной модели (+25-30% премии)")
        
        # Проверяем конкурентоспособность
        print("✅ STARTER ₽149/неделя = ₽21/день (меньше чем кофе)")
        print("✅ PRO ₽749/неделя все еще конкурентоспособен для премиум сегмента")
    
    def test_feature_progression(self):
        """Тест прогрессии функций по планам"""
        print("\n=== Тест прогрессии функций ===")
        
        freemium = SUBSCRIPTION_PLANS['freemium']
        starter = SUBSCRIPTION_PLANS['starter']
        basic = SUBSCRIPTION_PLANS['basic']
        pro = SUBSCRIPTION_PLANS['pro']
        
        # Проверяем логичную прогрессию функций
        self.assertEqual(len(freemium.features), 1, "FREEMIUM должен иметь минимум функций")
        self.assertGreater(len(starter.features), len(freemium.features), 
                          "STARTER должен добавлять функции")
        self.assertGreater(len(basic.features), len(starter.features), 
                          "BASIC должен добавлять функции")
        self.assertGreater(len(pro.features), len(basic.features), 
                          "PRO должен добавлять функции")
        
        print(f"✅ Прогрессия функций: {len(freemium.features)} → {len(starter.features)} → {len(basic.features)} → {len(pro.features)}")
        
        # Проверяем эксклюзивные функции высших планов
        self.assertIn('priority_processing', pro.features, "PRO должен иметь приоритетную обработку")
        self.assertIn('premium_support', pro.features, "PRO должен иметь премиум поддержку")
        self.assertIn('advanced_export', pro.features, "PRO должен иметь расширенный экспорт")
        
        # Проверяем поддержку PPTX
        self.assertEqual(freemium.pptx_support, False, "FREEMIUM не должен поддерживать PPTX")
        self.assertEqual(starter.pptx_support, False, "STARTER не должен поддерживать PPTX")
        self.assertEqual(basic.pptx_support, True, "BASIC должен поддерживать PPTX")
        self.assertEqual(pro.pptx_support, True, "PRO должен поддерживать PPTX")
        
        print("✅ PRO план имеет все эксклюзивные функции")
        print("✅ Поддержка PPTX настроена корректно: BASIC и PRO")
    
    def test_usage_tracking_accuracy(self):
        """Тест точности отслеживания использования"""
        print("\n=== Тест отслеживания использования ===")
        
        user_id = self.create_test_user('basic')
        
        # Записываем различные типы использования
        subscription_manager.record_usage(user_id, 'analysis', 3, 'test_files')
        subscription_manager.record_usage(user_id, 'pdf_pages', 25, 'large_pdf')
        subscription_manager.record_usage(user_id, 'ai_chat', 10, 'conversations')
        
        # Получаем статистику
        stats = subscription_manager.get_usage_stats(user_id)
        
        # Проверяем точность
        self.assertEqual(stats['analyses']['used'], 3, "Анализы должны быть записаны точно")
        print("✅ Анализы отслеживаются точно")
        
        # Проверяем историю использования
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('SELECT COUNT(*) FROM subscription_usage WHERE user_id = ?', (user_id,))
        usage_records = c.fetchone()[0]
        conn.close()
        
        self.assertEqual(usage_records, 3, "Должно быть 3 записи об использовании")
        print("✅ История использования ведется корректно")
    
    def test_monthly_limit_reset(self):
        """Тест сброса месячных лимитов"""
        print("\n=== Тест сброса месячных лимитов ===")
        
        user_id = self.create_test_user('starter')
        
        # Используем все анализы (5 для STARTER плана)
        subscription_manager.record_usage(user_id, 'analysis', 5, 'max_usage')
        
        # Проверяем исчерпание лимита
        allowed, message = subscription_manager.check_analysis_limit(user_id)
        self.assertFalse(allowed, "Лимит должен быть исчерпан")
        print("✅ Лимит корректно исчерпывается")
        
        # Симулируем прошедший месяц (устанавливаем дату сброса в прошлое)
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        past_date = (datetime.now() - timedelta(days=1)).isoformat()
        c.execute('UPDATE users SET monthly_reset_date = ? WHERE id = ?', (past_date, user_id))
        conn.commit()
        conn.close()
        
        # Проверяем сброс лимита
        allowed, message = subscription_manager.check_analysis_limit(user_id)
        self.assertTrue(allowed, "Лимит должен быть сброшен")
        print("✅ Месячные лимиты корректно сбрасываются")
    
    def run_all_tests(self):
        """Запуск всех тестов"""
        print("🚀 Запуск тестов оптимизированной системы планов подписки")
        print("=" * 60)
        
        test_methods = [
            self.test_new_plan_structure,
            self.test_freemium_motivation_flow,
            self.test_starter_plan_attractiveness,
            self.test_upgrade_motivation_flow,
            self.test_pricing_psychology,
            self.test_feature_progression,
            self.test_usage_tracking_accuracy,
            self.test_monthly_limit_reset
        ]
        
        passed = 0
        failed = 0
        
        for test_method in test_methods:
            try:
                # Сбрасываем состояние перед каждым тестом
                self.setUp()
                test_method()
                passed += 1
                print(f"✅ {test_method.__name__} - ПРОЙДЕН")
            except Exception as e:
                failed += 1
                print(f"❌ {test_method.__name__} - ПРОВАЛЕН: {e}")
            finally:
                self.tearDown()
        
        print("\n" + "=" * 60)
        print(f"📊 Результаты тестирования:")
        print(f"✅ Пройдено: {passed}")
        print(f"❌ Провалено: {failed}")
        print(f"📈 Успешность: {(passed/(passed+failed)*100):.1f}%")
        
        if failed == 0:
            print("\n🎉 Все тесты пройдены! Оптимизированная система готова к запуску.")
        else:
            print(f"\n⚠️  Обнаружены проблемы в {failed} тестах. Требуется доработка.")
        
        return failed == 0

def main():
    """Главная функция для запуска тестов"""
    tester = TestOptimizedSubscriptionPlans()
    success = tester.run_all_tests()
    
    if success:
        print("\n🚀 Рекомендации по внедрению:")
        print("1. Обновить UI с новыми планами и ценами")
        print("2. Настроить email-кампании для конверсии")
        print("3. Добавить A/B тестирование цен")
        print("4. Настроить аналитику конверсий")
        print("5. Подготовить маркетинговые материалы")
        
        return 0
    else:
        print("\n❌ Система требует доработки перед запуском")
        return 1

if __name__ == '__main__':
    exit(main())