"""
Менеджер задач анализа с возможностью отмены
"""

import sqlite3
import threading
import time
import logging
from datetime import datetime
from typing import Optional, Dict, Any
from pathlib import Path

logger = logging.getLogger(__name__)

class AnalysisManager:
    """Менеджер для управления задачами анализа"""
    
    def __init__(self):
        self.active_tasks = {}  # task_id -> {'thread': thread, 'cancelled': bool}
        self.lock = threading.Lock()
    
    def create_task(self, user_id: int, filename: str) -> int:
        """Создание новой задачи анализа"""
        conn = sqlite3.connect('ai_study.db')
        c = conn.cursor()
        
        c.execute('''
            INSERT INTO analysis_tasks (user_id, filename, status)
            VALUES (?, ?, 'processing')
        ''', (user_id, filename))
        
        task_id = c.lastrowid
        conn.commit()
        conn.close()
        
        logger.info(f"Created analysis task {task_id} for user {user_id}, file: {filename}")
        return task_id
    
    def cancel_task(self, task_id: int, user_id: int) -> bool:
        """Отмена задачи анализа"""
        logger.info(f"🔴 cancel_task вызвана для задачи {task_id}, пользователь {user_id}")
        
        with self.lock:
            # Проверяем, что задача принадлежит пользователю
            conn = sqlite3.connect('ai_study.db')
            c = conn.cursor()
            
            logger.info(f"🔍 Ищем задачу {task_id} для пользователя {user_id}")
            c.execute('''
                SELECT id, status FROM analysis_tasks 
                WHERE id = ? AND user_id = ?
            ''', (task_id, user_id))
            
            task = c.fetchone()
            if not task:
                logger.warning(f"⚠️ Задача {task_id} не найдена для пользователя {user_id}")
                conn.close()
                return False
            
            task_id_db, status = task
            logger.info(f"📋 Найдена задача {task_id_db} со статусом '{status}'")
            
            # Если задача уже завершена, нельзя отменить
            if status in ['completed', 'cancelled', 'failed']:
                logger.warning(f"⚠️ Задача {task_id} уже завершена со статусом '{status}', отмена невозможна")
                conn.close()
                return False
            
            # Помечаем задачу как отмененную в БД
            logger.info(f"💾 Обновляем статус задачи {task_id} на 'cancelled'")
            c.execute('''
                UPDATE analysis_tasks 
                SET status = 'cancelled', cancelled_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (task_id,))
            
            conn.commit()
            conn.close()
            
            # Помечаем задачу как отмененную в памяти
            if task_id in self.active_tasks:
                self.active_tasks[task_id]['cancelled'] = True
                logger.info(f"🧠 Помечена задача {task_id} как отмененная в памяти")
            else:
                logger.info(f"🧠 Задача {task_id} не найдена в активных задачах памяти")
            
            logger.info(f"✅ Успешно отменена задача {task_id} для пользователя {user_id}")
            return True
    
    def is_task_cancelled(self, task_id: int) -> bool:
        """Проверка, отменена ли задача"""
        with self.lock:
            if task_id in self.active_tasks:
                return self.active_tasks[task_id]['cancelled']
            
            # Проверяем в БД
            conn = sqlite3.connect('ai_study.db')
            c = conn.cursor()
            
            c.execute('''
                SELECT status FROM analysis_tasks WHERE id = ?
            ''', (task_id,))
            
            result = c.fetchone()
            conn.close()
            
            if result:
                return result[0] == 'cancelled'
            
            return False
    
    def complete_task(self, task_id: int, result_id: Optional[int] = None, error: Optional[str] = None):
        """Завершение задачи анализа"""
        with self.lock:
            # Удаляем из активных задач
            if task_id in self.active_tasks:
                del self.active_tasks[task_id]
            
            # Обновляем статус в БД
            conn = sqlite3.connect('ai_study.db')
            c = conn.cursor()
            
            if error:
                c.execute('''
                    UPDATE analysis_tasks 
                    SET status = 'failed', completed_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                ''', (task_id,))
                logger.error(f"Task {task_id} failed: {error}")
            else:
                c.execute('''
                    UPDATE analysis_tasks 
                    SET status = 'completed', completed_at = CURRENT_TIMESTAMP, result_id = ?
                    WHERE id = ?
                ''', (result_id, task_id))
                logger.info(f"Task {task_id} completed successfully with result {result_id}")
            
            conn.commit()
            conn.close()
    
    def start_analysis_task(self, task_id: int, user_id: int, filepath: str, filename: str, page_range: str = None):
        """Запуск задачи анализа в отдельном потоке"""
        def analysis_worker():
            try:
                logger.info(f"Starting analysis task {task_id}")
                
                # Импортируем здесь, чтобы избежать циклических импортов
                from ml import process_file_with_cancellation
                from app import save_result
                
                # Обрабатываем файл с проверкой отмены
                analysis_result = process_file_with_cancellation(filepath, filename, task_id, self, page_range)
                
                # Проверяем, не была ли задача отменена
                if self.is_task_cancelled(task_id):
                    logger.info(f"Task {task_id} was cancelled during processing")
                    # ✅ УЛУЧШЕНО: Удаляем файл при отмене с логированием
                    if Path(filepath).exists():
                        try:
                            file_size = Path(filepath).stat().st_size
                            Path(filepath).unlink()
                            logger.info(f"🗑️ File deleted after cancellation: {filename} ({file_size} bytes)")
                        except Exception as cleanup_error:
                            logger.warning(f"⚠️ Error deleting cancelled file {filepath}: {cleanup_error}")
                    else:
                        logger.warning(f"⚠️ File not found for deletion after cancellation: {filepath}")
                    return
                
                # Сохраняем результат
                file_type = Path(filename).suffix.lower()
                page_info = None
                if file_type in ['.pdf', '.pptx'] and page_range:
                    page_info = {
                        'page_range': page_range,
                        'processed_at': datetime.now().isoformat(),
                        'file_type': file_type
                    }
                
                access_token = save_result(filename, file_type, analysis_result, page_info, user_id, task_id, self)
                
                # Получаем result_id по access_token
                conn = sqlite3.connect('ai_study.db')
                c = conn.cursor()
                c.execute('SELECT id FROM result WHERE access_token = ?', (access_token,))
                result = c.fetchone()
                result_id = result[0] if result else None
                conn.close()
                
                # Начисление XP за анализ документа
                try:
                    from gamification import gamification
                    from flask_login import current_user
                    
                    xp_result = gamification.award_xp(
                        user_id, 
                        'document_analysis', 
                        f'Анализ {Path(filename).suffix.upper()} файла: {filename}',
                        {'file_type': Path(filename).suffix.lower(), 'filename': filename}
                    )
                    
                    # Обновляем ежедневную серию
                    streak_result = gamification.update_daily_streak(user_id)
                    
                    logger.info(f"XP awarded for task {task_id}: {xp_result}")
                    
                except Exception as e:
                    logger.warning(f"Failed to award XP for task {task_id}: {e}")
                
                # Завершаем задачу
                self.complete_task(task_id, result_id)
                
                # Удаляем файл
                if Path(filepath).exists():
                    Path(filepath).unlink()
                
                logger.info(f"Analysis task {task_id} completed successfully")
                
            except Exception as e:
                logger.error(f"Analysis task {task_id} failed: {str(e)}")
                self.complete_task(task_id, error=str(e))
                
                # ✅ УЛУЧШЕНО: Удаляем файл при ошибке с логированием
                if Path(filepath).exists():
                    try:
                        file_size = Path(filepath).stat().st_size
                        Path(filepath).unlink()
                        logger.info(f"🗑️ File deleted after error: {filename} ({file_size} bytes)")
                    except Exception as cleanup_error:
                        logger.warning(f"⚠️ Error deleting file {filepath}: {cleanup_error}")
                else:
                    logger.warning(f"⚠️ File not found for deletion after error: {filepath}")
        
        # Создаем и запускаем поток
        thread = threading.Thread(target=analysis_worker, daemon=True)
        
        with self.lock:
            self.active_tasks[task_id] = {
                'thread': thread,
                'cancelled': False
            }
        
        thread.start()
        logger.info(f"Started analysis task {task_id} in background thread")

    def start_video_analysis_task(self, task_id: int, user_id: int, filepath: str, filename: str, video_info: dict = None):
        """Запуск задачи анализа видео в отдельном потоке"""
        def video_analysis_worker():
            try:
                logger.info(f"Starting video analysis task {task_id}")
                
                # Импортируем здесь, чтобы избежать циклических импортов
                from ml import process_file_with_cancellation
                from app import save_result
                from gamification import gamification
                
                # Обрабатываем видео с проверкой отмены
                analysis_result = process_file_with_cancellation(filepath, filename, task_id, self)
                
                # Проверяем, не была ли задача отменена
                if self.is_task_cancelled(task_id):
                    logger.info(f"Video task {task_id} was cancelled during processing")
                    # ✅ УЛУЧШЕНО: Удаляем видеофайл при отмене с логированием
                    if Path(filepath).exists():
                        try:
                            file_size = Path(filepath).stat().st_size
                            Path(filepath).unlink()
                            logger.info(f"🗑️ Video file deleted after cancellation: {filename} ({file_size} bytes)")
                        except Exception as cleanup_error:
                            logger.warning(f"⚠️ Error deleting cancelled video file {filepath}: {cleanup_error}")
                    else:
                        logger.warning(f"⚠️ Video file not found for deletion after cancellation: {filepath}")
                    return
                
                # Сохраняем результат с информацией о видео
                access_token = save_result(filename, '.mp4', analysis_result, video_info, user_id, task_id, self)
                
                # Получаем result_id по access_token
                conn = sqlite3.connect('ai_study.db')
                c = conn.cursor()
                c.execute('SELECT id FROM result WHERE access_token = ?', (access_token,))
                result = c.fetchone()
                result_id = result[0] if result else None
                conn.close()
                
                # Начисление XP за анализ видео
                try:
                    video_duration = video_info.get('duration_minutes', 0) if video_info else 0
                    xp_result = gamification.award_xp(
                        user_id, 
                        'video_analysis', 
                        f'Анализ видео: {filename} ({video_duration:.1f} мин)',
                        {'filename': filename, 'duration': video_duration, 'source': 'url'}
                    )
                    
                    # Дополнительный XP за длинное видео
                    if video_duration > 30:
                        gamification.award_xp(
                            user_id,
                            'long_study_session',
                            f'Анализ длинного видео ({video_duration:.1f} мин)'
                        )
                    
                    # Обновляем ежедневную серию
                    streak_result = gamification.update_daily_streak(user_id)
                    
                    logger.info(f"XP awarded for video task {task_id}: {xp_result}")
                    
                except Exception as e:
                    logger.warning(f"Failed to award XP for video task {task_id}: {e}")
                
                # Завершаем задачу
                self.complete_task(task_id, result_id)
                
                # ✅ УЛУЧШЕНО: Удаляем видеофайл после успешного анализа
                if Path(filepath).exists():
                    file_size = Path(filepath).stat().st_size
                    Path(filepath).unlink()
                    logger.info(f"🗑️ Video file deleted after successful analysis: {filename} ({file_size} bytes)")
                else:
                    logger.warning(f"⚠️ Video file not found for deletion: {filepath}")
                
                logger.info(f"✅ Video analysis task {task_id} completed successfully")
                
            except Exception as e:
                logger.error(f"Video analysis task {task_id} failed: {str(e)}")
                self.complete_task(task_id, error=str(e))
                
                # ✅ УЛУЧШЕНО: Удаляем видеофайл при ошибке с логированием
                if Path(filepath).exists():
                    try:
                        file_size = Path(filepath).stat().st_size
                        Path(filepath).unlink()
                        logger.info(f"🗑️ Video file deleted after error: {filename} ({file_size} bytes)")
                    except Exception as cleanup_error:
                        logger.warning(f"⚠️ Error deleting video file {filepath}: {cleanup_error}")
                else:
                    logger.warning(f"⚠️ Video file not found for deletion after error: {filepath}")
        
        # Создаем и запускаем поток
        thread = threading.Thread(target=video_analysis_worker, daemon=True)
        
        with self.lock:
            self.active_tasks[task_id] = {
                'thread': thread,
                'cancelled': False
            }
        
        thread.start()
        logger.info(f"Started video analysis task {task_id} in background thread")
    
    def update_task_progress(self, task_id: int, progress: int, stage: str, details: str = ""):
        """Обновление прогресса задачи"""
        conn = sqlite3.connect('ai_study.db')
        c = conn.cursor()
        
        c.execute('''
            UPDATE analysis_tasks 
            SET progress = ?, current_stage = ?, stage_details = ?
            WHERE id = ?
        ''', (progress, stage, details, task_id))
        
        conn.commit()
        conn.close()
        
        logger.info(f"📊 Обновлен прогресс задачи {task_id}: {progress}% - {stage}")

    def update_task_filename(self, task_id: int, filename: str):
        """Обновление имени файла в задаче"""
        conn = sqlite3.connect('ai_study.db')
        c = conn.cursor()
        
        c.execute('''
            UPDATE analysis_tasks 
            SET filename = ?
            WHERE id = ?
        ''', (filename, task_id))
        
        conn.commit()
        conn.close()
        
        logger.info(f"📝 Обновлено имя файла для задачи {task_id}: {filename}")

    def get_task_status(self, task_id: int, user_id: int) -> Optional[Dict[str, Any]]:
        """Получение статуса задачи"""
        conn = sqlite3.connect('ai_study.db')
        c = conn.cursor()
        
        c.execute('''
            SELECT id, filename, status, created_at, completed_at, cancelled_at, result_id, 
                   progress, current_stage, stage_details
            FROM analysis_tasks 
            WHERE id = ? AND user_id = ?
        ''', (task_id, user_id))
        
        result = c.fetchone()
        conn.close()
        
        if not result:
            return None
        
        task_id_db, filename, status, created_at, completed_at, cancelled_at, result_id, progress, current_stage, stage_details = result
        
        return {
            'id': task_id_db,
            'filename': filename,
            'status': status,
            'created_at': created_at,
            'completed_at': completed_at,
            'cancelled_at': cancelled_at,
            'result_id': result_id,
            'progress': progress or 0,
            'current_stage': current_stage or 'Подготовка',
            'stage_details': stage_details or ''
        }
    
    def cleanup_old_tasks(self, days: int = 7):
        """Очистка старых задач"""
        conn = sqlite3.connect('ai_study.db')
        c = conn.cursor()
        
        c.execute('''
            DELETE FROM analysis_tasks 
            WHERE created_at < datetime('now', '-{} days')
        '''.format(days))
        
        deleted_count = c.rowcount
        conn.commit()
        conn.close()
        
        logger.info(f"Cleaned up {deleted_count} old analysis tasks")

    def cleanup_orphaned_files(self, upload_folder: str = "uploads", max_age_hours: int = 24):
        """Очистка осиротевших файлов в папке uploads"""
        if not os.path.exists(upload_folder):
            logger.info(f"Upload folder {upload_folder} does not exist, skipping cleanup")
            return
        
        import os
        import time
        
        current_time = time.time()
        cleaned_files = 0
        cleaned_size = 0
        
        logger.info(f"🧹 Starting cleanup of orphaned files in {upload_folder}")
        
        try:
            # Получаем список всех активных файлов из БД
            conn = sqlite3.connect('ai_study.db')
            c = conn.cursor()
            
            c.execute('''
                SELECT filename FROM analysis_tasks 
                WHERE status = 'processing'
            ''')
            
            active_files = set()
            for row in c.fetchall():
                filename = row[0]
                if filename and not filename.startswith('video_from_url_'):
                    active_files.add(filename)
            
            conn.close()
            
            # Проверяем все файлы в папке uploads
            for filename in os.listdir(upload_folder):
                filepath = os.path.join(upload_folder, filename)
                
                # Пропускаем директории
                if os.path.isdir(filepath):
                    continue
                
                # Проверяем возраст файла
                file_age_hours = (current_time - os.path.getmtime(filepath)) / 3600
                
                # Если файл старше max_age_hours и не активен, удаляем
                if file_age_hours > max_age_hours and filename not in active_files:
                    try:
                        file_size = os.path.getsize(filepath)
                        os.remove(filepath)
                        cleaned_files += 1
                        cleaned_size += file_size
                        logger.info(f"🗑️ Removed orphaned file: {filename} ({file_size} bytes, {file_age_hours:.1f}h old)")
                    except Exception as e:
                        logger.warning(f"⚠️ Error removing orphaned file {filepath}: {e}")
            
            if cleaned_files > 0:
                logger.info(f"✅ Cleanup completed: {cleaned_files} files removed, {cleaned_size / (1024*1024):.1f} MB freed")
            else:
                logger.info("✅ Cleanup completed: no orphaned files found")
                
        except Exception as e:
            logger.error(f"❌ Error during orphaned files cleanup: {e}")

    def cleanup_all(self, upload_folder: str = "uploads", task_days: int = 7, file_hours: int = 24):
        """Полная очистка: старые задачи и осиротевшие файлы"""
        logger.info("🧹 Starting full cleanup process")
        
        # Очищаем старые задачи
        self.cleanup_old_tasks(task_days)
        
        # Очищаем осиротевшие файлы
        self.cleanup_orphaned_files(upload_folder, file_hours)
        
        logger.info("✅ Full cleanup process completed")

# Глобальный экземпляр менеджера
analysis_manager = AnalysisManager()