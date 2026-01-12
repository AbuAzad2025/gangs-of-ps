document.addEventListener('DOMContentLoaded', function() {
    const widget = document.getElementById('youtube-widget');
    if (!widget) return;

    const header = document.getElementById('youtube-header');
    const toggleBtn = document.getElementById('youtube-toggle-btn');
    const closeBtn = document.getElementById('youtube-close-btn');
    const minimizeBtn = document.getElementById('youtube-minimize-btn');
    const searchInput = document.getElementById('youtube-search-input');
    const searchBtn = document.getElementById('youtube-search-btn');
    const iframe = document.getElementById('youtube-iframe');
    const body = document.getElementById('youtube-body');

    // Restore state
    try {
        const savedState = JSON.parse(localStorage.getItem('youtubeWidgetState'));
        if (savedState) {
            if (savedState.visible) {
                widget.style.display = 'flex';
                // Ensure it's on screen
                const x = Math.min(Math.max(0, savedState.x), window.innerWidth - 300);
                const y = Math.min(Math.max(0, savedState.y), window.innerHeight - 50);
                widget.style.left = x + 'px';
                widget.style.top = y + 'px';
                widget.style.right = 'auto'; // Ensure free movement (override RTL CSS)
                
                if (savedState.currentSrc && savedState.currentSrc !== 'about:blank') {
                    iframe.src = savedState.currentSrc;
                }
                
                if (savedState.minimized) {
                    body.style.display = 'none';
                    widget.classList.add('minimized');
                    widget.style.height = 'auto';
                    widget.style.resize = 'none';
                }
            }
        }
    } catch (e) {
        console.error('Error loading YouTube widget state:', e);
    }

    // Drag Logic
    let isDragging = false;
    let offsetX, offsetY;

    header.addEventListener('mousedown', (e) => {
        // Don't drag if clicking buttons
        if (e.target.closest('.youtube-controls')) return;
        
        isDragging = true;
        const rect = widget.getBoundingClientRect();
        offsetX = e.clientX - rect.left;
        offsetY = e.clientY - rect.top;
        widget.style.opacity = '0.9';
        widget.style.transition = 'none';
        widget.style.right = 'auto'; // Enable free movement in RTL
    });

    document.addEventListener('mousemove', (e) => {
        if (isDragging) {
            e.preventDefault();
            let x = e.clientX - offsetX;
            let y = e.clientY - offsetY;
            
            // Boundary checks
            x = Math.max(0, Math.min(x, window.innerWidth - widget.offsetWidth));
            y = Math.max(0, Math.min(y, window.innerHeight - widget.offsetHeight));
            
            widget.style.left = x + 'px';
            widget.style.top = y + 'px';
        }
    });

    document.addEventListener('mouseup', () => {
        if (isDragging) {
            isDragging = false;
            widget.style.opacity = '1';
            widget.style.transition = 'box-shadow 0.3s';
            saveState();
        }
    });

    // Toggle Visibility via Buttons (Class based)
    const toggleBtns = document.querySelectorAll('.js-youtube-toggle, #youtube-toggle-btn');
    
    toggleBtns.forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.preventDefault();
            if (widget.style.display === 'none' || !widget.style.display) {
                widget.style.display = 'flex';
                // Default position if never saved
                if (!widget.style.left) {
                    widget.style.top = '100px';
                    if (document.dir === 'rtl') {
                        widget.style.right = '20px';
                        widget.style.left = 'auto';
                    } else {
                        widget.style.left = '20px';
                    }
                }
                saveState();
            } else {
                widget.style.display = 'none';
                saveState();
            }
        });
    });

    // Close
    if (closeBtn) {
        closeBtn.addEventListener('click', () => {
            widget.style.display = 'none';
            iframe.src = ''; // Stop video
            saveState();
        });
    }

    // Minimize
    if (minimizeBtn) {
        minimizeBtn.addEventListener('click', () => {
            const isMinimized = body.style.display === 'none';
            
            if (isMinimized) {
                // Restore
                body.style.display = 'flex';
                widget.classList.remove('minimized');
                widget.style.height = '360px'; 
                widget.style.resize = 'both';
                minimizeBtn.innerHTML = '<i class="fas fa-minus"></i>';
            } else {
                // Minimize
                body.style.display = 'none';
                widget.classList.add('minimized');
                widget.style.height = 'auto';
                widget.style.resize = 'none';
                minimizeBtn.innerHTML = '<i class="far fa-window-maximize"></i>';
            }
            saveState();
        });
    }

    // Search
    function performSearch() {
        const query = searchInput.value.trim();
        if (query) {
            let src = '';
            // Check if it's a URL
            if (query.includes('youtube.com') || query.includes('youtu.be')) {
                try {
                    const url = new URL(query);
                    let videoId = '';
                    if (url.hostname === 'youtu.be') {
                        videoId = url.pathname.slice(1);
                    } else {
                        videoId = url.searchParams.get('v');
                    }
                    if (videoId) {
                        src = `https://www.youtube.com/embed/${videoId}?autoplay=1&origin=${window.location.origin}`;
                    }
                } catch (e) {
                    // Invalid URL, treat as search
                    src = `https://www.youtube.com/embed?listType=search&list=${encodeURIComponent(query)}&autoplay=1&origin=${window.location.origin}`;
                }
            } else {
                // Search query
                src = `https://www.youtube.com/embed?listType=search&list=${encodeURIComponent(query)}&autoplay=1&origin=${window.location.origin}`;
            }
            
            if (src) {
                iframe.src = src;
                saveState();
            }
        }
    }

    if (searchBtn) {
        searchBtn.addEventListener('click', performSearch);
    }
    
    if (searchInput) {
        searchInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') performSearch();
        });
    }

    function saveState() {
        const state = {
            x: widget.offsetLeft,
            y: widget.offsetTop,
            visible: widget.style.display !== 'none',
            minimized: body.style.display === 'none',
            currentSrc: iframe.src
        };
        localStorage.setItem('youtubeWidgetState', JSON.stringify(state));
    }
});
