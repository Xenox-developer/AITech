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