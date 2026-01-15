// ============= ENHANCED MAIN.JS FOR MZANSI INSIGHTS =============

// Live news ticker with rotation
function updateLiveNewsTicker() {
    fetch('/api/live-news')
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success' && data.articles.length > 0) {
                const ticker = document.getElementById('liveNews');
                if (ticker) {
                    let currentIndex = 0;
                    
                    function rotateTicker() {
                        const article = data.articles[currentIndex];
                        ticker.innerHTML = `
                            <strong>BREAKING:</strong> ${article.title}
                            <span style="color: ${article.color}; margin-left: 10px; font-weight: 600;">
                                <i class="fas fa-tag"></i> ${article.category}
                            </span>
                        `;
                        currentIndex = (currentIndex + 1) % data.articles.length;
                    }
                    
                    rotateTicker();
                    setInterval(rotateTicker, 8000); // Rotate every 8 seconds
                }
            }
        })
        .catch(error => console.error('Error updating ticker:', error));
}

// Source status indicator with detailed info
function updateSourceStatus() {
    fetch('/api/sources/status')
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                const indicator = document.querySelector('.status-indicator.active');
                if (indicator) {
                    indicator.innerHTML = `
                        <i class="fas fa-circle" style="color: #10b981;"></i>
                        ${data.total_active}/${data.total_sources} sources active
                    `;
                }
                
                // Update individual source cards if on sources page
                data.sources.forEach(source => {
                    const sourceCard = document.querySelector(`[data-source="${source.name}"]`);
                    if (sourceCard) {
                        const statusBadge = sourceCard.querySelector('.source-status');
                        if (statusBadge) {
                            statusBadge.className = `source-status ${source.status}`;
                            statusBadge.innerHTML = source.status === 'active' 
                                ? '<i class="fas fa-check-circle"></i> Active' 
                                : '<i class="fas fa-times-circle"></i> Inactive';
                        }
                    }
                });
            }
        })
        .catch(error => console.error('Error updating source status:', error));
}

// Performance monitoring with detailed metrics
function monitorPerformance() {
    if (window.performance && window.performance.timing) {
        const timing = performance.timing;
        const loadTime = timing.loadEventEnd - timing.navigationStart;
        const domReady = timing.domContentLoadedEventEnd - timing.navigationStart;
        
        // Log performance metrics
        console.log('Performance Metrics:', {
            'Page Load Time': loadTime + 'ms',
            'DOM Ready': domReady + 'ms',
            'DNS Lookup': (timing.domainLookupEnd - timing.domainLookupStart) + 'ms',
            'TCP Connection': (timing.connectEnd - timing.connectStart) + 'ms'
        });
        
        // Warn if load time is slow
        if (loadTime > 3000) {
            console.warn('⚠️ Page load time slow:', loadTime, 'ms');
        }
        
        // Send performance data to analytics (if available)
        if (typeof gtag !== 'undefined') {
            gtag('event', 'timing_complete', {
                'name': 'load',
                'value': loadTime,
                'event_category': 'Page Performance'
            });
        }
    }
}

// Intersection Observer for lazy loading images
function setupLazyLoading() {
    const imageObserver = new IntersectionObserver((entries, observer) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const img = entry.target;
                
                // Load the image
                if (img.dataset.src) {
                    img.src = img.dataset.src;
                    img.classList.add('loaded');
                    
                    // Optional: Add fade-in effect
                    img.style.opacity = '0';
                    img.onload = () => {
                        img.style.transition = 'opacity 0.3s';
                        img.style.opacity = '1';
                    };
                }
                
                observer.unobserve(img);
            }
        });
    }, {
        rootMargin: '50px', // Start loading 50px before entering viewport
        threshold: 0.01
    });
    
    // Observe all images with data-src attribute
    document.querySelectorAll('img[data-src]').forEach(img => {
        imageObserver.observe(img);
    });
}

// Real-time statistics updater
function updateStatistics() {
    fetch('/api/stats')
        .then(response => response.json())
        .then(data => {
            // Update total posts
            const totalPostsEl = document.getElementById('totalPosts');
            if (totalPostsEl) {
                animateNumber(totalPostsEl, parseInt(totalPostsEl.textContent), data.total_posts);
            }
            
            // Update total views
            const totalViewsEl = document.getElementById('totalViews');
            if (totalViewsEl) {
                animateNumber(totalViewsEl, parseInt(totalViewsEl.textContent), data.total_views);
            }
            
            // Update last update time
            const lastUpdateEl = document.getElementById('lastUpdate');
            if (lastUpdateEl) {
                lastUpdateEl.textContent = `Last updated: ${data.last_update}`;
            }
        })
        .catch(error => console.error('Error updating statistics:', error));
}

// Animate number changes
function animateNumber(element, start, end) {
    const duration = 1000; // 1 second
    const startTime = performance.now();
    
    function update(currentTime) {
        const elapsed = currentTime - startTime;
        const progress = Math.min(elapsed / duration, 1);
        
        const current = Math.floor(start + (end - start) * progress);
        element.textContent = current.toLocaleString();
        
        if (progress < 1) {
            requestAnimationFrame(update);
        }
    }
    
    requestAnimationFrame(update);
}

// Search functionality with suggestions
function setupSearchAutocomplete() {
    const searchInput = document.querySelector('.search-input');
    if (!searchInput) return;
    
    let debounceTimer;
    
    searchInput.addEventListener('input', (e) => {
        clearTimeout(debounceTimer);
        const query = e.target.value.trim();
        
        if (query.length < 2) return;
        
        debounceTimer = setTimeout(() => {
            fetch(`/api/search/suggestions?q=${encodeURIComponent(query)}`)
                .then(response => response.json())
                .then(data => {
                    // Display search suggestions (implement UI as needed)
                    console.log('Search suggestions:', data);
                })
                .catch(error => console.error('Error fetching suggestions:', error));
        }, 300);
    });
}

// Reading progress indicator
function setupReadingProgress() {
    const progressBar = document.createElement('div');
    progressBar.id = 'reading-progress';
    progressBar.style.cssText = `
        position: fixed;
        top: 0;
        left: 0;
        height: 3px;
        background: linear-gradient(90deg, #3b82f6, #10b981);
        width: 0%;
        z-index: 9999;
        transition: width 0.1s;
    `;
    document.body.appendChild(progressBar);
    
    window.addEventListener('scroll', () => {
        const winScroll = document.body.scrollTop || document.documentElement.scrollTop;
        const height = document.documentElement.scrollHeight - document.documentElement.clientHeight;
        const scrolled = (winScroll / height) * 100;
        progressBar.style.width = scrolled + '%';
    });
}

// View counter for articles
function incrementViewCount(postSlug) {
    fetch(`/api/post/${postSlug}/view`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        }
    })
    .then(response => response.json())
    .then(data => {
        const viewCount = document.querySelector('.view-count');
        if (viewCount && data.views) {
            viewCount.textContent = data.views;
        }
    })
    .catch(error => console.error('Error incrementing view count:', error));
}

// Social sharing functionality
function setupSocialSharing() {
    const shareButtons = document.querySelectorAll('.share-btn');
    
    shareButtons.forEach(button => {
        button.addEventListener('click', (e) => {
            e.preventDefault();
            const platform = button.dataset.platform;
            const url = encodeURIComponent(window.location.href);
            const title = encodeURIComponent(document.title);
            
            let shareUrl;
            switch(platform) {
                case 'twitter':
                    shareUrl = `https://twitter.com/intent/tweet?url=${url}&text=${title}`;
                    break;
                case 'facebook':
                    shareUrl = `https://www.facebook.com/sharer/sharer.php?u=${url}`;
                    break;
                case 'whatsapp':
                    shareUrl = `https://wa.me/?text=${title}%20${url}`;
                    break;
                case 'linkedin':
                    shareUrl = `https://www.linkedin.com/sharing/share-offsite/?url=${url}`;
                    break;
            }
            
            if (shareUrl) {
                window.open(shareUrl, '_blank', 'width=600,height=400');
            }
        });
    });
}

// Smooth scroll to sections
function setupSmoothScroll() {
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            const href = this.getAttribute('href');
            if (href !== '#') {
                e.preventDefault();
                const target = document.querySelector(href);
                if (target) {
                    target.scrollIntoView({
                        behavior: 'smooth',
                        block: 'start'
                    });
                }
            }
        });
    });
}

// Back to top button
function setupBackToTop() {
    const backToTop = document.createElement('button');
    backToTop.id = 'back-to-top';
    backToTop.innerHTML = '<i class="fas fa-arrow-up"></i>';
    backToTop.style.cssText = `
        position: fixed;
        bottom: 30px;
        right: 30px;
        width: 50px;
        height: 50px;
        background: linear-gradient(135deg, #3b82f6, #10b981);
        color: white;
        border: none;
        border-radius: 50%;
        cursor: pointer;
        display: none;
        align-items: center;
        justify-content: center;
        font-size: 1.2rem;
        box-shadow: 0 4px 12px rgba(0,0,0,0.2);
        transition: all 0.3s;
        z-index: 999;
    `;
    document.body.appendChild(backToTop);
    
    window.addEventListener('scroll', () => {
        if (window.pageYOffset > 300) {
            backToTop.style.display = 'flex';
        } else {
            backToTop.style.display = 'none';
        }
    });
    
    backToTop.addEventListener('click', () => {
        window.scrollTo({
            top: 0,
            behavior: 'smooth'
        });
    });
}

// Dark mode toggle (optional feature)
function setupDarkMode() {
    const darkModeToggle = document.getElementById('dark-mode-toggle');
    if (!darkModeToggle) return;
    
    const isDarkMode = localStorage.getItem('darkMode') === 'true';
    if (isDarkMode) {
        document.body.classList.add('dark-mode');
    }
    
    darkModeToggle.addEventListener('click', () => {
        document.body.classList.toggle('dark-mode');
        const isDark = document.body.classList.contains('dark-mode');
        localStorage.setItem('darkMode', isDark);
    });
}

// Category filter functionality
function setupCategoryFilter() {
    const filterButtons = document.querySelectorAll('.category-filter-btn');
    const postCards = document.querySelectorAll('.post-card');
    
    filterButtons.forEach(button => {
        button.addEventListener('click', () => {
            const category = button.dataset.category;
            
            // Update active button
            filterButtons.forEach(btn => btn.classList.remove('active'));
            button.classList.add('active');
            
            // Filter posts
            postCards.forEach(card => {
                if (category === 'all' || card.dataset.category === category) {
                    card.style.display = 'block';
                    card.style.animation = 'fadeIn 0.3s';
                } else {
                    card.style.display = 'none';
                }
            });
        });
    });
}

// Toast notification system
function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.style.cssText = `
        position: fixed;
        bottom: 30px;
        right: 30px;
        background: ${type === 'success' ? '#10b981' : type === 'error' ? '#ef4444' : '#3b82f6'};
        color: white;
        padding: 15px 25px;
        border-radius: 10px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.2);
        z-index: 10000;
        animation: slideInRight 0.3s;
    `;
    toast.textContent = message;
    document.body.appendChild(toast);
    
    setTimeout(() => {
        toast.style.animation = 'slideOutRight 0.3s';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// Initialize all functions on DOM load
document.addEventListener('DOMContentLoaded', function() {
    console.log('🇿🇦 Mzansi Insights - Initializing...');
    
    // Core functionality
    updateLiveNewsTicker();
    updateSourceStatus();
    monitorPerformance();
    setupLazyLoading();
    
    // Enhanced features
    setupSearchAutocomplete();
    setupReadingProgress();
    setupSocialSharing();
    setupSmoothScroll();
    setupBackToTop();
    setupDarkMode();
    setupCategoryFilter();
    
    // Update intervals
    setInterval(updateLiveNewsTicker, 60000);      // Every minute
    setInterval(updateSourceStatus, 300000);       // Every 5 minutes
    setInterval(updateStatistics, 120000);         // Every 2 minutes
    
    console.log('✅ All features initialized successfully');
});

// Handle visibility change to pause/resume updates
document.addEventListener('visibilitychange', function() {
    if (document.hidden) {
        console.log('Tab hidden - pausing updates');
    } else {
        console.log('Tab visible - resuming updates');
        updateLiveNewsTicker();
        updateSourceStatus();
    }
});

// Error handling for failed requests
window.addEventListener('error', function(e) {
    console.error('Global error:', e.error);
});

window.addEventListener('unhandledrejection', function(e) {
    console.error('Unhandled promise rejection:', e.reason);
});

// Export functions for use in other scripts
window.MzansiInsights = {
    updateLiveNewsTicker,
    updateSourceStatus,
    updateStatistics,
    showToast,
    incrementViewCount
};

console.log('🚀 Mzansi Insights JS loaded successfully');
