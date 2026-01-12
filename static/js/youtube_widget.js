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
    const resultsView = document.getElementById('youtube-results');
    const playerView = document.getElementById('youtube-player-view');
    const backBtn = document.getElementById('youtube-back-btn');

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
                    showPlayer();
                } else {
                    showResults();
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
                showResults();
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
                widget.style.height = '400px'; 
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

    // View Switching
    function showResults() {
        if (resultsView) resultsView.style.display = 'block';
        if (playerView) playerView.style.display = 'none';
    }

    function showPlayer() {
        if (resultsView) resultsView.style.display = 'none';
        if (playerView) playerView.style.display = 'flex';
    }

    if (backBtn) {
        backBtn.addEventListener('click', () => {
            showResults();
            iframe.src = ''; // Stop video when going back
            saveState();
        });
    }

    // Search Logic
    function performSearch() {
        const query = searchInput.value.trim();
        if (!query) return;

        // Check if direct URL
        if (query.includes('youtube.com') || query.includes('youtu.be')) {
            playDirectUrl(query);
            return;
        }

        // Show loading state
        resultsView.innerHTML = '<div class="text-center p-3 text-muted"><i class="fas fa-spinner fa-spin fa-2x"></i><br>جاري البحث...</div>';
        showResults();

        // Call API
        fetch(`/api/youtube/search?q=${encodeURIComponent(query)}`)
            .then(response => response.json())
            .then(data => {
                if (data.error) {
                    resultsView.innerHTML = `<div class="text-center p-3 text-danger">${data.error}</div>`;
                    return;
                }

                if (!data.results || data.results.length === 0) {
                    resultsView.innerHTML = '<div class="text-center p-3 text-muted">لا توجد نتائج</div>';
                    return;
                }

                renderResults(data.results);
            })
            .catch(err => {
                console.error('Search error:', err);
                resultsView.innerHTML = '<div class="text-center p-3 text-danger">حدث خطأ في البحث</div>';
            });
    }

    function renderResults(videos) {
        resultsView.innerHTML = '';
        videos.forEach(video => {
            const el = document.createElement('div');
            el.className = 'youtube-result-item';
            el.innerHTML = `
                <img src="${video.thumbnail}" class="youtube-result-thumb" alt="${video.title}">
                <div class="youtube-result-info">
                    <div class="youtube-result-title" title="${video.title}">${video.title}</div>
                    <div class="youtube-result-channel">${video.channel} • ${video.duration || ''}</div>
                </div>
            `;
            el.addEventListener('click', () => playVideo(video.id));
            resultsView.appendChild(el);
        });
    }

    function playVideo(videoId) {
        const src = `https://www.youtube.com/embed/${videoId}?autoplay=1&origin=${window.location.origin}&enablejsapi=1&rel=0`;
        iframe.src = src;
        showPlayer();
        saveState();
    }

    function playDirectUrl(urlStr) {
        try {
            let videoId = '';
            const url = new URL(urlStr);
            if (url.hostname === 'youtu.be') {
                videoId = url.pathname.slice(1);
            } else {
                videoId = url.searchParams.get('v');
            }
            if (videoId) {
                playVideo(videoId);
            } else {
                // Fallback to search if ID extraction fails
                searchInput.value = urlStr; // Ensure query is set
                // performSearch(); // Avoid infinite loop potential, just show error
                resultsView.innerHTML = '<div class="text-center p-3 text-danger">رابط غير صالح</div>';
                showResults();
            }
        } catch (e) {
             resultsView.innerHTML = '<div class="text-center p-3 text-danger">رابط غير صالح</div>';
             showResults();
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
