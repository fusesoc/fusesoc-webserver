document.addEventListener('DOMContentLoaded', function() {
    document.querySelectorAll('.section-card.collapsible').forEach(function(card) {
        var header = card.querySelector('.section-header');
        var content = card.querySelector('.section-content');
        var toggle = header.querySelector('.expand-toggle');
        var collapsed = card.getAttribute('data-collapsed') === 'true';

        // Set initial state
        if (collapsed) {
            content.style.display = 'none';
            if (toggle) toggle.innerHTML = '<i class="bi bi-plus"></i>';
        } else {
            content.style.display = 'block';
            if (toggle) toggle.innerHTML = '<i class="bi bi-dash"></i>';
        }

        // Toggle function
        function doToggle() {
            var isOpen = content.style.display === 'block';
            content.style.display = isOpen ? 'none' : 'block';
            if (toggle) {
                toggle.innerHTML = isOpen
                    ? '<i class="bi bi-plus"></i>'
                    : '<i class="bi bi-dash"></i>';
            }
        }

        // Click handler on header (but ignore if button was clicked)
        header.addEventListener('click', function(e) {
            if (e.target.closest('.expand-toggle')) return; // Don't toggle twice if button clicked
            doToggle();
        });

        // Click handler on button (for keyboard accessibility)
        if (toggle) {
            toggle.addEventListener('click', function(e) {
                e.stopPropagation(); // Prevent header handler from firing
                doToggle();
            });
        }
    });
});