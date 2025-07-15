// Простая и эффективная система распознавания математики
function smartMathDetection(content) {
    console.log('Smart math detection starting...');
    
    // Стратегия: найти целые предложения с математикой и обернуть их полностью
    
    // Паттерны для поиска математических предложений
    const patterns = [
        // Уравнения с греческими буквами и функциями
        /([^.!?\n]*(?:ξi|λi|σ|max|min|exp|sign)[^.!?\n]*[.!?]?)/gi,
        // Выражения с неравенствами и математическими символами  
        /([^.!?\n]*(?:[<>=]|[*+\-/]|\^|\|)[^.!?\n]*(?:λ|σ|ξ|C)[^.!?\n]*[.!?]?)/gi,
        // Функции и формулы
        /([^.!?\n]*(?:[a-zA-Z]\([^)]*\)|K\([^)]*\))[^.!?\n]*[.!?]?)/gi
    ];
    
    patterns.forEach(pattern => {
        content = content.replace(pattern, (match) => {
            const trimmed = match.trim();
            
            // Пропустить если уже обработано или слишком короткое
            if (trimmed.includes('<') || trimmed.includes('mjx-') || trimmed.length < 10) {
                return match;
            }
            
            // Проверить, содержит ли математические элементы
            if (containsMath(trimmed)) {
                console.log('Converting to math:', trimmed);
                return `$${cleanMathExpression(trimmed)}$`;
            }
            
            return match;
        });
    });
    
    return content;
}

function containsMath(text) {
    const mathIndicators = [
        /[ξλσπφμωαβγδθ]/i,  // Греческие буквы
        /exp\(|sign\(|max\s|min\s/i,  // Функции
        /[<>=]/,  // Операторы сравнения
        /\^[0-9]/,  // Степени
        /_[a-zA-Z0-9]/,  // Индексы
        /\|\|/,  // Нормы
        /[*]/  // Умножение
    ];
    
    return mathIndicators.some(pattern => pattern.test(text));
}

function cleanMathExpression(text) {
    let cleaned = text;
    
    // Убрать точки в конце
    cleaned = cleaned.replace(/[.!?]+$/, '');
    
    // Преобразовать в LaTeX
    cleaned = cleaned.replace(/ξi/g, '\\xi_i');
    cleaned = cleaned.replace(/λi/g, '\\lambda_i');
    cleaned = cleaned.replace(/σ/g, '\\sigma');
    cleaned = cleaned.replace(/λ/g, '\\lambda');
    cleaned = cleaned.replace(/exp\(/g, '\\exp(');
    cleaned = cleaned.replace(/sign\(/g, '\\text{sign}(');
    cleaned = cleaned.replace(/max\s/g, '\\max ');
    cleaned = cleaned.replace(/min\s/g, '\\min ');
    cleaned = cleaned.replace(/\*/g, ' \\cdot ');
    cleaned = cleaned.replace(/\|\|/g, '\\|');
    
    return cleaned;
}