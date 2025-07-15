    // Load study progress
    fetch(`/api/study_progress/{{ result_id }}`)
        .then(response => response.json())
        .then(data => {
            const progressHtml = `
                <div class="row text-center">
                    <div class="col-md-4">
                        <h3 class="text-primary">${data.total_cards}</h3>
                        <p class="text-muted mb-0">Всего карточек</p>
                    </div>
                    <div class="col-md-4">
                        <h3 class="text-info">${data.reviewed_cards}</h3>
                        <p class="text-muted mb-0">Изучено</p>
                    </div>
                    <div class="col-md-4">
                        <h3 class="text-success">${data.mastered_cards}</h3>
                        <p class="text-muted mb-0">Освоено</p>
                    </div>
                </div>
                <div class="progress mt-3" style="height: 25px;">
                    <div class="progress-bar bg-success" style="width: ${data.progress_percentage}%">
                        ${data.progress_percentage}%
                    </div>
                </div>
            `;
            document.getElementById('progressContainer').innerHTML = progressHtml;
        });

    // Enhanced Flashcard Functions
    let flashcardProgress = {};
    let currentStudySession = null;
    
    function filterCards(type) {
        const cards = document.querySelectorAll('.flashcard-advanced');
        let visibleCount = 0;
        
        cards.forEach(card => {
            if (type === 'all' || card.dataset.type === type) {
                card.style.display = 'block';
                visibleCount++;
            } else {
                card.style.display = 'none';
            }
        });
        
        // Update active button
        document.querySelectorAll('[data-filter]').forEach(btn => {
            btn.classList.remove('active');
        });
        document.querySelector(`[data-filter="${type}"]`).classList.add('active');
        
        // Show/hide no cards message
        document.getElementById('noCardsMessage').style.display = visibleCount === 0 ? 'block' : 'none';
        
        updateFlashcardStats();
    }

    function searchFlashcards() {
        const searchTerm = document.getElementById('flashcardSearch').value.toLowerCase();
        const cards = document.querySelectorAll('.flashcard-advanced');
        let visibleCount = 0;
        
        cards.forEach(card => {
            const question = card.querySelector('.flashcard-question').textContent.toLowerCase();
            const answer = card.querySelector('.answer-content').textContent.toLowerCase();
            
            if (question.includes(searchTerm) || answer.includes(searchTerm)) {
                card.style.display = 'block';
                visibleCount++;
            } else {
                card.style.display = 'none';
            }
        });
        
        document.getElementById('noCardsMessage').style.display = visibleCount === 0 ? 'block' : 'none';
    }

    function sortCards(criteria) {
        const container = document.getElementById('flashcardsAccordion');
        const cards = Array.from(container.querySelectorAll('.flashcard-advanced'));
        
        cards.sort((a, b) => {
            switch(criteria) {
                case 'difficulty':
                    return parseInt(a.dataset.difficulty) - parseInt(b.dataset.difficulty);
                case 'type':
                    return a.dataset.type.localeCompare(b.dataset.type);
                case 'progress':
                    const progressA = flashcardProgress[a.dataset.cardId] || 0;
                    const progressB = flashcardProgress[b.dataset.cardId] || 0;
                    return progressB - progressA;
                default:
                    return 0;
            }
        });
        
        // Re-append sorted cards
        cards.forEach(card => container.appendChild(card));
        
        // Show toast notification
        showToast(`Карты отсортированы по ${criteria === 'difficulty' ? 'сложности' : criteria === 'type' ? 'типу' : 'прогрессу'}`, 'info');
    }

    function startInteractiveStudy() {
        const modal = new bootstrap.Modal(document.getElementById('interactiveStudyModal'));
        const modalBody = document.getElementById('studyModalBody');
        
        // Get cards that need review
        const cards = Array.from(document.querySelectorAll('.flashcard-advanced')).filter(card => 
            card.style.display !== 'none'
        );
        
        if (cards.length === 0) {
            showToast('Нет доступных карт для изучения', 'warning');
            return;
        }
        
        currentStudySession = {
            cards: cards,
            currentIndex: 0,
            correct: 0,
            total: cards.length
        };
        
        modalBody.innerHTML = `
            <div class="study-session-container">
                <div class="progress mb-3">
                    <div class="progress-bar" role="progressbar" style="width: 0%" id="studyProgress"></div>
                </div>
                <div class="text-center mb-3">
                    <span class="badge bg-primary">Карта 1 из ${cards.length}</span>
                </div>
                <div class="study-card" id="studyCard">
                    <!-- Study card content will be loaded here -->
                </div>
                <div class="study-controls mt-4 text-center">
                    <button class="btn btn-outline-secondary" onclick="showStudyAnswer()" id="showAnswerBtn">
                        <i class="fas fa-eye me-1"></i>Показать ответ
                    </button>
                    <div id="studyAnswerControls" style="display: none;">
                        <button class="btn btn-danger me-2" onclick="studyCardResult(false)">
                            <i class="fas fa-times me-1"></i>Не знаю
                        </button>
                        <button class="btn btn-success" onclick="studyCardResult(true)">
                            <i class="fas fa-check me-1"></i>Знаю
                        </button>
                    </div>
                </div>
            </div>
        `;
        
        loadStudyCard();
        modal.show();
    }

    function loadStudyCard() {
        if (!currentStudySession) return;
        
        const card = currentStudySession.cards[currentStudySession.currentIndex];
        const question = card.querySelector('.flashcard-question').textContent;
        const cardNumber = currentStudySession.currentIndex + 1;
        const total = currentStudySession.total;
        
        document.getElementById('studyCard').innerHTML = `
            <div class="card">
                <div class="card-body text-center">
                    <h5 class="card-title mb-3">
                        <i class="fas fa-question-circle text-primary me-2"></i>
                        ${question}
                    </h5>
                    <div id="studyAnswer" style="display: none;">
                        <hr>
                        <div class="alert alert-success">
                            <i class="fas fa-check-circle me-2"></i>
                            ${card.querySelector('.answer-content').textContent}
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        // Update progress
        const progress = (cardNumber / total) * 100;
        document.getElementById('studyProgress').style.width = progress + '%';
        document.querySelector('.badge.bg-primary').textContent = `Карта ${cardNumber} из ${total}`;
        
        // Reset controls
        document.getElementById('showAnswerBtn').style.display = 'block';
        document.getElementById('studyAnswerControls').style.display = 'none';
    }

    function showStudyAnswer() {
        document.getElementById('studyAnswer').style.display = 'block';
        document.getElementById('showAnswerBtn').style.display = 'none';
        document.getElementById('studyAnswerControls').style.display = 'block';
    }

    function studyCardResult(correct) {
        if (!currentStudySession) return;
        
        if (correct) {
            currentStudySession.correct++;
        }
        
        currentStudySession.currentIndex++;
        
        if (currentStudySession.currentIndex >= currentStudySession.total) {
            // Session complete
            const accuracy = Math.round((currentStudySession.correct / currentStudySession.total) * 100);
            document.getElementById('studyModalBody').innerHTML = `
                <div class="text-center">
                    <i class="fas fa-trophy text-warning" style="font-size: 4rem;"></i>
                    <h4 class="mt-3">Сессия завершена!</h4>
                    <p class="lead">Правильных ответов: ${currentStudySession.correct} из ${currentStudySession.total}</p>
                    <div class="progress mb-3">
                        <div class="progress-bar bg-${accuracy >= 80 ? 'success' : accuracy >= 60 ? 'warning' : 'danger'}" 
                             style="width: ${accuracy}%">${accuracy}%</div>
                    </div>
                    <button class="btn btn-primary" onclick="startInteractiveStudy()">
                        <i class="fas fa-redo me-1"></i>Повторить сессию
                    </button>
                </div>
            `;
            currentStudySession = null;
        } else {
            loadStudyCard();
        }
    }

    function startQuizMode() {
        showToast('Режим теста будет добавлен в следующей версии', 'info');
    }

    function showCreateCardModal() {
        const modal = new bootstrap.Modal(document.getElementById('createCardModal'));
        modal.show();
    }

    function createNewCard() {
        const question = document.getElementById('newCardQuestion').value;
        const answer = document.getElementById('newCardAnswer').value;
        const type = document.getElementById('newCardType').value;
        const difficulty = document.getElementById('newCardDifficulty').value;
        const hint = document.getElementById('newCardHint').value;
        
        if (!question || !answer) {
            showToast('Заполните вопрос и ответ', 'warning');
            return;
        }
        
        // Here you would typically send this to the server
        // For now, just show success message
        showToast('Флеш-карта создана успешно!', 'success');
        
        // Close modal and reset form
        bootstrap.Modal.getInstance(document.getElementById('createCardModal')).hide();
        document.getElementById('createCardForm').reset();
    }

    function addToFavorites(cardId) {
        showToast('Карта добавлена в избранное', 'success');
        // Here you would save to favorites
    }

    function shareCard(cardId) {
        if (navigator.share) {
            navigator.share({
                title: 'Флеш-карта',
                text: 'Изучаем вместе!',
                url: window.location.href
            });
        } else {
            // Fallback - copy to clipboard
            navigator.clipboard.writeText(window.location.href);
            showToast('Ссылка скопирована в буфер обмена', 'info');
        }
    }

    function updateFlashcardStats() {
        // This would typically fetch real progress data
        const totalCards = document.querySelectorAll('.flashcard-advanced').length;
        const masteredCards = Object.values(flashcardProgress).filter(p => p >= 3).length;
        const reviewCards = Object.values(flashcardProgress).filter(p => p > 0 && p < 3).length;
        const newCards = totalCards - masteredCards - reviewCards;
        const progressPercent = totalCards > 0 ? Math.round((masteredCards / totalCards) * 100) : 0;
        
        document.getElementById('masteredCount').textContent = masteredCards;
        document.getElementById('reviewCount').textContent = reviewCards;
        document.getElementById('newCount').textContent = newCards;
        document.getElementById('progressPercent').textContent = progressPercent + '%';
    }

    function showToast(message, type = 'info') {
        const toast = document.createElement('div');
        toast.className = `alert alert-${type} position-fixed`;
        toast.style.cssText = 'top: 20px; right: 20px; z-index: 9999; min-width: 300px;';
        toast.innerHTML = `
            <i class="fas fa-${type === 'success' ? 'check-circle' : type === 'warning' ? 'exclamation-triangle' : 'info-circle'} me-2"></i>
            ${message}
            <button type="button" class="btn-close ms-2" onclick="this.parentElement.remove()"></button>
        `;
        document.body.appendChild(toast);
        
        setTimeout(() => toast.remove(), 4000);
    }

    // Enhanced mark card as reviewed with confidence levels
    function markCardReviewed(resultId, cardId, correct, confidence = 2) {
        fetch('/api/flashcard_progress', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                result_id: resultId,
                flashcard_id: cardId,
                correct: correct,
                confidence: confidence
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // Update progress indicator
                const progressIndicator = document.querySelector(`[data-card="${cardId}"]`);
                if (progressIndicator) {
                    const icon = progressIndicator.querySelector('i');
                    if (correct && confidence >= 3) {
                        icon.className = 'fas fa-check-circle text-success';
                        icon.title = 'Изучено';
                    } else if (correct && confidence >= 2) {
                        icon.className = 'fas fa-clock text-warning';
                        icon.title = 'На повторение';
                    } else {
                        icon.className = 'fas fa-times-circle text-danger';
                        icon.title = 'Требует изучения';
                    }
                }
                
                // Update buttons
                const buttons = event.target.parentElement.querySelectorAll('button');
                buttons.forEach(btn => {
                    btn.disabled = true;
                    btn.classList.remove('btn-outline-danger', 'btn-outline-warning', 'btn-outline-success');
                    btn.classList.add('btn-secondary');
                });
                
                // Update progress in memory
                flashcardProgress[cardId] = confidence;
                
                // Show feedback
                let message = '';
                let nextReview = '';
                
                if (correct && confidence >= 3) {
                    message = 'Отлично! Карта помечена как изученная.';
                    nextReview = data.next_review_days ? `Повторение через ${data.next_review_days} дней` : '';
                } else if (correct && confidence >= 2) {
                    message = 'Хорошо! Карта добавлена на повторение.';
                    nextReview = 'Повторение завтра';
                } else {
                    message = 'Карта будет показана снова для изучения.';
                    nextReview = 'Повторение сегодня';
                }
                
                showToast(message + (nextReview ? ' ' + nextReview : ''), 'success');
                
                // Update statistics
                updateFlashcardStats();
            }
        })
        .catch(error => {
            console.error('Error updating flashcard progress:', error);
            showToast('Ошибка при сохранении прогресса', 'danger');
        });
    }

    // Modern Mind Map Implementation
    let mindMapData = null;
    let currentLayout = 'radial';
    let mindMapNodes = [];
    let mindMapLinks = [];

    function initMindMap() {
        // Show loading
        document.getElementById('mindMapLoading').style.display = 'block';
        
        fetch(`/api/mind_map/{{ result_id }}`)
            .then(response => response.json())
            .then(data => {
                mindMapData = data;
                document.getElementById('mindMapLoading').style.display = 'none';
                drawModernMindMap();
            })
            .catch(error => {
                console.error('Error loading mind map:', error);
                document.getElementById('mindMapLoading').innerHTML = 
                    '<div class="text-danger"><i class="fas fa-exclamation-triangle"></i> Ошибка загрузки</div>';
            });
    }

    function drawModernMindMap() {
        if (!mindMapData || !mindMapData.branches) return;

        const svg = d3.select('#mindMapSvg');
        svg.selectAll('*').remove(); // Clear previous content
        
        const width = document.getElementById('mindMapSvg').clientWidth;
        const height = 500;

        // Prepare data
        prepareGraphData();
        
        // Update statistics
        updateMindMapStats();

        // Create main group with zoom capability
        const g = svg.append('g').attr('class', 'mind-map-group');

        // Add zoom behavior
        const zoom = d3.zoom()
            .scaleExtent([0.3, 3])
            .on('zoom', (event) => {
                g.attr('transform', event.transform);
            });

        svg.call(zoom);

        // Draw based on layout
        if (currentLayout === 'radial') {
            drawRadialLayout(g, width, height);
        } else if (currentLayout === 'tree') {
            drawTreeLayout(g, width, height);
        } else {
            drawForceLayout(g, width, height);
        }
    }

    function prepareGraphData() {
        mindMapNodes = [];
        mindMapLinks = [];

        // Central node
        mindMapNodes.push({
            id: 'central',
            name: mindMapData.central_topic || 'Основная тема',
            type: 'central',
            level: 0,
            color: '#667eea',
            size: 35,
            details: {
                title: mindMapData.central_topic || 'Основная тема',
                description: 'Центральная тема документа',
                type: 'Основная тема'
            }
        });

        // Branch nodes and their children
        mindMapData.branches.forEach((branch, branchIndex) => {
            const branchId = `branch-${branchIndex}`;
            
            mindMapNodes.push({
                id: branchId,
                name: branch.name,
                type: 'branch',
                level: 1,
                color: branch.color || '#4ECDC4',
                size: 25,
                details: {
                    title: branch.name,
                    description: `Важность: ${Math.round((branch.importance || 0.5) * 100)}%`,
                    type: 'Основная ветка',
                    children: branch.children ? branch.children.length : 0
                }
            });

            // Link from central to branch
            mindMapLinks.push({
                source: 'central',
                target: branchId,
                type: 'main'
            });

            // Child nodes
            if (branch.children) {
                branch.children.forEach((child, childIndex) => {
                    const childId = `child-${branchIndex}-${childIndex}`;
                    
                    mindMapNodes.push({
                        id: childId,
                        name: child.name,
                        type: 'child',
                        level: 2,
                        color: child.color || branch.color || '#96CEB4',
                        size: 18,
                        parent: branchId,
                        details: {
                            title: child.name,
                            description: `Подтема раздела "${branch.name}"`,
                            type: 'Подтема',
                            parent: branch.name
                        }
                    });

                    // Link from branch to child
                    mindMapLinks.push({
                        source: branchId,
                        target: childId,
                        type: 'sub'
                    });
                });
            }
        });
    }

    function drawRadialLayout(g, width, height) {
        const centerX = width / 2;
        const centerY = height / 2;

        // Position nodes
        const branches = mindMapNodes.filter(n => n.type === 'branch');
        const angleStep = (2 * Math.PI) / Math.max(branches.length, 1);

        // Position central node
        const centralNode = mindMapNodes.find(n => n.type === 'central');
        centralNode.x = centerX;
        centralNode.y = centerY;

        // Position branch nodes in circle
        branches.forEach((branch, index) => {
            const angle = index * angleStep - Math.PI / 2; // Start from top
            branch.x = centerX + Math.cos(angle) * 120;
            branch.y = centerY + Math.sin(angle) * 120;
        });

        // Position child nodes around their parents
        mindMapNodes.filter(n => n.type === 'child').forEach(child => {
            const parent = mindMapNodes.find(n => n.id === child.parent);
            if (parent) {
                const siblings = mindMapNodes.filter(n => n.parent === child.parent);
                const childIndex = siblings.indexOf(child);
                const totalSiblings = siblings.length;
                
                const angleOffset = (childIndex - (totalSiblings - 1) / 2) * (Math.PI / 6);
                const distance = 70;
                
                // Calculate angle from center to parent
                const parentAngle = Math.atan2(parent.y - centerY, parent.x - centerX);
                const childAngle = parentAngle + angleOffset;
                
                child.x = parent.x + Math.cos(childAngle) * distance;
                child.y = parent.y + Math.sin(childAngle) * distance;
            }
        });

        drawStaticNodes(g);
    }

    function drawTreeLayout(g, width, height) {
        // Simple tree layout
        const levels = [
            mindMapNodes.filter(n => n.level === 0),
            mindMapNodes.filter(n => n.level === 1),
            mindMapNodes.filter(n => n.level === 2)
        ];

        const levelHeight = height / (levels.length + 1);

        levels.forEach((levelNodes, levelIndex) => {
            const y = levelHeight * (levelIndex + 1);
            const spacing = width / (levelNodes.length + 1);
            
            levelNodes.forEach((node, nodeIndex) => {
                node.x = spacing * (nodeIndex + 1);
                node.y = y;
            });
        });

        drawStaticNodes(g);
    }

    function drawForceLayout(g, width, height) {
        // Force-directed layout
        const simulation = d3.forceSimulation(mindMapNodes)
            .force('link', d3.forceLink(mindMapLinks).id(d => d.id).distance(80))
            .force('charge', d3.forceManyBody().strength(-200))
            .force('center', d3.forceCenter(width / 2, height / 2))
            .force('collision', d3.forceCollide().radius(d => d.size + 5));

        drawDynamicNodes(g, simulation);
    }

    function drawStaticNodes(g) {
        // Draw links
        const links = g.selectAll('.mind-link')
            .data(mindMapLinks)
            .enter()
            .append('line')
            .attr('class', 'mind-link')
            .attr('x1', d => {
                const source = mindMapNodes.find(n => n.id === d.source);
                return source ? source.x : 0;
            })
            .attr('y1', d => {
                const source = mindMapNodes.find(n => n.id === d.source);
                return source ? source.y : 0;
            })
            .attr('x2', d => {
                const target = mindMapNodes.find(n => n.id === d.target);
                return target ? target.x : 0;
            })
            .attr('y2', d => {
                const target = mindMapNodes.find(n => n.id === d.target);
                return target ? target.y : 0;
            })
            .attr('stroke', d => d.type === 'main' ? '#667eea' : '#dee2e6')
            .attr('stroke-width', d => d.type === 'main' ? 3 : 2)
            .attr('opacity', 0.7);

        // Draw nodes
        const nodeGroups = g.selectAll('.mind-node')
            .data(mindMapNodes)
            .enter()
            .append('g')
            .attr('class', 'mind-node')
            .attr('transform', d => `translate(${d.x}, ${d.y})`)
            .style('cursor', 'pointer')
            .on('click', (event, d) => showNodeDetails(d))
            .on('mouseover', function(event, d) {
                d3.select(this).select('circle')
                    .transition().duration(200)
                    .attr('r', d.size * 1.3)
                    .attr('stroke-width', 4);
            })
            .on('mouseout', function(event, d) {
                d3.select(this).select('circle')
                    .transition().duration(200)
                    .attr('r', d.size)
                    .attr('stroke-width', 2);
            });

        // Node circles with gradient
        const defs = g.append('defs');
        mindMapNodes.forEach(node => {
            const gradient = defs.append('radialGradient')
                .attr('id', `gradient-${node.id}`)
                .attr('cx', '30%')
                .attr('cy', '30%');
            
            gradient.append('stop')
                .attr('offset', '0%')
                .attr('stop-color', d3.color(node.color).brighter(0.5));
            
            gradient.append('stop')
                .attr('offset', '100%')
                .attr('stop-color', node.color);
        });

        nodeGroups.append('circle')
            .attr('r', d => d.size)
            .attr('fill', d => `url(#gradient-${d.id})`)
            .attr('stroke', '#fff')
            .attr('stroke-width', 2)
            .style('filter', 'drop-shadow(0 3px 6px rgba(0,0,0,0.2))');

        // Node labels with better positioning
        nodeGroups.append('text')
            .attr('text-anchor', 'middle')
            .attr('dy', d => d.size + 18)
            .attr('font-size', d => d.type === 'central' ? '13px' : d.type === 'branch' ? '11px' : '9px')
            .attr('font-weight', d => d.type === 'central' ? 'bold' : 'normal')
            .attr('fill', '#333')
            .style('text-shadow', '1px 1px 2px rgba(255,255,255,0.8)')
            .text(d => {
                const maxLength = d.type === 'central' ? 25 : d.type === 'branch' ? 20 : 15;
                return d.name.length > maxLength ? d.name.substring(0, maxLength) + '...' : d.name;
            });
    }

    function drawDynamicNodes(g, simulation) {
        // Similar to drawStaticNodes but with simulation updates
        const links = g.selectAll('.mind-link')
            .data(mindMapLinks)
            .enter()
            .append('line')
            .attr('class', 'mind-link')
            .attr('stroke', d => d.type === 'main' ? '#667eea' : '#dee2e6')
            .attr('stroke-width', d => d.type === 'main' ? 3 : 2)
            .attr('opacity', 0.7);

        const nodeGroups = g.selectAll('.mind-node')
            .data(mindMapNodes)
            .enter()
            .append('g')
            .attr('class', 'mind-node')
            .style('cursor', 'pointer')
            .on('click', (event, d) => showNodeDetails(d))
            .call(d3.drag()
                .on('start', (event, d) => {
                    if (!event.active) simulation.alphaTarget(0.3).restart();
                    d.fx = d.x;
                    d.fy = d.y;
                })
                .on('drag', (event, d) => {
                    d.fx = event.x;
                    d.fy = event.y;
                })
                .on('end', (event, d) => {
                    if (!event.active) simulation.alphaTarget(0);
                    d.fx = null;
                    d.fy = null;
                }));

        nodeGroups.append('circle')
            .attr('r', d => d.size)
            .attr('fill', d => d.color)
            .attr('stroke', '#fff')
            .attr('stroke-width', 2);

        nodeGroups.append('text')
            .attr('text-anchor', 'middle')
            .attr('dy', d => d.size + 15)
            .attr('font-size', '10px')
            .attr('fill', '#333')
            .text(d => d.name.length > 15 ? d.name.substring(0, 15) + '...' : d.name);

        simulation.on('tick', () => {
            links
                .attr('x1', d => d.source.x)
                .attr('y1', d => d.source.y)
                .attr('x2', d => d.target.x)
                .attr('y2', d => d.target.y);

            nodeGroups
                .attr('transform', d => `translate(${d.x}, ${d.y})`);
        });
    }

    function showNodeDetails(d) {
        const panel = document.getElementById('nodeDetailsPanel');
        const title = document.getElementById('nodeTitle');
        const content = document.getElementById('nodeContent');

        title.innerHTML = `<i class="fas fa-info-circle me-2"></i>${d.details.title}`;
        
        let detailsHtml = `
            <div class="row mb-3">
                <div class="col-md-6">
                    <div class="d-flex align-items-center mb-2">
                        <i class="fas fa-tag me-2 text-primary"></i>
                        <strong>Тип:</strong>
                        <span class="badge ms-2" style="background-color: ${d.color}; color: white;">
                            ${d.type === 'central' ? 'Центральная тема' : d.type === 'branch' ? 'Основная ветка' : 'Подтема'}
                        </span>
                    </div>
                    <div class="mb-2">
                        <i class="fas fa-align-left me-2 text-info"></i>
                        <strong>Описание:</strong>
                        <p class="mt-1 text-muted">${d.details.description}</p>
                    </div>
                </div>
                <div class="col-md-6">
        `;

        if (d.details.children !== undefined) {
            detailsHtml += `
                <div class="mb-2">
                    <i class="fas fa-sitemap me-2 text-success"></i>
                    <strong>Подтем:</strong> 
                    <span class="badge bg-success ms-1">${d.details.children}</span>
                </div>`;
        }
        if (d.details.parent) {
            detailsHtml += `
                <div class="mb-2">
                    <i class="fas fa-level-up-alt me-2 text-warning"></i>
                    <strong>Родитель:</strong> 
                    <span class="text-primary">${d.details.parent}</span>
                </div>`;
        }

        // Add connection info
        const connections = mindMapLinks.filter(link => 
            link.source === d.id || link.target === d.id
        ).length;
        
        detailsHtml += `
                <div class="mb-2">
                    <i class="fas fa-link me-2 text-secondary"></i>
                    <strong>Связей:</strong> 
                    <span class="badge bg-secondary ms-1">${connections}</span>
                </div>
            </div>
        </div>
        
        <!-- Quick Actions -->
        <div class="border-top pt-3">
            <h6 class="mb-2"><i class="fas fa-bolt me-2"></i>Быстрые действия</h6>
            <div class="d-flex gap-2 flex-wrap">
                <button class="btn btn-sm btn-outline-primary" onclick="focusOnNode('${d.id}')">
                    <i class="fas fa-crosshairs me-1"></i>Фокус
                </button>
                <button class="btn btn-sm btn-outline-success" onclick="highlightConnections('${d.id}')">
                    <i class="fas fa-project-diagram me-1"></i>Связи
                </button>
                <button class="btn btn-sm btn-outline-info" onclick="createFlashcardFromNode('${d.id}')">
                    <i class="fas fa-layer-group me-1"></i>Флеш-карта
                </button>
                <button class="btn btn-sm btn-outline-warning" onclick="addToStudyPlan('${d.id}')">
                    <i class="fas fa-calendar-plus me-1"></i>В план
                </button>
            </div>
        </div>
        `;

        content.innerHTML = detailsHtml;
        panel.style.display = 'block';
        panel.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        
        // Store current selected node
        window.selectedNode = d;
    }

    function hideNodeDetails() {
        document.getElementById('nodeDetailsPanel').style.display = 'none';
    }

    function setMindMapLayout(layout) {
        currentLayout = layout;
        
        // Update active button
        document.querySelectorAll('.mind-map-controls .btn').forEach(btn => {
            btn.classList.remove('active');
        });
        event.target.classList.add('active');
        
        drawModernMindMap();
    }

    function resetMindMapView() {
        const svg = d3.select('#mindMapSvg');
        svg.transition().duration(750).call(
            d3.zoom().transform,
            d3.zoomIdentity
        );
    }

    function downloadMindMap() {
        const svgElement = document.getElementById('mindMapSvg');
        const svgData = new XMLSerializer().serializeToString(svgElement);
        
        // Create canvas for export
        const canvas = document.createElement('canvas');
        const ctx = canvas.getContext('2d');
        canvas.width = svgElement.clientWidth;
        canvas.height = 500;
        
        // Create image from SVG
        const img = new Image();
        img.onload = function() {
            // White background
            ctx.fillStyle = 'white';
            ctx.fillRect(0, 0, canvas.width, canvas.height);
            ctx.drawImage(img, 0, 0);
            
            // Download
            const link = document.createElement('a');
            link.download = 'mind_map.png';
            link.href = canvas.toDataURL('image/png');
            link.click();
        };
        
        const blob = new Blob([svgData], {type: 'image/svg+xml;charset=utf-8'});
        img.src = URL.createObjectURL(blob);
    }

    // New Enhanced Mind Map Functions
    function searchMindMapNodes() {
        const searchTerm = document.getElementById('mindMapSearch').value.toLowerCase();
        if (!searchTerm) {
            // Reset all nodes
            d3.selectAll('.mind-node').style('opacity', 1);
            return;
        }
        
        d3.selectAll('.mind-node').style('opacity', function(d) {
            return d.name.toLowerCase().includes(searchTerm) ? 1 : 0.3;
        });
    }

    function filterNodes(type) {
        // Update active button
        document.querySelectorAll('[data-filter]').forEach(btn => {
            btn.classList.remove('active');
        });
        document.querySelector(`[data-filter="${type}"]`).classList.add('active');
        
        if (type === 'all') {
            d3.selectAll('.mind-node').style('opacity', 1);
            d3.selectAll('.mind-link').style('opacity', 0.6);
        } else {
            d3.selectAll('.mind-node').style('opacity', function(d) {
                return d.type === type ? 1 : 0.3;
            });
            d3.selectAll('.mind-link').style('opacity', function(d) {
                const sourceNode = mindMapNodes.find(n => n.id === d.source);
                const targetNode = mindMapNodes.find(n => n.id === d.target);
                return (sourceNode && sourceNode.type === type) || (targetNode && targetNode.type === type) ? 0.6 : 0.1;
            });
        }
    }

    function adjustMindMapSize(size) {
        // Update active button
        document.querySelectorAll('.mind-map-controls .btn-group:last-child .btn').forEach(btn => {
            btn.classList.remove('active');
        });
        event.target.classList.add('active');
        
        const svg = d3.select('#mindMapSvg');
        let scale;
        
        switch(size) {
            case 'small': scale = 0.7; break;
            case 'large': scale = 1.3; break;
            default: scale = 1; break;
        }
        
        svg.transition().duration(500).call(
            d3.zoom().transform,
            d3.zoomIdentity.scale(scale)
        );
    }

    function focusOnNode(nodeId) {
        const node = mindMapNodes.find(n => n.id === nodeId);
        if (!node) return;
        
        const svg = d3.select('#mindMapSvg');
        const width = document.getElementById('mindMapSvg').clientWidth;
        const height = 500;
        
        const scale = 1.5;
        const x = width / 2 - node.x * scale;
        const y = height / 2 - node.y * scale;
        
        svg.transition().duration(750).call(
            d3.zoom().transform,
            d3.zoomIdentity.translate(x, y).scale(scale)
        );
        
        // Highlight the node
        d3.selectAll('.mind-node').style('opacity', 0.3);
        d3.select(`[data-node-id="${nodeId}"]`).style('opacity', 1);
        
        setTimeout(() => {
            d3.selectAll('.mind-node').style('opacity', 1);
        }, 2000);
    }

    function highlightConnections(nodeId) {
        const connectedLinks = mindMapLinks.filter(link => 
            link.source === nodeId || link.target === nodeId
        );
        
        const connectedNodeIds = new Set();
        connectedLinks.forEach(link => {
            connectedNodeIds.add(link.source);
            connectedNodeIds.add(link.target);
        });
        
        // Highlight connected nodes and links
        d3.selectAll('.mind-node').style('opacity', function(d) {
            return connectedNodeIds.has(d.id) ? 1 : 0.3;
        });
        
        d3.selectAll('.mind-link').style('opacity', function(d) {
            return connectedLinks.includes(d) ? 1 : 0.1;
        }).style('stroke-width', function(d) {
            return connectedLinks.includes(d) ? 3 : 1;
        });
        
        // Reset after 3 seconds
        setTimeout(() => {
            d3.selectAll('.mind-node').style('opacity', 1);
            d3.selectAll('.mind-link').style('opacity', 0.6).style('stroke-width', 1);
        }, 3000);
    }

    function createFlashcardFromNode(nodeId) {
        const node = window.selectedNode || mindMapNodes.find(n => n.id === nodeId);
        if (!node) return;
        
        // Create a simple flashcard modal or redirect to flashcards tab
        const flashcardData = {
            question: `Что такое "${node.name}"?`,
            answer: node.details.description,
            difficulty: node.type === 'central' ? 3 : node.type === 'branch' ? 2 : 1
        };
        
        // Show success message
        const toast = document.createElement('div');
        toast.className = 'alert alert-success position-fixed';
        toast.style.cssText = 'top: 20px; right: 20px; z-index: 9999; min-width: 300px;';
        toast.innerHTML = `
            <i class="fas fa-check-circle me-2"></i>
            Флеш-карта создана для "${node.name}"
            <button type="button" class="btn-close ms-2" onclick="this.parentElement.remove()"></button>
        `;
        document.body.appendChild(toast);
        
        setTimeout(() => toast.remove(), 3000);
    }

    function addToStudyPlan(nodeId) {
        const node = window.selectedNode || mindMapNodes.find(n => n.id === nodeId);
        if (!node) return;
        
        // Show success message
        const toast = document.createElement('div');
        toast.className = 'alert alert-info position-fixed';
        toast.style.cssText = 'top: 20px; right: 20px; z-index: 9999; min-width: 300px;';
        toast.innerHTML = `
            <i class="fas fa-calendar-plus me-2"></i>
            "${node.name}" добавлено в план обучения
            <button type="button" class="btn-close ms-2" onclick="this.parentElement.remove()"></button>
        `;
        document.body.appendChild(toast);
        
        setTimeout(() => toast.remove(), 3000);
    }

    function fitToScreen() {
        const svg = d3.select('#mindMapSvg');
        svg.transition().duration(750).call(
            d3.zoom().transform,
            d3.zoomIdentity.scale(0.8)
        );
    }

    function centerView() {
        const svg = d3.select('#mindMapSvg');
        svg.transition().duration(750).call(
            d3.zoom().transform,
            d3.zoomIdentity
        );
    }

    function updateMindMapStats() {
        document.getElementById('nodeCount').textContent = mindMapNodes.length;
        document.getElementById('linkCount').textContent = mindMapLinks.length;
    }

    // Start study session
    function startStudySession() {
        // TODO: Implement interactive study mode
        alert('Интерактивный режим изучения будет добавлен в следующей версии');
    }

    // Start specific session
    function startSession(day) {
        // TODO: Implement session start
        alert(`Начать сессию дня ${day}`);
    }

    // Seek to video time
    function seekToTime(seconds) {
        // TODO: Implement video player integration
        alert(`Перейти к ${Math.floor(seconds / 60)}:${Math.floor(seconds % 60).toString().padStart(2, '0')}`);
    }

    // Load progress function
    function loadProgress() {
        fetch(`/api/study_progress/{{ result_id }}`)
            .then(response => response.json())
            .then(data => {
                const progressHtml = `
                    <div class="row text-center">
                        <div class="col-md-4">
                            <h3 class="text-primary">${data.total_cards}</h3>
                            <p class="text-muted mb-0">Всего карточек</p>
                        </div>
                        <div class="col-md-4">
                            <h3 class="text-info">${data.reviewed_cards}</h3>
                            <p class="text-muted mb-0">Изучено</p>
                        </div>
                        <div class="col-md-4">
                            <h3 class="text-success">${data.mastered_cards}</h3>
                            <p class="text-muted mb-0">Освоено</p>
                        </div>
                    </div>
                    <div class="progress mt-3" style="height: 25px;">
                        <div class="progress-bar bg-success" style="width: ${data.progress_percentage}%">
                            ${data.progress_percentage}%
                        </div>
                    </div>
                `;
                document.getElementById('progressContainer').innerHTML = progressHtml;
            });
    }

    // Initialize on tab change
    document.getElementById('mindmap-tab').addEventListener('shown.bs.tab', function() {
        initMindMap();
    });

    // Expand/collapse all flashcards
    function expandAll() {
        document.querySelectorAll('.accordion-collapse').forEach(el => {
            new bootstrap.Collapse(el, { show: true });
        });
    }

    function collapseAll() {
        document.querySelectorAll('.accordion-collapse').forEach(el => {
            new bootstrap.Collapse(el, { hide: true });
        });
    }

    // Enhanced Summary Functionality
    let isCompactView = false;
    let summaryText = `{{ summary|replace('\n', '\\n')|replace('"', '\\"')|safe }}`;

    function initSummary() {
        processSummaryContent();
        calculateSummaryStats();
        initReadingProgress();
    }

    function processSummaryContent() {
        const summaryContainer = document.getElementById('summaryContent');
        if (!summaryContainer || !summaryText) return;

        // Process the summary text to create structured HTML
        let processedContent = summaryText;

        // Convert emoji headers to structured sections
        processedContent = processedContent.replace(/## 🎯 ([^:]+):/g, '<div class="emoji-section"><h2><span class="me-2">🎯</span>$1</h2>');
        processedContent = processedContent.replace(/## 📊 ([^:]+):/g, '</div><div class="emoji-section"><h2><span class="me-2">📊</span>$1</h2>');
        processedContent = processedContent.replace(/## 🔗 ([^:]+):/g, '</div><div class="emoji-section"><h2><span class="me-2">🔗</span>$1</h2>');
        processedContent = processedContent.replace(/## 💡 ([^:]+):/g, '</div><div class="emoji-section"><h2><span class="me-2">💡</span>$1</h2>');
        processedContent = processedContent.replace(/## ⚡ ([^:]+):/g, '</div><div class="emoji-section"><h2><span class="me-2">⚡</span>$1</h2>');

        // Convert bullet points to enhanced list items
        processedContent = processedContent.replace(/• \*\*([^*]+)\*\*: ([^\n]+)/g, '<div class="key-point"><strong>$1:</strong> $2</div>');
        processedContent = processedContent.replace(/• ([^\n]+)/g, '<li>$1</li>');

        // Convert bold text
        processedContent = processedContent.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');

        // Convert line breaks to paragraphs
        processedContent = processedContent.replace(/\n\n/g, '</p><p>');
        processedContent = processedContent.replace(/\n/g, '<br>');

        // Wrap in paragraphs and close sections
        processedContent = '<p>' + processedContent + '</p></div>';

        // Clean up empty paragraphs
        processedContent = processedContent.replace(/<p><\/p>/g, '');
        processedContent = processedContent.replace(/<p><br><\/p>/g, '');

        summaryContainer.innerHTML = processedContent;
    }

    function calculateSummaryStats() {
        const wordCount = summaryText.split(/\s+/).length;
        const readingTime = Math.ceil(wordCount / 200); // Average reading speed
        const sectionCount = (summaryText.match(/##/g) || []).length;
        const keyPoints = (summaryText.match(/•/g) || []).length;

        document.getElementById('wordCount').textContent = wordCount;
        document.getElementById('readingTime').textContent = readingTime;
        document.getElementById('sectionCount').textContent = sectionCount;
        document.getElementById('keyPoints').textContent = keyPoints;
    }

    function initReadingProgress() {
        const summaryContainer = document.getElementById('summaryContent');
        if (!summaryContainer) return;

        // Simulate reading progress based on scroll
        summaryContainer.addEventListener('scroll', function() {
            const scrollTop = this.scrollTop;
            const scrollHeight = this.scrollHeight - this.clientHeight;
            const progress = scrollHeight > 0 ? (scrollTop / scrollHeight) * 100 : 0;
            
            document.getElementById('progressBar').style.width = progress + '%';
            document.getElementById('readingProgress').textContent = Math.round(progress) + '%';
        });

        // Auto-progress simulation for demonstration
        let autoProgress = 0;
        const progressInterval = setInterval(() => {
            if (autoProgress < 100) {
                autoProgress += 2;
                document.getElementById('progressBar').style.width = autoProgress + '%';
                document.getElementById('readingProgress').textContent = autoProgress + '%';
            } else {
                clearInterval(progressInterval);
            }
        }, 100);
    }

    function toggleSummaryView() {
        const summaryContainer = document.querySelector('.summary-modern');
        const toggleText = document.getElementById('viewToggleText');
        
        isCompactView = !isCompactView;
        
        if (isCompactView) {
            summaryContainer.classList.add('summary-compact');
            toggleText.textContent = 'Полный вид';
        } else {
            summaryContainer.classList.remove('summary-compact');
            toggleText.textContent = 'Компактный вид';
        }
    }

    function copySummary() {
        const textToCopy = summaryText.replace(/\*\*/g, '').replace(/##/g, '').replace(/•/g, '-');
        
        if (navigator.clipboard) {
            navigator.clipboard.writeText(textToCopy).then(() => {
                showNotification('Резюме скопировано в буфер обмена!', 'success');
            }).catch(() => {
                fallbackCopyText(textToCopy);
            });
        } else {
            fallbackCopyText(textToCopy);
        }
    }

    function fallbackCopyText(text) {
        const textArea = document.createElement('textarea');
        textArea.value = text;
        textArea.style.position = 'fixed';
        textArea.style.left = '-999999px';
        textArea.style.top = '-999999px';
        document.body.appendChild(textArea);
        textArea.focus();
        textArea.select();
        
        try {
            document.execCommand('copy');
            showNotification('Резюме скопировано в буфер обмена!', 'success');
        } catch (err) {
            showNotification('Не удалось скопировать текст', 'error');
        }
        
        document.body.removeChild(textArea);
    }

    function printSummary() {
        const printContent = document.getElementById('summaryContent').innerHTML;
        const printWindow = window.open('', '_blank');
        
        printWindow.document.write(`
            <html>
                <head>
                    <title>Резюме - AI-конспект</title>
                    <style>
                        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; margin: 40px; }
                        h2 { color: #667eea; border-bottom: 2px solid #667eea; padding-bottom: 10px; }
                        .emoji-section { margin: 20px 0; padding: 15px; background: #f8f9fa; border-radius: 8px; }
                        .key-point { background: #fff5f5; border: 1px solid #fed7d7; border-radius: 5px; padding: 10px; margin: 8px 0; }
                        strong { color: #2d3748; }
                        @media print { body { margin: 20px; } }
                    </style>
                </head>
                <body>
                    <h1>📄 Структурированное резюме</h1>
                    <div>${printContent}</div>
                    <div style="margin-top: 40px; text-align: center; color: #666; font-size: 12px;">
                        Создано с помощью AI-конспект Pro
                    </div>
                </body>
            </html>
        `);
        
        printWindow.document.close();
        printWindow.focus();
        
        setTimeout(() => {
            printWindow.print();
            printWindow.close();
        }, 250);
    }

    function showNotification(message, type = 'info') {
        // Create notification element
        const notification = document.createElement('div');
        notification.className = `alert alert-${type === 'success' ? 'success' : 'danger'} alert-dismissible fade show position-fixed`;
        notification.style.cssText = 'top: 20px; right: 20px; z-index: 9999; min-width: 300px;';
        notification.innerHTML = `
            <i class="fas fa-${type === 'success' ? 'check-circle' : 'exclamation-triangle'} me-2"></i>
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;
        
        document.body.appendChild(notification);
        
        // Auto remove after 3 seconds
        setTimeout(() => {
            if (notification.parentNode) {
                notification.remove();
            }
        }, 3000);
    }

    // Initialize summary when tab is shown
    document.getElementById('summary-tab').addEventListener('shown.bs.tab', function() {
        setTimeout(initSummary, 100); // Small delay to ensure content is rendered
    });

    // Initialize if summary tab is already active
    if (document.getElementById('summary-tab').classList.contains('active')) {
        setTimeout(initSummary, 100);
    }

    // Enhanced Study Plan Functionality
    let isCompactSessionView = false;

    function initStudyPlan() {
        // Initialize progress circles for milestones
        initMilestoneProgress();
        
        // Set up session interactions
        setupSessionInteractions();
        
        // Initialize timeline interactions
        initTimelineInteractions();
    }

    function initMilestoneProgress() {
        const progressCircles = document.querySelectorAll('.progress-circle');
        progressCircles.forEach(circle => {
            const progressText = circle.textContent.trim();
            const progressValue = parseInt(progressText.replace('%', ''));
            circle.style.setProperty('--progress', progressValue);
        });
    }

    function setupSessionInteractions() {
        console.log('Session interactions will be handled by event delegation');
        // Event delegation is handled globally, no need for individual listeners
    }

    function initTimelineInteractions() {
        const timelineItems = document.querySelectorAll('.timeline-item');
        timelineItems.forEach(item => {
            item.addEventListener('click', function() {
                const sessionNumber = this.dataset.session;
                scrollToSession(sessionNumber);
                highlightSession(sessionNumber);
            });
        });
    }

    function toggleSessionDetails(sessionNumber) {
        console.log('Toggling session details for session:', sessionNumber);
        const detailsElement = document.getElementById(`sessionDetails${sessionNumber}`);
        const toggleButton = document.querySelector(`.session-toggle-btn[data-session="${sessionNumber}"]`);
        const sessionCard = detailsElement ? detailsElement.closest('.session-card') : null;
        
        if (!detailsElement || !toggleButton) {
            console.error('Elements not found:', { detailsElement, toggleButton });
            return;
        }
        
        console.log('Details element found:', detailsElement);
        console.log('Toggle button found:', toggleButton);
        console.log('Current display:', detailsElement.style.display);
        
        const isHidden = detailsElement.style.display === 'none' || 
                        getComputedStyle(detailsElement).display === 'none';
        
        if (isHidden) {
            console.log('Showing details...');
            // Show details
            detailsElement.style.display = 'block';
            detailsElement.style.maxHeight = '0';
            detailsElement.style.opacity = '0';
            detailsElement.style.overflow = 'hidden';
            detailsElement.style.transition = 'all 0.4s ease-out';
            
            // Force reflow
            detailsElement.offsetHeight;
            
            // Animate in
            detailsElement.style.maxHeight = '2000px';
            detailsElement.style.opacity = '1';
            
            // Update button
            toggleButton.innerHTML = '<i class="fas fa-chevron-up me-1"></i>Свернуть';
            toggleButton.setAttribute('title', 'Свернуть');
            
            // Add expanded class for styling
            if (sessionCard) {
                sessionCard.classList.add('expanded');
            }
            
            // Clean up after animation
            setTimeout(() => {
                detailsElement.style.maxHeight = '';
                detailsElement.style.overflow = 'visible';
                detailsElement.style.transition = '';
            }, 400);
            
        } else {
            console.log('Hiding details...');
            // Hide details
            detailsElement.style.maxHeight = detailsElement.scrollHeight + 'px';
            detailsElement.style.overflow = 'hidden';
            detailsElement.style.transition = 'all 0.4s ease-out';
            
            // Force reflow
            detailsElement.offsetHeight;
            
            // Animate out
            detailsElement.style.maxHeight = '0';
            detailsElement.style.opacity = '0';
            
            // Update button
            toggleButton.innerHTML = '<i class="fas fa-chevron-down me-1"></i>Развернуть';
            toggleButton.setAttribute('title', 'Развернуть');
            
            setTimeout(() => {
                detailsElement.style.display = 'none';
                detailsElement.style.maxHeight = '';
                detailsElement.style.opacity = '';
                detailsElement.style.transition = '';
                if (sessionCard) {
                    sessionCard.classList.remove('expanded');
                }
            }, 400);
        }
    }

    function toggleSessionView() {
        const sessionsContainer = document.querySelector('.sessions-container');
        const toggleButton = document.querySelector('[onclick="toggleSessionView()"]');
        
        isCompactSessionView = !isCompactSessionView;
        
        if (isCompactSessionView) {
            sessionsContainer.classList.add('compact-view');
            toggleButton.innerHTML = '<i class="fas fa-expand me-1"></i>Полный вид';
            
            // Hide all expanded details
            document.querySelectorAll('.session-details').forEach(details => {
                details.style.display = 'none';
            });
        } else {
            sessionsContainer.classList.remove('compact-view');
            toggleButton.innerHTML = '<i class="fas fa-list me-1"></i>Компактный вид';
        }
    }

    function startSession(sessionNumber) {
        // Create session modal or redirect to session page
        showSessionModal(sessionNumber);
    }

    function showSessionModal(sessionNumber) {
        // Find session data
        const sessionCard = document.querySelector(`[data-session="${sessionNumber}"]`);
        if (!sessionCard) return;
        
        const sessionTitle = sessionCard.querySelector('.session-title h6').textContent;
        const sessionPhase = sessionCard.querySelector('.session-phase').textContent;
        const sessionDuration = sessionCard.querySelector('.session-duration').textContent;
        
        // Create modal content
        const modalContent = `
            <div class="modal fade" id="sessionModal" tabindex="-1">
                <div class="modal-dialog modal-lg">
                    <div class="modal-content">
                        <div class="modal-header bg-primary text-white">
                            <h5 class="modal-title">
                                <i class="fas fa-play-circle me-2"></i>
                                Начать ${sessionTitle}
                            </h5>
                            <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
                        </div>
                        <div class="modal-body">
                            <div class="session-start-info">
                                <div class="row mb-4">
                                    <div class="col-md-4">
                                        <div class="info-card">
                                            <div class="info-icon">📚</div>
                                            <div class="info-label">Фаза</div>
                                            <div class="info-value">${sessionPhase}</div>
                                        </div>
                                    </div>
                                    <div class="col-md-4">
                                        <div class="info-card">
                                            <div class="info-icon">⏱️</div>
                                            <div class="info-label">Длительность</div>
                                            <div class="info-value">${sessionDuration}</div>
                                        </div>
                                    </div>
                                    <div class="col-md-4">
                                        <div class="info-card">
                                            <div class="info-icon">🎯</div>
                                            <div class="info-label">Сессия</div>
                                            <div class="info-value">#${sessionNumber}</div>
                                        </div>
                                    </div>
                                </div>
                                
                                <div class="session-checklist">
                                    <h6><i class="fas fa-clipboard-check me-2"></i>Подготовка к сессии</h6>
                                    <div class="checklist-items">
                                        <label class="checklist-item">
                                            <input type="checkbox" class="form-check-input me-2">
                                            Подготовить рабочее место и материалы
                                        </label>
                                        <label class="checklist-item">
                                            <input type="checkbox" class="form-check-input me-2">
                                            Убрать отвлекающие факторы (телефон, уведомления)
                                        </label>
                                        <label class="checklist-item">
                                            <input type="checkbox" class="form-check-input me-2">
                                            Настроить таймер на ${sessionDuration}
                                        </label>
                                        <label class="checklist-item">
                                            <input type="checkbox" class="form-check-input me-2">
                                            Подготовить воду и перекус
                                        </label>
                                    </div>
                                </div>
                            </div>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">
                                <i class="fas fa-times me-1"></i>Отмена
                            </button>
                            <button type="button" class="btn btn-success" onclick="beginSession(${sessionNumber})">
                                <i class="fas fa-rocket me-1"></i>Начать изучение!
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        // Remove existing modal
        const existingModal = document.getElementById('sessionModal');
        if (existingModal) {
            existingModal.remove();
        }
        
        // Add modal to page
        document.body.insertAdjacentHTML('beforeend', modalContent);
        
        // Show modal
        const modal = new bootstrap.Modal(document.getElementById('sessionModal'));
        modal.show();
        
        // Add styles for modal content
        const modalStyles = `
            <style>
                .session-start-info .info-card {
                    text-align: center;
                    padding: 15px;
                    background: #f8f9fa;
                    border-radius: 10px;
                    margin-bottom: 15px;
                }
                .session-start-info .info-icon {
                    font-size: 2rem;
                    margin-bottom: 8px;
                }
                .session-start-info .info-label {
                    font-size: 0.9rem;
                    color: #6c757d;
                    margin-bottom: 4px;
                }
                .session-start-info .info-value {
                    font-weight: 600;
                    color: #495057;
                }
                .session-checklist {
                    background: #f8f9fa;
                    padding: 20px;
                    border-radius: 10px;
                    margin-top: 20px;
                }
                .checklist-items {
                    display: flex;
                    flex-direction: column;
                    gap: 12px;
                    margin-top: 15px;
                }
                .checklist-item {
                    display: flex;
                    align-items: center;
                    padding: 8px 12px;
                    background: white;
                    border-radius: 6px;
                    cursor: pointer;
                    transition: background-color 0.2s;
                }
                .checklist-item:hover {
                    background: #e9ecef;
                }
            </style>
        `;
        
        if (!document.getElementById('sessionModalStyles')) {
            document.head.insertAdjacentHTML('beforeend', modalStyles.replace('<style>', '<style id="sessionModalStyles">'));
        }
    }

    function beginSession(sessionNumber) {
        // Close modal
        const modal = bootstrap.Modal.getInstance(document.getElementById('sessionModal'));
        modal.hide();
        
        // Mark session as started
        const sessionCard = document.querySelector(`[data-session="${sessionNumber}"]`);
        if (sessionCard) {
            sessionCard.classList.add('session-started');
            
            // Update button
            const startButton = sessionCard.querySelector('[onclick*="startSession"]');
            if (startButton) {
                startButton.innerHTML = '<i class="fas fa-check me-1"></i>В процессе';
                startButton.classList.remove('btn-primary');
                startButton.classList.add('btn-success');
            }
        }
        
        // Show success notification
        showNotification('Сессия начата! Удачного изучения! 🚀', 'success');
        
        // Optional: Start timer or redirect to study interface
        startSessionTimer(sessionNumber);
    }

    function startSessionTimer(sessionNumber) {
        // This could integrate with a Pomodoro timer or study tracker
        console.log(`Starting timer for session ${sessionNumber}`);
        
        // Example: Show a floating timer
        const timerHtml = `
            <div id="studyTimer" class="study-timer">
                <div class="timer-content">
                    <div class="timer-icon">⏱️</div>
                    <div class="timer-text">
                        <div class="timer-session">Сессия ${sessionNumber}</div>
                        <div class="timer-time" id="timerDisplay">45:00</div>
                    </div>
                    <button class="timer-close" onclick="closeTimer()">×</button>
                </div>
            </div>
        `;
        
        document.body.insertAdjacentHTML('beforeend', timerHtml);
        
        // Add timer styles
        const timerStyles = `
            <style id="timerStyles">
                .study-timer {
                    position: fixed;
                    top: 20px;
                    right: 20px;
                    z-index: 1050;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                    padding: 15px 20px;
                    border-radius: 15px;
                    box-shadow: 0 8px 25px rgba(0,0,0,0.2);
                    animation: slideInRight 0.3s ease-out;
                }
                .timer-content {
                    display: flex;
                    align-items: center;
                    gap: 12px;
                }
                .timer-icon {
                    font-size: 1.5rem;
                }
                .timer-session {
                    font-size: 0.8rem;
                    opacity: 0.9;
                }
                .timer-time {
                    font-size: 1.2rem;
                    font-weight: bold;
                }
                .timer-close {
                    background: none;
                    border: none;
                    color: white;
                    font-size: 1.2rem;
                    cursor: pointer;
                    opacity: 0.7;
                    margin-left: 10px;
                }
                .timer-close:hover {
                    opacity: 1;
                }
                @keyframes slideInRight {
                    from { transform: translateX(100%); opacity: 0; }
                    to { transform: translateX(0); opacity: 1; }
                }
            </style>
        `;
        
        if (!document.getElementById('timerStyles')) {
            document.head.insertAdjacentHTML('beforeend', timerStyles);
        }
    }

    function closeTimer() {
        const timer = document.getElementById('studyTimer');
        if (timer) {
            timer.style.animation = 'slideOutRight 0.3s ease-out';
            setTimeout(() => timer.remove(), 300);
        }
    }

    function scrollToSession(sessionNumber) {
        const sessionCard = document.querySelector(`[data-session="${sessionNumber}"]`);
        if (sessionCard) {
            sessionCard.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
    }

    function highlightSession(sessionNumber) {
        // Remove previous highlights
        document.querySelectorAll('.session-card.highlighted').forEach(card => {
            card.classList.remove('highlighted');
        });
        
        // Add highlight to selected session
        const sessionCard = document.querySelector(`[data-session="${sessionNumber}"]`);
        if (sessionCard) {
            sessionCard.classList.add('highlighted');
            setTimeout(() => {
                sessionCard.classList.remove('highlighted');
            }, 2000);
        }
    }

    // Initialize study plan when tab is shown
    document.getElementById('studyplan-tab').addEventListener('shown.bs.tab', function() {
        setTimeout(initStudyPlan, 100);
    });

    // Add CSS animations for session interactions
    const studyPlanStyles = `
        <style id="studyPlanInteractionStyles">
            @keyframes slideDown {
                from { opacity: 0; max-height: 0; }
                to { opacity: 1; max-height: 1000px; }
            }
            @keyframes slideUp {
                from { opacity: 1; max-height: 1000px; }
                to { opacity: 0; max-height: 0; }
            }
            @keyframes slideOutRight {
                from { transform: translateX(0); opacity: 1; }
                to { transform: translateX(100%); opacity: 0; }
            }
            .session-card.highlighted {
                transform: scale(1.02);
                box-shadow: 0 12px 40px rgba(102, 126, 234, 0.3) !important;
                border: 2px solid #667eea;
                transition: all 0.3s ease;
            }
            .session-card.session-started {
                border-left: 5px solid #28a745;
            }
            .sessions-container.compact-view .session-details {
                display: none !important;
            }
            .sessions-container.compact-view .session-card {
                margin-bottom: 10px;
            }
            .sessions-container.compact-view .session-header {
                padding: 15px;
            }
        </style>
    `;
    
    if (!document.getElementById('studyPlanInteractionStyles')) {
        document.head.insertAdjacentHTML('beforeend', studyPlanStyles);
    }
    
    // Simple direct event delegation for session toggle buttons
    let isToggling = false;
    
    document.addEventListener('click', function(e) {
        // Check if clicked element is a session toggle button
        if (e.target.closest('.session-toggle-btn')) {
            e.preventDefault();
            e.stopPropagation();
            
            // Prevent double clicks
            if (isToggling) {
                console.log('Toggle already in progress, ignoring click');
                return;
            }
            
            const button = e.target.closest('.session-toggle-btn');
            const sessionNumber = button.getAttribute('data-session');
            
            console.log('Session toggle clicked for session:', sessionNumber);
            isToggling = true;
            
            toggleSessionDetails(sessionNumber);
            
            // Reset flag after animation
            setTimeout(() => {
                isToggling = false;
            }, 500);
        }
    });
    
    // Initialize study plan functionality when page loads
    document.addEventListener('DOMContentLoaded', function() {
        console.log('DOM loaded, initializing study plan...');
        initStudyPlan();
        initMathSupport();
    });
    
    // Beautiful Math Support - Enhanced Visual Display
    function initMathSupport() {
        console.log('Initializing beautiful math support...');
        
        // Process math immediately
        setTimeout(() => {
            processBeautifulMath();
        }, 500);
        
        // Also process when tabs are switched
        document.querySelectorAll('[data-bs-toggle="tab"]').forEach(tab => {
            tab.addEventListener('shown.bs.tab', function() {
                setTimeout(() => {
                    processBeautifulMath();
                }, 200);
            });
        });
    }
    
    function processBeautifulMath() {
        console.log('Processing math with beautiful formatting...');
        
        // Find all text content that might contain math formulas
        const contentElements = document.querySelectorAll(
            '.summary-content-enhanced, .flashcard-question, .answer-content, .accordion-body, .topic-card'
        );
        
        contentElements.forEach(element => {
            if (element.textContent && !element.classList.contains('math-processed')) {
                let content = element.innerHTML;
                
                // Process both LaTeX formulas AND auto-detect math expressions
                content = createBeautifulMathFormulas(content);
                content = autoDetectMathExpressions(content);
                
                element.innerHTML = content;
                element.classList.add('math-processed');
            }
        });
    }
    
    function autoDetectMathExpressions(content) {
        console.log('Auto-detecting math in content:', content.substring(0, 200));
        
        // ULTRA SIMPLE - just look for ANY text with Greek letters or math functions
        // This will catch your example: a(x) = sign(Σyiλi exp(-||xi - x||^2 / 2σ^2))
        
        // Replace ANY text containing Greek letters or math functions
        content = content.replace(/([^<>\n]*(?:[ΣσλπφμωαβγδθΦΠΩΛΔΓΒΑ]|sign|exp|cos|sin|log|sqrt)[^<>\n]*)/gi, (match) => {
            // Skip if already processed or contains HTML
            if (match.includes('<') || match.includes('class=') || match.trim().length < 5) {
                return match;
            }
            
            // Skip if it's just a single Greek letter
            if (match.trim().length < 8) {
                return match;
            }
            
            console.log('Found math expression:', match.trim());
            return `<div class="math-formula">${beautifyAutoDetectedFormula(match.trim())}</div>`;
        });
        
        return content;
    }
    
    function containsMathSymbols(text) {
        // Check if text contains mathematical symbols
        const mathIndicators = [
            /[Σσλπφμωαβγδθ]/,  // Greek letters
            /\^[0-9]/,           // Powers like ^2
            /[a-zA-Z]_[a-zA-Z0-9]/, // Subscripts like x_i
            /exp\(/,             // Functions like exp(
            /sin\(|cos\(|tan\(/, // Trig functions
            /\|\|/,              // Norms like ||x||
            /sqrt\(/,            // Square root
            /log\(|ln\(/,        // Logarithms
            /sign\(/             // Sign function
        ];
        
        return mathIndicators.some(pattern => pattern.test(text));
    }
    
    function beautifyAutoDetectedFormula(formula) {
        let processed = formula;
        
        // Replace Greek letters
        processed = processed.replace(/Σ/g, '<span class="math-symbol">Σ</span>');
        processed = processed.replace(/σ/g, '<span class="math-symbol">σ</span>');
        processed = processed.replace(/λ/g, '<span class="math-symbol">λ</span>');
        processed = processed.replace(/π/g, '<span class="math-symbol">π</span>');
        processed = processed.replace(/φ/g, '<span class="math-symbol">φ</span>');
        processed = processed.replace(/μ/g, '<span class="math-symbol">μ</span>');
        processed = processed.replace(/ω/g, '<span class="math-symbol">ω</span>');
        processed = processed.replace(/α/g, '<span class="math-symbol">α</span>');
        processed = processed.replace(/β/g, '<span class="math-symbol">β</span>');
        processed = processed.replace(/γ/g, '<span class="math-symbol">γ</span>');
        processed = processed.replace(/δ/g, '<span class="math-symbol">δ</span>');
        processed = processed.replace(/θ/g, '<span class="math-symbol">θ</span>');
        
        // Replace mathematical functions
        processed = processed.replace(/\b(sin|cos|tan|log|ln|exp|sign)\(/g, '<span class="math-func">$1</span>(');
        
        // Replace powers
        processed = processed.replace(/\^([0-9]+)/g, '<span class="math-sup">$1</span>');
        processed = processed.replace(/\^2/g, '<span class="math-sup">2</span>');
        processed = processed.replace(/\^3/g, '<span class="math-sup">3</span>');
        
        // Replace subscripts
        processed = processed.replace(/([a-zA-Z])_([a-zA-Z0-9]+)/g, '$1<span class="math-sub">$2</span>');
        processed = processed.replace(/([a-zA-Z])i/g, '$1<span class="math-sub">i</span>');
        
        // Replace norms and absolute values
        processed = processed.replace(/\|\|([^|]+)\|\|/g, '<span class="math-symbol">||</span>$1<span class="math-symbol">||</span>');
        
        // Replace fractions (simple pattern like a/b)
        processed = processed.replace(/([^/\s]+)\s*\/\s*([^/\s]+)/g, (match, num, den) => {
            // Only if it looks like a mathematical fraction
            if (/^[0-9a-zA-Z^_σλπφμωαβγδθΣ\s]+$/.test(num + den)) {
                return `<span class="math-frac"><span class="numerator">${num.trim()}</span><span class="denominator">${den.trim()}</span></span>`;
            }
            return match;
        });
        
        // Style parentheses
        processed = processed.replace(/\(/g, '<span class="math-paren">(</span>');
        processed = processed.replace(/\)/g, '<span class="math-paren">)</span>');
        
        return processed;
    }
    
    function createBeautifulMathFormulas(content) {
        // Handle display formulas ($$...$$) with beautiful formatting
        content = content.replace(/\$\$([^$]+)\$\$/g, (match, formula) => {
            console.log('Processing formula:', formula);
            return `<div class="math-formula">${beautifyFormula(formula)}</div>`;
        });
        
        // Handle inline formulas ($...$)
        content = content.replace(/\$([^$]+)\$/g, (match, formula) => {
            return `<span class="math-inline">${beautifyFormula(formula, true)}</span>`;
        });
        
        return content;
    }
    
    function beautifyFormula(formula, isInline = false) {
        let processed = formula;
        
        // Handle fractions with beautiful styling
        processed = processed.replace(/\\frac\{([^}]+)\}\{([^}]+)\}/g, (match, num, den) => {
            if (isInline) {
                return `<span class="math-fraction"><sup>${beautifyContent(num)}</sup>⁄<sub>${beautifyContent(den)}</sub></span>`;
            } else {
                return `<span class="math-frac"><span class="numerator">${beautifyContent(num)}</span><span class="denominator">${beautifyContent(den)}</span></span>`;
            }
        });
        
        // Handle parentheses with styling
        processed = processed.replace(/\\left\(/g, '<span class="math-paren">(</span>');
        processed = processed.replace(/\\right\)/g, '<span class="math-paren">)</span>');
        processed = processed.replace(/\\left\[/g, '<span class="math-paren">[</span>');
        processed = processed.replace(/\\right\]/g, '<span class="math-paren">]</span>');
        processed = processed.replace(/\\left\{/g, '<span class="math-paren">{</span>');
        processed = processed.replace(/\\right\}/g, '<span class="math-paren">}</span>');
        
        // Handle mathematical functions
        processed = processed.replace(/\\?(sin|cos|tan|log|ln|exp|sign)\b/g, '<span class="math-func">$1</span>');
        
        // Handle Greek letters with beautiful styling
        const greekReplacements = [
            ['\\\\sum', '<span class="math-symbol">Σ</span>'],
            ['\\\\Sigma', '<span class="math-symbol">Σ</span>'],
            ['\\\\lambda', '<span class="math-symbol">λ</span>'],
            ['\\\\sigma', '<span class="math-symbol">σ</span>'],
            ['\\\\pi', '<span class="math-symbol">π</span>'],
            ['\\\\alpha', '<span class="math-symbol">α</span>'],
            ['\\\\beta', '<span class="math-symbol">β</span>'],
            ['\\\\gamma', '<span class="math-symbol">γ</span>'],
            ['\\\\delta', '<span class="math-symbol">δ</span>'],
            ['\\\\phi', '<span class="math-symbol">φ</span>'],
            ['\\\\Phi', '<span class="math-symbol">Φ</span>'],
            ['\\\\mu', '<span class="math-symbol">μ</span>'],
            ['\\\\omega', '<span class="math-symbol">ω</span>'],
            ['\\\\theta', '<span class="math-symbol">θ</span>']
        ];
        
        greekReplacements.forEach(([pattern, replacement]) => {
            processed = processed.replace(new RegExp(pattern, 'g'), replacement);
        });
        
        // Handle superscripts and subscripts with beautiful styling
        processed = processed.replace(/([a-zA-Z0-9]+)\^([a-zA-Z0-9]+)/g, '$1<span class="math-sup">$2</span>');
        processed = processed.replace(/([a-zA-Z0-9]+)_([a-zA-Z0-9]+)/g, '$1<span class="math-sub">$2</span>');
        
        // Handle special cases
        processed = processed.replace(/\^2/g, '<span class="math-sup">2</span>');
        processed = processed.replace(/\^3/g, '<span class="math-sup">3</span>');
        processed = processed.replace(/_i/g, '<span class="math-sub">i</span>');
        processed = processed.replace(/_j/g, '<span class="math-sub">j</span>');
        
        // Handle mathematical operators
        processed = processed.replace(/\|\|/g, '<span class="math-symbol">||</span>');
        processed = processed.replace(/\*/g, '<span class="math-symbol">·</span>');
        
        return processed;
    }
    
    function beautifyContent(content) {
        // Process content inside fractions, superscripts, etc.
        let processed = content;
        
        // Greek letters (simple replacements)
        const simpleGreek = [
            ['\\sum', 'Σ'], ['\\lambda', 'λ'], ['\\sigma', 'σ'], ['\\pi', 'π'],
            ['\\alpha', 'α'], ['\\beta', 'β'], ['\\gamma', 'γ'], ['\\delta', 'δ'],
            ['\\phi', 'φ'], ['\\Phi', 'Φ'], ['\\mu', 'μ'], ['\\omega', 'ω']
        ];
        
        simpleGreek.forEach(([latex, symbol]) => {
            processed = processed.replace(new RegExp(latex, 'g'), symbol);
        });
        
        // Subscripts and superscripts
        processed = processed.replace(/([a-zA-Z0-9]+)_([a-zA-Z0-9]+)/g, '$1<sub>$2</sub>');
        processed = processed.replace(/([a-zA-Z0-9]+)\^([a-zA-Z0-9]+)/g, '$1<sup>$2</sup>');
        processed = processed.replace(/\^2/g, '²');
        processed = processed.replace(/\^3/g, '³');
        processed = processed.replace(/_i/g, 'ᵢ');
        processed = processed.replace(/_j/g, 'ⱼ');
        
        return processed;
        
        // Wait for KaTeX to be ready
        if (window.katex && window.renderMathInElement) {
            processMathFormulas();
        } else {
            // Wait for KaTeX to load
            setTimeout(() => {
                if (window.katex && window.renderMathInElement) {
                    processMathFormulas();
                } else {
                    console.log('KaTeX not available, trying again...');
                    setTimeout(initMathSupport, 1000);
                }
            }, 1000);
        }
    }
    
    function processMathFormulas() {
        console.log('Processing math formulas with advanced recognition...');
        
        // Find all text content that might contain math formulas
        const contentElements = document.querySelectorAll(
            '.summary-content-enhanced, .flashcard-question, .answer-content, .accordion-body, .topic-card'
        );
        
        contentElements.forEach(element => {
            if (element.textContent && !element.classList.contains('math-processed')) {
                element.classList.add('math-processing');
                
                let content = element.innerHTML;
                
                // Advanced Wolfram-style pattern matching
                content = enhanceMathContentAdvanced(content);
                
                element.innerHTML = content;
                element.classList.remove('math-processing');
                element.classList.add('math-processed');
            }
        });
        
        // Render math with KaTeX
        renderMathWithKaTeX();
    }
    
    function enhanceMathContentAdvanced(content) {
        // Protect existing math expressions
        const mathExpressions = [];
        content = content.replace(/\$\$([^$]+)\$\$/g, (match) => {
            mathExpressions.push(match);
            return `__MATH_DISPLAY_${mathExpressions.length - 1}__`;
        });
        content = content.replace(/\$([^$]+)\$/g, (match) => {
            mathExpressions.push(match);
            return `__MATH_INLINE_${mathExpressions.length - 1}__`;
        });
        
        // Advanced mathematical pattern recognition (Wolfram-style)
        const advancedPatterns = [
            // Complex functions like φ(x) = (1/√n)(cos(w1^{T} x), ..., cos(wn^{T} x), sin(w1^{T} x), ..., sin(wn^{T} x))
            {
                pattern: /([φϕΦ])\s*\(\s*([^)]+)\)\s*=\s*\(([^)]+)\)\s*\\\s*\(([^)]+)\)/g,
                replacement: '$$\\$1($2) = \\left(\\frac{1}{\\sqrt{n}}\\right)\\left(\\cos(w_1^T x), \\ldots, \\cos(w_n^T x), \\sin(w_1^T x), \\ldots, \\sin(w_n^T x)\\right)$$'
            },
            // Functions with equals like K(x, z) = ...
            {
                pattern: /([A-Za-zφϕΦ]+)\s*\(\s*([^)]+)\)\s*=\s*([^.]+\.[^.]*)/g,
                replacement: (match, func, args, expr) => {
                    // Clean up the expression
                    let cleanExpr = expr.replace(/\.$/, ''); // Remove trailing dot
                    cleanExpr = processComplexExpression(cleanExpr);
                    return `$$${func}(${args}) = ${cleanExpr}$$`;
                }
            },
            // Fractions with square root like 1/√n
            {
                pattern: /(\d+)\/√([a-zA-Z]+)/g,
                replacement: '\\frac{$1}{\\sqrt{$2}}'
            },
            // Regular fractions
            {
                pattern: /(\d+)\/([a-zA-Z]+)/g,
                replacement: '\\frac{$1}{$2}'
            },
            // Powers with braces like w1^{T}
            {
                pattern: /([a-zA-Z0-9]+)\^\{([^}]+)\}/g,
                replacement: '$1^{$2}'
            },
            // Simple powers like w1^T
            {
                pattern: /([a-zA-Z0-9]+)\^([A-Za-z])/g,
                replacement: '$1^{$2}'
            },
            // Subscripts like w_j
            {
                pattern: /([a-zA-Z]+)_([a-zA-Z0-9]+)/g,
                replacement: '$1_{$2}'
            },
            // Greek letters
            {
                pattern: /\bphi\b/g,
                replacement: '\\phi'
            },
            {
                pattern: /\bPhi\b/g,
                replacement: '\\Phi'
            },
            {
                pattern: /\bSigma\b/g,
                replacement: '\\Sigma'
            },
            {
                pattern: /\bsum\b/g,
                replacement: '\\sum'
            },
            // Trigonometric functions
            {
                pattern: /\\cos\(/g,
                replacement: '\\cos('
            },
            {
                pattern: /\\sin\(/g,
                replacement: '\\sin('
            },
            {
                pattern: /\bcos\(/g,
                replacement: '\\cos('
            },
            {
                pattern: /\bsin\(/g,
                replacement: '\\sin('
            },
            // Mathematical operators
            {
                pattern: /\*\s*/g,
                replacement: ' \\cdot '
            },
            {
                pattern: /\+\/-/g,
                replacement: '\\pm'
            },
            {
                pattern: /<=/g,
                replacement: '\\leq'
            },
            {
                pattern: />=/g,
                replacement: '\\geq'
            },
            {
                pattern: /!=/g,
                replacement: '\\neq'
            },
            // Ellipsis
            {
                pattern: /\.\.\./g,
                replacement: '\\ldots'
            },
            {
                pattern: /,\s*\.\.\.\s*,/g,
                replacement: ', \\ldots, '
            }
        ];
        
        // Apply advanced patterns
        advancedPatterns.forEach(({ pattern, replacement }) => {
            if (typeof replacement === 'function') {
                content = content.replace(pattern, replacement);
            } else {
                content = content.replace(pattern, replacement);
            }
        });
        
        // Restore protected math expressions
        mathExpressions.forEach((expr, index) => {
            content = content.replace(`__MATH_DISPLAY_${index}__`, expr);
            content = content.replace(`__MATH_INLINE_${index}__`, expr);
        });
        
        return content;
    }
    
    function processComplexExpression(expr) {
        // Process complex mathematical expressions
        let processed = expr;
        
        // Handle parentheses with fractions
        processed = processed.replace(/\(([^)]+)\/([^)]+)\)/g, '\\left(\\frac{$1}{$2}\\right)');
        
        // Handle Σ summation
        processed = processed.replace(/Σ/g, '\\sum');
        
        // Handle multiplication
        processed = processed.replace(/\s*\*\s*/g, ' \\cdot ');
        
        // Handle trigonometric functions
        processed = processed.replace(/cos\(/g, '\\cos(');
        processed = processed.replace(/sin\(/g, '\\sin(');
        
        // Handle subscripts and superscripts
        processed = processed.replace(/([a-zA-Z]+)_([a-zA-Z0-9]+)/g, '$1_{$2}');
        processed = processed.replace(/([a-zA-Z0-9]+)\^([A-Za-z])/g, '$1^{$2}');
        
        // Handle square root
        processed = processed.replace(/√([a-zA-Z]+)/g, '\\sqrt{$1}');
        
        return processed;
    }
    
    function renderMathWithKaTeX() {
        if (window.renderMathInElement) {
            try {
                // Render math in all processed elements
                document.querySelectorAll('.math-processed').forEach(element => {
                    window.renderMathInElement(element, {
                        delimiters: [
                            {left: '$$', right: '$$', display: true},
                            {left: '$', right: '$', display: false},
                            {left: '\\[', right: '\\]', display: true},
                            {left: '\\(', right: '\\)', display: false}
                        ],
                        throwOnError: false,
                        errorColor: '#cc0000',
                        strict: false
                    });
                });
                
                console.log('Math formulas rendered successfully with KaTeX');
                addMathInteractivity();
            } catch (error) {
                console.error('KaTeX rendering error:', error);
            }
        }
    }
    
    function addMathInteractivity() {
        // Add click handlers to math expressions for copying
        document.querySelectorAll('.katex').forEach(mathElement => {
            mathElement.style.cursor = 'pointer';
            mathElement.title = 'Нажмите, чтобы скопировать формулу';
            
            mathElement.addEventListener('click', function() {
                const mathText = this.textContent || this.innerText;
                if (navigator.clipboard) {
                    navigator.clipboard.writeText(mathText);
                    showToast('Формула скопирована в буфер обмена', 'success');
                }
            });
        });
        
        // Add special styling to inline math
        document.querySelectorAll('.katex:not(.katex-display)').forEach(inlineMath => {
            inlineMath.classList.add('katex-inline');
        });
    }

</script>
