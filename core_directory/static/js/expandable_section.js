document.addEventListener('DOMContentLoaded', function() {
    document.querySelectorAll('.section-header').forEach(function(header) {
        header.addEventListener('click', function() {
            var content = header.nextElementSibling;
            var btn = header.querySelector('.expand-toggle');
            // Toggle visibility
            if (content.style.display === 'none' || content.style.display === '') {
                content.style.display = 'block';
                // Optionally animate:
                content.style.maxHeight = content.scrollHeight + "px";
                btn.innerHTML = '<i class="bi bi-dash"></i>';
            } else {
                content.style.display = 'none';
                btn.innerHTML = '<i class="bi bi-plus"></i>';
            }
        });
    });
});
