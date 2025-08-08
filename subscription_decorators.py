"""
Декораторы для проверки ограничений подписки
"""
from functools import wraps
from flask import jsonify, flash, redirect, url_for, request
from flask_login import current_user
from subscription_manager import subscription_manager
import logging

logger = logging.getLogger(__name__)

def require_subscription_limit(limit_type, **kwargs):
    """
    Декоратор для проверки ограничений подписки
    
    Args:
        limit_type: тип ограничения ('analysis', 'pdf_pages', 'video_duration', 'ai_chat', 'feature')
        **kwargs: дополнительные параметры для проверки
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **func_kwargs):
            if not current_user.is_authenticated:
                flash('Необходимо войти в систему', 'error')
                return redirect(url_for('login'))
            
            user_id = current_user.id
            
            # Проверяем различные типы ограничений
            if limit_type == 'analysis':
                allowed, message = subscription_manager.check_analysis_limit(user_id)
                if not allowed:
                    if request.is_json:
                        return jsonify({'error': message, 'limit_exceeded': True}), 403
                    flash(message, 'error')
                    return redirect(url_for('dashboard'))
            
            elif limit_type == 'pdf_pages':
                pages_count = kwargs.get('pages_count') or func_kwargs.get('pages_count')
                if pages_count:
                    allowed, message = subscription_manager.check_pdf_pages_limit(user_id, pages_count)
                    if not allowed:
                        if request.is_json:
                            return jsonify({'error': message, 'limit_exceeded': True}), 403
                        flash(message, 'error')
                        return redirect(url_for('dashboard'))
            
            elif limit_type == 'video_duration':
                duration = kwargs.get('duration_minutes') or func_kwargs.get('duration_minutes')
                if duration:
                    allowed, message = subscription_manager.check_video_duration_limit(user_id, duration)
                    if not allowed:
                        if request.is_json:
                            return jsonify({'error': message, 'limit_exceeded': True}), 403
                        flash(message, 'error')
                        return redirect(url_for('dashboard'))
            
            elif limit_type == 'ai_chat':
                allowed, message = subscription_manager.check_ai_chat_limit(user_id)
                if not allowed:
                    if request.is_json:
                        return jsonify({'error': message, 'limit_exceeded': True}), 403
                    flash(message, 'error')
                    return redirect(url_for('dashboard'))
            
            elif limit_type == 'feature':
                feature = kwargs.get('feature') or func_kwargs.get('feature')
                if feature and not subscription_manager.check_feature_access(user_id, feature):
                    message = f"Функция '{feature}' недоступна в вашем плане подписки"
                    if request.is_json:
                        return jsonify({'error': message, 'feature_unavailable': True}), 403
                    flash(message, 'error')
                    return redirect(url_for('dashboard'))
            
            return f(*args, **func_kwargs)
        return decorated_function
    return decorator

def track_usage(usage_type, amount_key=None, resource_info_key=None):
    """
    Декоратор для отслеживания использования ресурсов
    
    Args:
        usage_type: тип использования ('analysis', 'pdf_pages', 'video_minutes', 'ai_chat')
        amount_key: ключ для получения количества из kwargs функции
        resource_info_key: ключ для получения информации о ресурсе
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            result = f(*args, **kwargs)
            
            if current_user.is_authenticated:
                user_id = current_user.id
                amount = 1
                resource_info = None
                
                # Получаем количество из kwargs если указан ключ
                if amount_key and amount_key in kwargs:
                    amount = kwargs[amount_key]
                
                # Получаем информацию о ресурсе если указан ключ
                if resource_info_key and resource_info_key in kwargs:
                    resource_info = str(kwargs[resource_info_key])
                
                try:
                    subscription_manager.record_usage(user_id, usage_type, amount, resource_info)
                except Exception as e:
                    logger.error(f"Error tracking usage: {e}")
            
            return result
        return decorated_function
    return decorator

def subscription_required(plans=None):
    """
    Декоратор для проверки наличия определенного плана подписки
    
    Args:
        plans: список допустимых планов (например, ['basic', 'pro'])
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                flash('Необходимо войти в систему', 'error')
                return redirect(url_for('login'))
            
            if plans:
                subscription = subscription_manager.get_user_subscription(current_user.id)
                if not subscription or subscription['type'] not in plans:
                    message = f"Требуется план подписки: {', '.join(plans)}"
                    if request.is_json:
                        return jsonify({'error': message, 'subscription_required': True}), 403
                    flash(message, 'error')
                    return redirect(url_for('pricing'))
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator