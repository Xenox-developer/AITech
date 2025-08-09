// Скрипт для отладки проблемы с отменой анализа
// Вставьте этот код в консоль браузера (F12) для диагностики

console.log('🔍 ДИАГНОСТИКА ОТМЕНЫ АНАЛИЗА');
console.log('================================');

// Проверяем текущие значения переменных
console.log('📊 Текущие значения переменных:');
console.log('   currentTaskId:', typeof currentTaskId !== 'undefined' ? currentTaskId : 'UNDEFINED');
console.log('   currentUploadXHR:', typeof currentUploadXHR !== 'undefined' ? !!currentUploadXHR : 'UNDEFINED');
console.log('   analysisStatusInterval:', typeof analysisStatusInterval !== 'undefined' ? !!analysisStatusInterval : 'UNDEFINED');

// Проверяем состояние модального окна
const modal = document.getElementById('processing-modal');
console.log('🔍 Состояние модального окна:');
console.log('   Найдено:', !!modal);
if (modal) {
    console.log('   Активно:', modal.classList.contains('active'));
    console.log('   Классы:', modal.className);
}

// Проверяем кнопку отмены
const cancelBtn = document.querySelector('button[onclick*="cancelAnalysis"]');
console.log('🔍 Кнопка отмены:');
console.log('   Найдена:', !!cancelBtn);
if (cancelBtn) {
    console.log('   Текст:', cancelBtn.textContent.trim());
    console.log('   Видима:', cancelBtn.offsetParent !== null);
}

// Функция для мониторинга переменных
function monitorVariables() {
    console.log('📊 Мониторинг переменных каждые 2 секунды...');
    
    setInterval(() => {
        const taskId = typeof currentTaskId !== 'undefined' ? currentTaskId : 'UNDEFINED';
        const uploadXHR = typeof currentUploadXHR !== 'undefined' ? !!currentUploadXHR : 'UNDEFINED';
        const statusInterval = typeof analysisStatusInterval !== 'undefined' ? !!analysisStatusInterval : 'UNDEFINED';
        
        console.log(`[${new Date().toLocaleTimeString()}] taskId: ${taskId}, uploadXHR: ${uploadXHR}, interval: ${statusInterval}`);
    }, 2000);
}

// Функция для принудительной отмены
function forceCancel() {
    console.log('🔴 ПРИНУДИТЕЛЬНАЯ ОТМЕНА');
    
    // Пытаемся найти task_id из URL или других источников
    let taskId = null;
    
    // Проверяем localStorage
    if (typeof localStorage !== 'undefined') {
        taskId = localStorage.getItem('currentTaskId');
        console.log('   TaskId из localStorage:', taskId);
    }
    
    // Проверяем sessionStorage
    if (typeof sessionStorage !== 'undefined') {
        taskId = sessionStorage.getItem('currentTaskId');
        console.log('   TaskId из sessionStorage:', taskId);
    }
    
    // Если нашли task_id, пытаемся отменить
    if (taskId) {
        console.log('   Пытаемся отменить задачу:', taskId);
        
        fetch(`/api/analysis/cancel/${taskId}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            }
        })
        .then(response => response.json())
        .then(data => {
            console.log('   Результат отмены:', data);
            if (data.success) {
                alert('Анализ отменен принудительно!');
                location.reload();
            } else {
                alert('Ошибка отмены: ' + data.error);
            }
        })
        .catch(error => {
            console.error('   Ошибка запроса отмены:', error);
            alert('Ошибка сети при отмене');
        });
    } else {
        console.log('   TaskId не найден');
        alert('Не удалось найти ID задачи для отмены');
    }
}

// Функция для тестирования cancelAnalysis
function testCancelAnalysis() {
    console.log('🧪 ТЕСТИРОВАНИЕ cancelAnalysis()');
    
    if (typeof cancelAnalysis === 'function') {
        console.log('   Функция cancelAnalysis найдена');
        try {
            cancelAnalysis();
        } catch (error) {
            console.error('   Ошибка при вызове cancelAnalysis:', error);
        }
    } else {
        console.log('   Функция cancelAnalysis НЕ НАЙДЕНА');
    }
}

console.log('🛠️ Доступные команды:');
console.log('   monitorVariables() - запустить мониторинг переменных');
console.log('   forceCancel() - принудительная отмена анализа');
console.log('   testCancelAnalysis() - тестирование функции отмены');

// Автоматически запускаем мониторинг
monitorVariables();