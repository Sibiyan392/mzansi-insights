// ===== ADMIN PANEL FUNCTIONALITY =====
class AdminPanel {
    constructor() {
        this.init();
    }

    init() {
        this.setupSidebar();
        this.setupTheme();
        this.setupNotifications();
        this.setupDataTables();
        this.setupRichTextEditor();
        this.setupFileUpload();
        this.setupAutoPost();
        this.setupAnalytics();
        this.setupQuickActions();
        this.setupRealTimeUpdates();
    }

    // ===== SIDEBAR TOGGLE =====
    setupSidebar() {
        const sidebarToggle = document.querySelector('.sidebar-toggle');
        const sidebar = document.querySelector('.admin-sidebar');
        const mainContent = document.querySelector('.admin-main');

        if (sidebarToggle && sidebar) {
            sidebarToggle.addEventListener('click', () => {
                sidebar.classList.toggle('collapsed');
                mainContent?.classList.toggle('sidebar-collapsed');
                
                // Update toggle icon
                const icon = sidebarToggle.querySelector('i');
                if (sidebar.classList.contains('collapsed')) {
                    icon.className = 'fas fa-bars';
                } else {
                    icon.className = 'fas fa-times';
                }
                
                // Save state
                localStorage.setItem('sidebar_collapsed', sidebar.classList.contains('collapsed'));
            });

            // Load saved state
            if (localStorage.getItem('sidebar_collapsed') === 'true') {
                sidebar.classList.add('collapsed');
                mainContent?.classList.add('sidebar-collapsed');
                const icon = sidebarToggle.querySelector('i');
                if (icon) icon.className = 'fas fa-bars';
            }
        }

        // Active nav item highlighting
        const currentPath = window.location.pathname;
        document.querySelectorAll('.nav-item').forEach(item => {
            if (item.getAttribute('href') === currentPath) {
                item.classList.add('active');
            }
        });
    }

    // ===== ADMIN THEME =====
    setupTheme() {
        const savedTheme = localStorage.getItem('admin_theme') || 'dark';
        this.applyTheme(savedTheme);

        // Theme switcher (if exists)
        const themeSwitch = document.querySelector('.theme-switch');
        if (themeSwitch) {
            themeSwitch.addEventListener('click', () => {
                const currentTheme = document.body.getAttribute('data-theme') || 'dark';
                const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
                this.applyTheme(newTheme);
                this.showNotification(`Switched to ${newTheme} theme`, 'info');
            });
        }
    }

    applyTheme(theme) {
        document.body.setAttribute('data-theme', theme);
        localStorage.setItem('admin_theme', theme);
        
        // Update theme switch icon
        const themeSwitch = document.querySelector('.theme-switch');
        if (themeSwitch) {
            const icon = themeSwitch.querySelector('i');
            icon.className = theme === 'dark' ? 'fas fa-sun' : 'fas fa-moon';
        }
    }

    // ===== NOTIFICATIONS =====
    setupNotifications() {
        const notificationBtn = document.querySelector('.notification-btn');
        if (!notificationBtn) return;

        const notificationCount = notificationBtn.querySelector('.notification-count');
        
        // Load notifications from server
        this.loadNotifications();

        // Mark as read on click
        notificationBtn.addEventListener('click', (e) => {
            e.preventDefault();
            this.showNotificationPanel();
        });

        // Poll for new notifications
        setInterval(() => {
            this.checkNewNotifications();
        }, 30000); // Every 30 seconds
    }

    async loadNotifications() {
        try {
            // Simulated API call
            await new Promise(resolve => setTimeout(resolve, 500));
            
            const notifications = [
                { id: 1, title: 'Auto-post completed', message: 'Generated 5 new posts', time: '10 min ago', type: 'success' },
                { id: 2, title: 'New comment', message: 'John commented on "Latest SASSA Updates"', time: '1 hour ago', type: 'info' },
                { id: 3, title: 'Traffic spike', message: '1,200 visitors in the last hour', time: '2 hours ago', type: 'warning' }
            ];

            this.updateNotificationBadge(notifications.length);
            
        } catch (error) {
            console.error('Failed to load notifications:', error);
        }
    }

    updateNotificationBadge(count) {
        const badge = document.querySelector('.notification-count');
        if (badge) {
            badge.textContent = count;
            badge.style.display = count > 0 ? 'flex' : 'none';
        }
    }

    showNotificationPanel() {
        // Create notification panel
        const panel = document.createElement('div');
        panel.className = 'notifications-panel';
        panel.innerHTML = `
            <div class="panel-header">
                <h3>Notifications</h3>
                <button class="panel-close"><i class="fas fa-times"></i></button>
            </div>
            <div class="notifications-list">
                <div class="notification-item success">
                    <div class="notification-icon">
                        <i class="fas fa-check-circle"></i>
                    </div>
                    <div class="notification-content">
                        <h4>Auto-post completed</h4>
                        <p>Generated 5 new posts from RSS feeds</p>
                        <span class="notification-time">10 minutes ago</span>
                    </div>
                </div>
                <div class="notification-item info">
                    <div class="notification-icon">
                        <i class="fas fa-comment"></i>
                    </div>
                    <div class="notification-content">
                        <h4>New comment</h4>
                        <p>John commented on "Latest SASSA Updates"</p>
                        <span class="notification-time">1 hour ago</span>
                    </div>
                </div>
                <div class="notification-item warning">
                    <div class="notification-icon">
                        <i class="fas fa-chart-line"></i>
                    </div>
                    <div class="notification-content">
                        <h4>Traffic spike</h4>
                        <p>1,200 visitors in the last hour</p>
                        <span class="notification-time">2 hours ago</span>
                    </div>
                </div>
            </div>
            <div class="panel-footer">
                <a href="#" class="view-all-notifications">View All Notifications</a>
            </div>
        `;

        document.body.appendChild(panel);

        // Add styles
        if (!document.querySelector('#notification-panel-styles')) {
            const style = document.createElement('style');
            style.id = 'notification-panel-styles';
            style.textContent = `
                .notifications-panel {
                    position: fixed;
                    top: 70px;
                    right: 20px;
                    width: 400px;
                    background: var(--admin-bg-card);
                    border-radius: var(--admin-radius);
                    box-shadow: var(--admin-shadow);
                    z-index: 1000;
                    border: 1px solid var(--admin-border);
                    animation: slideDown 0.3s ease-out;
                }
                .panel-header {
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    padding: 20px;
                    border-bottom: 1px solid var(--admin-border);
                }
                .panel-header h3 {
                    margin: 0;
                    color: var(--admin-text-primary);
                }
                .panel-close {
                    background: none;
                    border: none;
                    color: var(--admin-text-secondary);
                    cursor: pointer;
                    font-size: 1.2rem;
                }
                .notifications-list {
                    max-height: 400px;
                    overflow-y: auto;
                }
                .notification-item {
                    display: flex;
                    gap: 15px;
                    padding: 15px 20px;
                    border-bottom: 1px solid var(--admin-border);
                    transition: background 0.3s ease;
                }
                .notification-item:hover {
                    background: var(--admin-bg-hover);
                }
                .notification-item.success {
                    border-left: 4px solid var(--admin-success);
                }
                .notification-item.info {
                    border-left: 4px solid var(--admin-primary);
                }
                .notification-item.warning {
                    border-left: 4px solid var(--admin-warning);
                }
                .notification-icon {
                    width: 40px;
                    height: 40px;
                    border-radius: 50%;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    flex-shrink: 0;
                }
                .notification-item.success .notification-icon {
                    background: rgba(76, 201, 240, 0.1);
                    color: var(--admin-success);
                }
                .notification-item.info .notification-icon {
                    background: rgba(67, 97, 238, 0.1);
                    color: var(--admin-primary);
                }
                .notification-item.warning .notification-icon {
                    background: rgba(255, 158, 0, 0.1);
                    color: var(--admin-warning);
                }
                .notification-content {
                    flex: 1;
                }
                .notification-content h4 {
                    margin: 0 0 5px;
                    color: var(--admin-text-primary);
                    font-size: 0.95rem;
                }
                .notification-content p {
                    margin: 0 0 5px;
                    color: var(--admin-text-secondary);
                    font-size: 0.85rem;
                    line-height: 1.4;
                }
                .notification-time {
                    font-size: 0.75rem;
                    color: var(--admin-text-muted);
                }
                .panel-footer {
                    padding: 15px 20px;
                    text-align: center;
                    border-top: 1px solid var(--admin-border);
                }
                .view-all-notifications {
                    color: var(--admin-primary);
                    text-decoration: none;
                    font-size: 0.9rem;
                }
                @keyframes slideDown {
                    from {
                        opacity: 0;
                        transform: translateY(-10px);
                    }
                    to {
                        opacity: 1;
                        transform: translateY(0);
                    }
                }
            `;
            document.head.appendChild(style);
        }

        // Close panel
        const closeBtn = panel.querySelector('.panel-close');
        closeBtn.addEventListener('click', () => {
            panel.style.animation = 'slideUp 0.3s ease-out forwards';
            setTimeout(() => panel.remove(), 300);
        });

        // Close on outside click
        document.addEventListener('click', (e) => {
            if (!panel.contains(e.target) && !e.target.closest('.notification-btn')) {
                panel.style.animation = 'slideUp 0.3s ease-out forwards';
                setTimeout(() => panel.remove(), 300);
            }
        });

        // Add slideUp animation
        if (!document.querySelector('#slide-up-styles')) {
            const style = document.createElement('style');
            style.id = 'slide-up-styles';
            style.textContent = `
                @keyframes slideUp {
                    from {
                        opacity: 1;
                        transform: translateY(0);
                    }
                    to {
                        opacity: 0;
                        transform: translateY(-10px);
                    }
                }
            `;
            document.head.appendChild(style);
        }
    }

    checkNewNotifications() {
        // Simulate checking for new notifications
        const hasNew = Math.random() > 0.7; // 30% chance of new notification
        
        if (hasNew) {
            const badge = document.querySelector('.notification-count');
            if (badge) {
                const current = parseInt(badge.textContent) || 0;
                badge.textContent = current + 1;
                badge.style.display = 'flex';
                
                // Show desktop notification
                if (Notification.permission === 'granted') {
                    new Notification('SA Updates Admin', {
                        body: 'New notification received',
                        icon: '/static/img/logo.png'
                    });
                }
            }
        }
    }

    // ===== DATA TABLES =====
    setupDataTables() {
        const tables = document.querySelectorAll('.data-table');
        
        tables.forEach(table => {
            this.enhanceTable(table);
        });
    }

    enhanceTable(table) {
        // Add sorting
        const headers = table.querySelectorAll('th[data-sort]');
        headers.forEach(header => {
            header.style.cursor = 'pointer';
            header.addEventListener('click', () => {
                this.sortTable(table, header);
            });
        });

        // Add search
        const searchContainer = document.createElement('div');
        searchContainer.className = 'table-search';
        searchContainer.innerHTML = `
            <input type="text" placeholder="Search table..." class="search-input">
            <button class="search-clear"><i class="fas fa-times"></i></button>
        `;
        table.parentNode.insertBefore(searchContainer, table);

        const searchInput = searchContainer.querySelector('.search-input');
        searchInput.addEventListener('input', (e) => {
            this.filterTable(table, e.target.value);
        });

        searchContainer.querySelector('.search-clear').addEventListener('click', () => {
            searchInput.value = '';
            this.filterTable(table, '');
            searchInput.focus();
        });

        // Add pagination controls
        this.addPagination(table);
    }

    sortTable(table, header) {
        const column = header.cellIndex;
        const rows = Array.from(table.querySelectorAll('tbody tr'));
        const direction = header.getAttribute('data-sort-direction') || 'asc';
        
        rows.sort((a, b) => {
            const aVal = a.cells[column].textContent.trim();
            const bVal = b.cells[column].textContent.trim();
            
            // Try to parse as number
            const aNum = parseFloat(aVal.replace(/[^\d.-]/g, ''));
            const bNum = parseFloat(bVal.replace(/[^\d.-]/g, ''));
            
            if (!isNaN(aNum) && !isNaN(bNum)) {
                return direction === 'asc' ? aNum - bNum : bNum - aNum;
            }
            
            // Otherwise sort as string
            return direction === 'asc' 
                ? aVal.localeCompare(bVal)
                : bVal.localeCompare(aVal);
        });
        
        // Update table
        const tbody = table.querySelector('tbody');
        rows.forEach(row => tbody.appendChild(row));
        
        // Update sort direction
        header.setAttribute('data-sort-direction', direction === 'asc' ? 'desc' : 'asc');
        
        // Update sort indicator
        table.querySelectorAll('th').forEach(th => {
            th.classList.remove('sort-asc', 'sort-desc');
        });
        header.classList.add(`sort-${direction}`);
    }

    filterTable(table, query) {
        const rows = table.querySelectorAll('tbody tr');
        query = query.toLowerCase();
        
        rows.forEach(row => {
            const text = row.textContent.toLowerCase();
            row.style.display = text.includes(query) ? '' : 'none';
        });
    }

    addPagination(table) {
        const rowsPerPage = 10;
        const rows = table.querySelectorAll('tbody tr');
        const pageCount = Math.ceil(rows.length / rowsPerPage);
        
        if (pageCount <= 1) return;
        
        const pagination = document.createElement('div');
        pagination.className = 'table-pagination';
        
        // Create pagination controls
        let paginationHTML = `
            <div class="pagination-info">
                Showing <span class="page-start">1</span>-<span class="page-end">${Math.min(rowsPerPage, rows.length)}</span> of ${rows.length}
            </div>
            <div class="pagination-controls">
                <button class="page-btn prev-btn" disabled>
                    <i class="fas fa-chevron-left"></i>
                </button>
                <div class="page-numbers">
        `;
        
        for (let i = 1; i <= Math.min(pageCount, 5); i++) {
            paginationHTML += `<button class="page-number ${i === 1 ? 'active' : ''}">${i}</button>`;
        }
        
        if (pageCount > 5) {
            paginationHTML += `<span class="ellipsis">...</span><button class="page-number">${pageCount}</button>`;
        }
        
        paginationHTML += `
                </div>
                <button class="page-btn next-btn ${pageCount > 1 ? '' : 'disabled'}">
                    <i class="fas fa-chevron-right"></i>
                </button>
            </div>
        `;
        
        pagination.innerHTML = paginationHTML;
        table.parentNode.appendChild(pagination);
        
        // Pagination logic
        let currentPage = 1;
        
        function showPage(page) {
            const start = (page - 1) * rowsPerPage;
            const end = start + rowsPerPage;
            
            rows.forEach((row, index) => {
                row.style.display = (index >= start && index < end) ? '' : 'none';
            });
            
            // Update pagination info
            pagination.querySelector('.page-start').textContent = start + 1;
            pagination.querySelector('.page-end').textContent = Math.min(end, rows.length);
            
            // Update active page
            pagination.querySelectorAll('.page-number').forEach(btn => {
                btn.classList.remove('active');
                if (parseInt(btn.textContent) === page) {
                    btn.classList.add('active');
                }
            });
            
            // Update button states
            pagination.querySelector('.prev-btn').disabled = page === 1;
            pagination.querySelector('.next-btn').disabled = page === pageCount;
        }
        
        // Event listeners
        pagination.querySelector('.prev-btn').addEventListener('click', () => {
            if (currentPage > 1) {
                currentPage--;
                showPage(currentPage);
            }
        });
        
        pagination.querySelector('.next-btn').addEventListener('click', () => {
            if (currentPage < pageCount) {
                currentPage++;
                showPage(currentPage);
            }
        });
        
        pagination.querySelectorAll('.page-number').forEach(btn => {
            btn.addEventListener('click', () => {
                currentPage = parseInt(btn.textContent);
                showPage(currentPage);
            });
        });
        
        // Show first page
        showPage(1);
    }

    // ===== RICH TEXT EDITOR =====
    setupRichTextEditor() {
        const textareas = document.querySelectorAll('textarea.rich-text');
        
        textareas.forEach(textarea => {
            this.initRichTextEditor(textarea);
        });
    }

    initRichTextEditor(textarea) {
        const editorContainer = document.createElement('div');
        editorContainer.className = 'rich-text-editor';
        
        // Toolbar
        const toolbar = document.createElement('div');
        toolbar.className = 'editor-toolbar';
        toolbar.innerHTML = `
            <button type="button" data-command="bold"><i class="fas fa-bold"></i></button>
            <button type="button" data-command="italic"><i class="fas fa-italic"></i></button>
            <button type="button" data-command="underline"><i class="fas fa-underline"></i></button>
            <div class="toolbar-separator"></div>
            <button type="button" data-command="insertUnorderedList"><i class="fas fa-list-ul"></i></button>
            <button type="button" data-command="insertOrderedList"><i class="fas fa-list-ol"></i></button>
            <div class="toolbar-separator"></div>
            <button type="button" data-command="createLink"><i class="fas fa-link"></i></button>
            <button type="button" data-command="unlink"><i class="fas fa-unlink"></i></button>
            <div class="toolbar-separator"></div>
            <button type="button" data-command="formatBlock" data-value="h2"><i class="fas fa-heading"></i> H2</button>
            <button type="button" data-command="formatBlock" data-value="h3"><i class="fas fa-heading"></i> H3</button>
            <div class="toolbar-separator"></div>
            <button type="button" data-command="undo"><i class="fas fa-undo"></i></button>
            <button type="button" data-command="redo"><i class="fas fa-redo"></i></button>
        `;
        
        // Editor content
        const editor = document.createElement('div');
        editor.className = 'editor-content';
        editor.contentEditable = true;
        editor.innerHTML = textarea.value;
        
        // Assemble editor
        editorContainer.appendChild(toolbar);
        editorContainer.appendChild(editor);
        
        // Replace textarea with editor
        textarea.parentNode.insertBefore(editorContainer, textarea);
        textarea.style.display = 'none';
        
        // Update textarea on editor change
        editor.addEventListener('input', () => {
            textarea.value = editor.innerHTML;
        });
        
        // Toolbar functionality
        toolbar.addEventListener('click', (e) => {
            const button = e.target.closest('button');
            if (!button) return;
            
            e.preventDefault();
            editor.focus();
            
            const command = button.dataset.command;
            const value = button.dataset.value;
            
            if (command === 'createLink') {
                const url = prompt('Enter URL:');
                if (url) {
                    document.execCommand(command, false, url);
                }
            } else if (command === 'formatBlock') {
                document.execCommand(command, false, value);
            } else {
                document.execCommand(command, false, null);
            }
            
            // Update textarea
            textarea.value = editor.innerHTML;
        });
        
        // Add editor styles
        if (!document.querySelector('#editor-styles')) {
            const style = document.createElement('style');
            style.id = 'editor-styles';
            style.textContent = `
                .rich-text-editor {
                    border: 1px solid var(--admin-border);
                    border-radius: var(--admin-radius);
                    overflow: hidden;
                }
                .editor-toolbar {
                    background: var(--admin-bg-secondary);
                    padding: 10px;
                    border-bottom: 1px solid var(--admin-border);
                    display: flex;
                    flex-wrap: wrap;
                    gap: 5px;
                }
                .editor-toolbar button {
                    background: var(--admin-bg-card);
                    border: 1px solid var(--admin-border);
                    color: var(--admin-text-secondary);
                    padding: 8px 12px;
                    border-radius: 4px;
                    cursor: pointer;
                    display: flex;
                    align-items: center;
                    gap: 5px;
                    font-size: 0.9rem;
                    transition: all 0.3s ease;
                }
                .editor-toolbar button:hover {
                    background: var(--admin-bg-hover);
                    color: var(--admin-text-primary);
                    border-color: var(--admin-primary);
                }
                .toolbar-separator {
                    width: 1px;
                    background: var(--admin-border);
                    margin: 0 5px;
                }
                .editor-content {
                    min-height: 300px;
                    padding: 20px;
                    background: var(--admin-bg-primary);
                    color: var(--admin-text-primary);
                    outline: none;
                    overflow-y: auto;
                }
                .editor-content:focus {
                    outline: 2px solid var(--admin-primary);
                    outline-offset: -2px;
                }
                .editor-content h2 {
                    font-size: 1.5rem;
                    margin: 20px 0 10px;
                }
                .editor-content h3 {
                    font-size: 1.3rem;
                    margin: 15px 0 8px;
                }
                .editor-content ul, .editor-content ol {
                    margin: 10px 0;
                    padding-left: 30px;
                }
                .editor-content a {
                    color: var(--admin-primary);
                    text-decoration: underline;
                }
            `;
            document.head.appendChild(style);
        }
    }

    // ===== FILE UPLOAD =====
    setupFileUpload() {
        const uploadAreas = document.querySelectorAll('.upload-area');
        
        uploadAreas.forEach(area => {
            this.initFileUpload(area);
        });
    }

    initFileUpload(uploadArea) {
        const input = uploadArea.querySelector('input[type="file"]');
        const preview = uploadArea.querySelector('.upload-preview');
        const dropZone = uploadArea.querySelector('.upload-dropzone');
        
        if (!input || !dropZone) return;
        
        // Click on dropzone to trigger file input
        dropZone.addEventListener('click', () => {
            input.click();
        });
        
        // Handle file selection
        input.addEventListener('change', (e) => {
            this.handleFileSelection(e.target.files, preview);
        });
        
        // Drag and drop
        dropZone.addEventListener('dragover', (e) => {
            e.preventDefault();
            dropZone.classList.add('dragover');
        });
        
        dropZone.addEventListener('dragleave', () => {
            dropZone.classList.remove('dragover');
        });
        
        dropZone.addEventListener('drop', (e) => {
            e.preventDefault();
            dropZone.classList.remove('dragover');
            
            if (e.dataTransfer.files.length) {
                input.files = e.dataTransfer.files;
                this.handleFileSelection(e.dataTransfer.files, preview);
            }
        });
        
        // Remove file
        uploadArea.addEventListener('click', (e) => {
            if (e.target.classList.contains('remove-file')) {
                preview.innerHTML = '';
                input.value = '';
                dropZone.style.display = 'block';
            }
        });
    }

    handleFileSelection(files, preview) {
        if (!files.length) return;
        
        const file = files[0];
        
        // Validate file type
        const validTypes = ['image/jpeg', 'image/png', 'image/gif', 'image/webp'];
        if (!validTypes.includes(file.type)) {
            this.showNotification('Please upload an image file (JPEG, PNG, GIF, WebP)', 'error');
            return;
        }
        
        // Validate file size (max 5MB)
        if (file.size > 5 * 1024 * 1024) {
            this.showNotification('File size must be less than 5MB', 'error');
            return;
        }
        
        // Create preview
        const reader = new FileReader();
        reader.onload = (e) => {
            preview.innerHTML = `
                <div class="file-preview">
                    <img src="${e.target.result}" alt="Preview">
                    <button type="button" class="remove-file">
                        <i class="fas fa-times"></i>
                    </button>
                    <div class="file-info">
                        <span>${file.name}</span>
                        <span>${(file.size / 1024).toFixed(1)} KB</span>
                    </div>
                </div>
            `;
            
            // Hide dropzone
            const dropZone = preview.parentNode.querySelector('.upload-dropzone');
            if (dropZone) dropZone.style.display = 'none';
        };
        reader.readAsDataURL(file);
    }

    // ===== AUTO-POST =====
    setupAutoPost() {
        const runAutoBtn = document.querySelector('#run-auto-post');
        if (!runAutoBtn) return;
        
        runAutoBtn.addEventListener('click', async (e) => {
            e.preventDefault();
            
            const originalText = runAutoBtn.innerHTML;
            runAutoBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Running...';
            runAutoBtn.disabled = true;
            
            try {
                // Simulate API call to run auto-post
                await new Promise(resolve => setTimeout(resolve, 3000));
                
                this.showNotification('Auto-post completed successfully! Generated 5 new articles.', 'success');
                
                // Refresh page after 2 seconds
                setTimeout(() => {
                    window.location.reload();
                }, 2000);
                
            } catch (error) {
                this.showNotification('Auto-post failed: ' + error.message, 'error');
            } finally {
                runAutoBtn.innerHTML = originalText;
                runAutoBtn.disabled = false;
            }
        });
    }

    // ===== ANALYTICS =====
    setupAnalytics() {
        // Initialize charts if on dashboard
        if (document.querySelector('.analytics-chart')) {
            this.initAnalyticsCharts();
        }
        
        // Update stats every minute
        setInterval(() => {
            this.updateLiveStats();
        }, 60000);
    }

    initAnalyticsCharts() {
        // Simple chart implementation using CSS/JS
        // In production, you might want to use Chart.js or similar
        
        const charts = document.querySelectorAll('.analytics-chart');
        
        charts.forEach(chart => {
            const type = chart.dataset.chartType || 'line';
            
            if (type === 'line') {
                this.createLineChart(chart);
            } else if (type === 'bar') {
                this.createBarChart(chart);
            }
        });
    }

    createLineChart(container) {
        // Mock data for line chart
        const data = [65, 59, 80, 81, 56, 55, 40, 70, 90, 100, 85, 95];
        const max = Math.max(...data);
        
        const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
        svg.setAttribute('viewBox', '0 0 400 200');
        svg.setAttribute('class', 'line-chart');
        
        let path = `M 0,${200 - (data[0] / max) * 180}`;
        
        for (let i = 1; i < data.length; i++) {
            const x = (i / (data.length - 1)) * 380 + 10;
            const y = 200 - (data[i] / max) * 180;
            path += ` L ${x},${y}`;
        }
        
        const pathElement = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        pathElement.setAttribute('d', path);
        pathElement.setAttribute('fill', 'none');
        pathElement.setAttribute('stroke', 'var(--admin-primary)');
        pathElement.setAttribute('stroke-width', '2');
        
        svg.appendChild(pathElement);
        container.appendChild(svg);
    }

    createBarChart(container) {
        // Mock data for bar chart
        const data = [30, 45, 60, 75, 90, 65, 50];
        const max = Math.max(...data);
        
        const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
        svg.setAttribute('viewBox', '0 0 400 200');
        svg.setAttribute('class', 'bar-chart');
        
        const barWidth = 40;
        const spacing = 10;
        
        data.forEach((value, index) => {
            const x = index * (barWidth + spacing) + 20;
            const height = (value / max) * 180;
            const y = 200 - height;
            
            const rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
            rect.setAttribute('x', x);
            rect.setAttribute('y', y);
            rect.setAttribute('width', barWidth);
            rect.setAttribute('height', height);
            rect.setAttribute('fill', 'var(--admin-primary)');
            
            svg.appendChild(rect);
        });
        
        container.appendChild(svg);
    }

    async updateLiveStats() {
        // Simulate fetching updated stats
        const stats = {
            views: Math.floor(Math.random() * 100),
            posts: Math.floor(Math.random() * 5),
            users: Math.floor(Math.random() * 10)
        };
        
        // Update stat cards
        document.querySelectorAll('.stat-card').forEach(card => {
            const statType = card.querySelector('p')?.textContent?.toLowerCase();
            const valueElement = card.querySelector('h3');
            
            if (valueElement && statType) {
                const currentValue = parseInt(valueElement.textContent) || 0;
                
                if (statType.includes('view')) {
                    valueElement.textContent = currentValue + stats.views;
                } else if (statType.includes('post')) {
                    valueElement.textContent = currentValue + stats.posts;
                }
                
                // Add animation
                valueElement.style.transform = 'scale(1.1)';
                setTimeout(() => {
                    valueElement.style.transform = 'scale(1)';
                }, 300);
            }
        });
    }

    // ===== QUICK ACTIONS =====
    setupQuickActions() {
        const quickActionBtns = document.querySelectorAll('.quick-action-btn');
        
        quickActionBtns.forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.preventDefault();
                const action = btn.dataset.action;
                this.handleQuickAction(action);
            });
        });
    }

    handleQuickAction(action) {
        switch (action) {
            case 'clear-cache':
                this.clearCache();
                break;
            case 'backup-db':
                this.backupDatabase();
                break;
            case 'optimize-db':
                this.optimizeDatabase();
                break;
            case 'test-email':
                this.testEmailSystem();
                break;
        }
    }

    async clearCache() {
        try {
            // Simulate API call
            await new Promise(resolve => setTimeout(resolve, 1000));
            this.showNotification('Cache cleared successfully', 'success');
        } catch (error) {
            this.showNotification('Failed to clear cache', 'error');
        }
    }

    async backupDatabase() {
        try {
            // Simulate API call
            await new Promise(resolve => setTimeout(resolve, 2000));
            
            // Create download link
            const backupData = {
                timestamp: new Date().toISOString(),
                posts: 150,
                views: 50000,
                size: '2.5 MB'
            };
            
            const blob = new Blob([JSON.stringify(backupData, null, 2)], { type: 'application/json' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `backup-${new Date().toISOString().split('T')[0]}.json`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
            
            this.showNotification('Database backup downloaded', 'success');
        } catch (error) {
            this.showNotification('Failed to create backup', 'error');
        }
    }

    async optimizeDatabase() {
        try {
            // Simulate API call
            await new Promise(resolve => setTimeout(resolve, 1500));
            this.showNotification('Database optimized successfully', 'success');
        } catch (error) {
            this.showNotification('Failed to optimize database', 'error');
        }
    }

    async testEmailSystem() {
        try {
            // Simulate API call
            await new Promise(resolve => setTimeout(resolve, 1000));
            this.showNotification('Test email sent successfully', 'success');
        } catch (error) {
            this.showNotification('Failed to send test email', 'error');
        }
    }

    // ===== REAL-TIME UPDATES =====
    setupRealTimeUpdates() {
        // Simulate WebSocket connection for real-time updates
        // In production, use actual WebSocket or Server-Sent Events
        
        setInterval(() => {
            this.simulateRealTimeUpdate();
        }, 10000); // Every 10 seconds
    }

    simulateRealTimeUpdate() {
        const updates = [
            { type: 'view', message: 'New visitor from Johannesburg' },
            { type: 'comment', message: 'New comment on recent post' },
            { type: 'post', message: 'Auto-post generated new content' }
        ];
        
        const update = updates[Math.floor(Math.random() * updates.length)];
        
        // Show toast notification
        this.showToastNotification(update);
        
        // Update dashboard stats
        this.updateDashboardStats(update.type);
    }

    showToastNotification(update) {
        const toast = document.createElement('div');
        toast.className = `toast-notification toast-${update.type}`;
        toast.innerHTML = `
            <div class="toast-icon">
                <i class="fas fa-${update.type === 'view' ? 'eye' : update.type === 'comment' ? 'comment' : 'newspaper'}"></i>
            </div>
            <div class="toast-content">
                <p>${update.message}</p>
                <span class="toast-time">Just now</span>
            </div>
            <button class="toast-close"><i class="fas fa-times"></i></button>
        `;
        
        document.body.appendChild(toast);
        
        // Auto-remove after 5 seconds
        setTimeout(() => {
            toast.classList.add('fade-out');
            setTimeout(() => toast.remove(), 300);
        }, 5000);
        
        // Close button
        toast.querySelector('.toast-close').addEventListener('click', () => {
            toast.classList.add('fade-out');
            setTimeout(() => toast.remove(), 300);
        });
        
        // Add styles if not present
        if (!document.querySelector('#toast-styles')) {
            const style = document.createElement('style');
            style.id = 'toast-styles';
            style.textContent = `
                .toast-notification {
                    position: fixed;
                    bottom: 20px;
                    right: 20px;
                    background: var(--admin-bg-card);
                    border: 1px solid var(--admin-border);
                    border-radius: var(--admin-radius);
                    padding: 15px;
                    display: flex;
                    align-items: center;
                    gap: 15px;
                    box-shadow: var(--admin-shadow);
                    z-index: 1000;
                    animation: slideInRight 0.3s ease-out;
                    max-width: 350px;
                }
                .toast-view {
                    border-left: 4px solid var(--admin-success);
                }
                .toast-comment {
                    border-left: 4px solid var(--admin-primary);
                }
                .toast-post {
                    border-left: 4px solid var(--admin-accent);
                }
                .toast-icon {
                    width: 40px;
                    height: 40px;
                    border-radius: 50%;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    flex-shrink: 0;
                }
                .toast-view .toast-icon {
                    background: rgba(76, 201, 240, 0.1);
                    color: var(--admin-success);
                }
                .toast-comment .toast-icon {
                    background: rgba(67, 97, 238, 0.1);
                    color: var(--admin-primary);
                }
                .toast-post .toast-icon {
                    background: rgba(247, 37, 133, 0.1);
                    color: var(--admin-accent);
                }
                .toast-content {
                    flex: 1;
                }
                .toast-content p {
                    margin: 0 0 5px;
                    color: var(--admin-text-primary);
                    font-size: 0.9rem;
                }
                .toast-time {
                    font-size: 0.75rem;
                    color: var(--admin-text-muted);
                }
                .toast-close {
                    background: none;
                    border: none;
                    color: var(--admin-text-secondary);
                    cursor: pointer;
                    padding: 5px;
                }
                .fade-out {
                    animation: fadeOut 0.3s ease-out forwards;
                }
                @keyframes slideInRight {
                    from {
                        opacity: 0;
                        transform: translateX(100%);
                    }
                    to {
                        opacity: 1;
                        transform: translateX(0);
                    }
                }
                @keyframes fadeOut {
                    from {
                        opacity: 1;
                        transform: translateX(0);
                    }
                    to {
                        opacity: 0;
                        transform: translateX(100%);
                    }
                }
            `;
            document.head.appendChild(style);
        }
    }

    updateDashboardStats(type) {
        const statCards = {
            view: document.querySelector('.stat-card:nth-child(2) h3'), // Views card
            comment: document.querySelector('.stat-card:nth-child(4) h3'), // Comments card (if exists)
            post: document.querySelector('.stat-card:nth-child(1) h3') // Posts card
        };
        
        const card = statCards[type];
        if (card) {
            const current = parseInt(card.textContent) || 0;
            card.textContent = current + 1;
            
            // Add highlight animation
            card.style.color = 'var(--admin-success)';
            setTimeout(() => {
                card.style.color = '';
            }, 1000);
        }
    }

    // ===== UTILITY FUNCTIONS =====
    showNotification(message, type = 'info') {
        // Use existing notification system or create simple alert
        alert(`${type.toUpperCase()}: ${message}`);
    }
}

// ===== INITIALIZATION =====
document.addEventListener('DOMContentLoaded', () => {
    window.adminPanel = new AdminPanel();
    
    // Request notification permission
    if (Notification.permission === 'default') {
        Notification.requestPermission();
    }
    
    // Initialize tooltips
    this.initTooltips();
    
    // Initialize form validation
    this.initFormValidation();
    
    // Initialize modal system
    this.initModals();
});

// ===== TOOLTIPS =====
function initTooltips() {
    const tooltipElements = document.querySelectorAll('[data-tooltip]');
    
    tooltipElements.forEach(element => {
        element.addEventListener('mouseenter', (e) => {
            const tooltip = document.createElement('div');
            tooltip.className = 'admin-tooltip';
            tooltip.textContent = e.target.dataset.tooltip;
            
            const rect = e.target.getBoundingClientRect();
            tooltip.style.left = rect.left + rect.width / 2 + 'px';
            tooltip.style.top = rect.top - 10 + 'px';
            tooltip.style.transform = 'translate(-50%, -100%)';
            
            document.body.appendChild(tooltip);
            
            e.target.dataset.tooltipId = tooltip.id = 'tooltip-' + Date.now();
        });
        
        element.addEventListener('mouseleave', (e) => {
            const tooltipId = e.target.dataset.tooltipId;
            if (tooltipId) {
                const tooltip = document.getElementById(tooltipId);
                if (tooltip) {
                    tooltip.remove();
                }
            }
        });
    });
    
    // Add tooltip styles
    if (!document.querySelector('#tooltip-styles')) {
        const style = document.createElement('style');
        style.id = 'tooltip-styles';
        style.textContent = `
            .admin-tooltip {
                position: fixed;
                background: var(--admin-bg-card);
                color: var(--admin-text-primary);
                padding: 8px 12px;
                border-radius: 4px;
                font-size: 0.8rem;
                border: 1px solid var(--admin-border);
                box-shadow: var(--admin-shadow);
                z-index: 10000;
                white-space: nowrap;
                pointer-events: none;
            }
            .admin-tooltip::after {
                content: '';
                position: absolute;
                top: 100%;
                left: 50%;
                transform: translateX(-50%);
                border: 5px solid transparent;
                border-top-color: var(--admin-bg-card);
            }
        `;
        document.head.appendChild(style);
    }
}

// ===== FORM VALIDATION =====
function initFormValidation() {
    const forms = document.querySelectorAll('form.validate');
    
    forms.forEach(form => {
        form.addEventListener('submit', (e) => {
            if (!validateForm(form)) {
                e.preventDefault();
            }
        });
    });
    
    function validateForm(form) {
        let isValid = true;
        
        form.querySelectorAll('[required]').forEach(input => {
            if (!input.value.trim()) {
                showInputError(input, 'This field is required');
                isValid = false;
            } else {
                clearInputError(input);
                
                // Email validation
                if (input.type === 'email') {
                    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
                    if (!emailRegex.test(input.value)) {
                        showInputError(input, 'Please enter a valid email');
                        isValid = false;
                    }
                }
                
                // Password confirmation
                if (input.dataset.match) {
                    const matchInput = document.querySelector(input.dataset.match);
                    if (matchInput && input.value !== matchInput.value) {
                        showInputError(input, 'Passwords do not match');
                        isValid = false;
                    }
                }
            }
        });
        
        return isValid;
    }
    
    function showInputError(input, message) {
        const errorElement = input.nextElementSibling?.classList.contains('error-message') 
            ? input.nextElementSibling 
            : document.createElement('div');
        
        errorElement.className = 'error-message';
        errorElement.textContent = message;
        errorElement.style.color = 'var(--admin-danger)';
        errorElement.style.fontSize = '0.8rem';
        errorElement.style.marginTop = '5px';
        
        if (!input.nextElementSibling?.classList.contains('error-message')) {
            input.parentNode.appendChild(errorElement);
        }
        
        input.style.borderColor = 'var(--admin-danger)';
    }
    
    function clearInputError(input) {
        const errorElement = input.nextElementSibling;
        if (errorElement?.classList.contains('error-message')) {
            errorElement.remove();
        }
        input.style.borderColor = '';
    }
}

// ===== MODALS =====
function initModals() {
    // Open modals
    document.querySelectorAll('[data-modal-target]').forEach(trigger => {
        trigger.addEventListener('click', (e) => {
            e.preventDefault();
            const modalId = trigger.dataset.modalTarget;
            const modal = document.getElementById(modalId);
            if (modal) {
                openModal(modal);
            }
        });
    });
    
    // Close modals
    document.querySelectorAll('.modal-close, .modal-overlay').forEach(closeBtn => {
        closeBtn.addEventListener('click', (e) => {
            if (e.target.classList.contains('modal-close') || e.target.classList.contains('modal-overlay')) {
                closeModal(e.target.closest('.modal'));
            }
        });
    });
    
    // Close on escape key
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            const openModal = document.querySelector('.modal.active');
            if (openModal) {
                closeModal(openModal);
            }
        }
    });
    
    function openModal(modal) {
        modal.classList.add('active');
        document.body.style.overflow = 'hidden';
    }
    
    function closeModal(modal) {
        modal.classList.remove('active');
        setTimeout(() => {
            document.body.style.overflow = '';
        }, 300);
    }
}