
document.addEventListener('DOMContentLoaded', function() {
    const searchInput = document.querySelector('input[name="q"]');
    const suggestionsDiv = document.createElement('div');
    suggestionsDiv.className = 'suggestions';
    searchInput.parentNode.appendChild(suggestionsDiv);
    
    let currentRequest = null;
    
    searchInput.addEventListener('input', function() {
        const query = this.value.trim();
        
        // Cancelar request anterior si existe
        if (currentRequest) {
            currentRequest.abort();
        }
        
        if (query.length < 2) {
            suggestionsDiv.style.display = 'none';
            return;
        }
        
        // Mostrar loading
        suggestionsDiv.innerHTML = '<div class="suggestion-item">Buscando sugerencias...</div>';
        suggestionsDiv.style.display = 'block';
        
        // Hacer request
        currentRequest = new XMLHttpRequest();
        currentRequest.open('GET', '/suggest?q=' + encodeURIComponent(query));
        currentRequest.onload = function() {
            if (currentRequest.status === 200) {
                const suggestions = JSON.parse(currentRequest.responseText);
                displaySuggestions(suggestions);
            }
            currentRequest = null;
        };
        currentRequest.send();
    });
    
    function displaySuggestions(suggestions) {
        if (suggestions.length === 0) {
            suggestionsDiv.style.display = 'none';
            return;
        }
        
        suggestionsDiv.innerHTML = '';
        suggestions.forEach(function(suggestion) {
            const div = document.createElement('div');
            div.className = 'suggestion-item';
            div.textContent = suggestion;
            div.addEventListener('click', function() {
                searchInput.value = suggestion;
                suggestionsDiv.style.display = 'none';
                searchInput.focus();
            });
            suggestionsDiv.appendChild(div);
        });
        suggestionsDiv.style.display = 'block';
    }
    
    // Ocultar sugerencias al hacer click fuera
    document.addEventListener('click', function(e) {
        if (!searchInput.contains(e.target) && !suggestionsDiv.contains(e.target)) {
            suggestionsDiv.style.display = 'none';
        }
    });
});