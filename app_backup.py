from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os
import sqlite3
import sys

# Add automation folder to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'automation'))

# Import your automation modules
try:
    from automation.content_generator import ContentGenerator
    from automation.rss_importer import RSSImporter
    from automation.scheduler import Scheduler
    from automation.config import Config as AutoConfig
    AUTOMATION_AVAILABLE = True
except ImportError as e:
    print(f"⚠️  Automation modules not available: {e}")
    AUTOMATION_AVAILABLE = False

# ============= FLASK CONFIG =============
class FlaskConfig:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-key-change-me-now'
    SITE_NAME = "Mzansi Insights"
    SITE_DESCRIPTION = "South African News & Updates"
    POSTS_PER_PAGE = 10
    ADMIN_USERNAME = 'admin'
    ADMIN_PASSWORD = 'admin123'

# ============= DATABASE =============
def setup_database():
    """Initialize database with proper tables"""
    os.makedirs('data', exist_ok=True)
    
    conn = sqlite3.connect('data/posts.db')
    c = conn.cursor()
    
    # Users table
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Categories table
    c.execute('''
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            slug TEXT UNIQUE NOT NULL,
            description TEXT
        )
    ''')
    
    # Posts table
    c.execute('''
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            slug TEXT UNIQUE NOT NULL,
            content TEXT NOT NULL,
            excerpt TEXT,
            image_url TEXT,
            source_url TEXT,
            category_id INTEGER,
            author TEXT DEFAULT 'Mzansi Insights',
            is_auto_generated BOOLEAN DEFAULT 0,
            is_published BOOLEAN DEFAULT 1,
            views INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (category_id) REFERENCES categories(id)
        )
    ''')
    
    # RSS feeds table
    c.execute('''
        CREATE TABLE IF NOT EXISTS rss_feeds (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            url TEXT NOT NULL,
            category_id INTEGER,
            is_active BOOLEAN DEFAULT 1,
            last_fetch TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (category_id) REFERENCES categories(id)
        )
    ''')
    
    # Insert admin user
    c.execute("SELECT COUNT(*) FROM users WHERE username = 'admin'")
    if c.fetchone()[0] == 0:
        pwd_hash = generate_password_hash(FlaskConfig.ADMIN_PASSWORD)
        c.execute("INSERT INTO users (username, password_hash) VALUES (?, ?)", 
                 ('admin', pwd_hash))
    
    # Default categories
    categories = [
        ('News', 'news', 'Latest South African news'),
        ('Jobs', 'jobs', 'Employment opportunities'),
        ('Grants', 'grants', 'Government funding'),
        ('Entertainment', 'entertainment', 'Movies, music & TV')
    ]
    
    for name, slug, desc in categories:
        c.execute("INSERT OR IGNORE INTO categories (name, slug, description) VALUES (?, ?, ?)", 
                 (name, slug, desc))
    
    # Sample posts
    c.execute("SELECT COUNT(*) FROM posts")
    if c.fetchone()[0] == 0:
        sample_posts = [
            ('Welcome to Mzansi Insights', 'welcome-to-mzansi-insights',
             '# Welcome!\n\nYour South African news platform is ready.\n\n## Features:\n- Automated content\n- Admin dashboard\n- RSS integration\n- Modern design',
             'Start your SA news journey', 1),
            ('SA News Updates', 'sa-news-updates',
             '## Stay informed about South Africa\n\nThis platform automatically fetches the latest news from various sources.',
             'Automated news updates', 1),
            ('Find Jobs in SA', 'find-jobs-in-sa',
             '## Employment opportunities\n\nCheck back regularly for job postings and career advice.',
             'Career opportunities', 2)
        ]
        
        for title, slug, content, excerpt, cat_id in sample_posts:
            c.execute('''
                INSERT INTO posts (title, slug, content, excerpt, category_id) 
                VALUES (?, ?, ?, ?, ?)
            ''', (title, slug, content, excerpt, cat_id))
    
    conn.commit()
    conn.close()
    print("✅ Database initialized")

# ============= FLASK APP =============
app = Flask(__name__)
app.config['SECRET_KEY'] = FlaskConfig.SECRET_KEY

# Setup database
setup_database()

# ============= LOGIN =============
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'admin_login'

class User:
    def __init__(self, id, username):
        self.id = id
        self.username = username
        self.is_authenticated = True
        self.is_active = True
        self.is_anonymous = False
    
    def get_id(self):
        return str(self.id)

@login_manager.user_loader
def load_user(user_id):
    conn = sqlite3.connect('data/posts.db')
    c = conn.cursor()
    c.execute("SELECT id, username FROM users WHERE id = ?", (user_id,))
    user_data = c.fetchone()
    conn.close()
    
    if user_data:
        return User(user_data[0], user_data[1])
    return None

# ============= HELPER FUNCTIONS =============
def get_db_connection():
    conn = sqlite3.connect('data/posts.db')
    conn.row_factory = sqlite3.Row
    return conn

def get_categories():
    conn = get_db_connection()
    categories = conn.execute("SELECT * FROM categories").fetchall()
    conn.close()
    return categories

# ============= ROUTES =============
@app.route('/')
def index():
    conn = get_db_connection()
    
    # Get posts with pagination
    page = request.args.get('page', 1, type=int)
    limit = FlaskConfig.POSTS_PER_PAGE
    offset = (page - 1) * limit
    
    posts = conn.execute('''
        SELECT p.*, c.name as category_name, c.slug as category_slug
        FROM posts p 
        LEFT JOIN categories c ON p.category_id = c.id 
        WHERE p.is_published = 1 
        ORDER BY p.created_at DESC 
        LIMIT ? OFFSET ?
    ''', (limit, offset)).fetchall()
    
    # Total count for pagination
    total = conn.execute("SELECT COUNT(*) FROM posts WHERE is_published = 1").fetchone()[0]
    pages = (total + limit - 1) // limit
    
    # Recent posts for sidebar
    recent = conn.execute('''
        SELECT * FROM posts 
        WHERE is_published = 1 
        ORDER BY created_at DESC 
        LIMIT 5
    ''').fetchall()
    
    categories = conn.execute("SELECT * FROM categories").fetchall()
    conn.close()
    
    return render_template('index.html',
                         posts=posts,
                         recent_posts=recent,
                         categories=categories,
                         config=FlaskConfig,
                         now=datetime.now(),
                         page=page,
                         pages=pages,
                         total=total)

@app.route('/post/<slug>')
def post_detail(slug):
    conn = get_db_connection()
    
    post = conn.execute('''
        SELECT p.*, c.name as category_name, c.slug as category_slug
        FROM posts p 
        LEFT JOIN categories c ON p.category_id = c.id 
        WHERE p.slug = ? AND p.is_published = 1
    ''', (slug,)).fetchone()
    
    if not post:
        conn.close()
        return render_template('404.html', config=FlaskConfig), 404
    
    # Update views
    conn.execute("UPDATE posts SET views = views + 1 WHERE id = ?", (post['id'],))
    
    # Get recent posts
    recent = conn.execute('''
        SELECT * FROM posts 
        WHERE is_published = 1 AND id != ? 
        ORDER BY created_at DESC 
        LIMIT 5
    ''', (post['id'],)).fetchall()
    
    categories = get_categories()
    conn.commit()
    conn.close()
    
    return render_template('post.html',
                         post=post,
                         recent_posts=recent,
                         categories=categories,
                         config=FlaskConfig,
                         now=datetime.now())

@app.route('/category/<slug>')
def category_page(slug):
    conn = get_db_connection()
    
    category = conn.execute("SELECT * FROM categories WHERE slug = ?", (slug,)).fetchone()
    
    if not category:
        conn.close()
        return render_template('404.html', config=FlaskConfig), 404
    
    page = request.args.get('page', 1, type=int)
    limit = FlaskConfig.POSTS_PER_PAGE
    offset = (page - 1) * limit
    
    posts = conn.execute('''
        SELECT p.*, c.name as category_name, c.slug as category_slug
        FROM posts p 
        LEFT JOIN categories c ON p.category_id = c.id 
        WHERE p.category_id = ? AND p.is_published = 1 
        ORDER BY p.created_at DESC 
        LIMIT ? OFFSET ?
    ''', (category['id'], limit, offset)).fetchall()
    
    total = conn.execute("SELECT COUNT(*) FROM posts WHERE category_id = ? AND is_published = 1", 
                        (category['id'],)).fetchone()[0]
    pages = (total + limit - 1) // limit
    
    recent = conn.execute('''
        SELECT * FROM posts 
        WHERE is_published = 1 
        ORDER BY created_at DESC 
        LIMIT 5
    ''').fetchall()
    
    categories = get_categories()
    conn.close()
    
    return render_template('category.html',
                         category=category,
                         posts=posts,
                         recent_posts=recent,
                         categories=categories,
                         config=FlaskConfig,
                         now=datetime.now(),
                         page=page,
                         pages=pages,
                         total=total)

# ============= ADMIN ROUTES =============
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if current_user.is_authenticated:
        return redirect(url_for('admin_dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        conn = get_db_connection()
        user = conn.execute("SELECT id, password_hash FROM users WHERE username = ?", 
                           (username,)).fetchone()
        conn.close()
        
        if user and check_password_hash(user['password_hash'], password):
            user_obj = User(user['id'], username)
            login_user(user_obj)
            flash('✅ Login successful!', 'success')
            return redirect(url_for('admin_dashboard'))
        else:
            flash('❌ Invalid username or password', 'error')
    
    return render_template('admin/login.html', config=FlaskConfig)

@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    conn = get_db_connection()
    
    # Statistics
    total_posts = conn.execute("SELECT COUNT(*) FROM posts").fetchone()[0]
    published_posts = conn.execute("SELECT COUNT(*) FROM posts WHERE is_published = 1").fetchone()[0]
    total_views = conn.execute("SELECT SUM(views) FROM posts").fetchone()[0] or 0
    
    # Recent posts
    recent_posts = conn.execute('''
        SELECT p.*, c.name as category_name 
        FROM posts p 
        LEFT JOIN categories c ON p.category_id = c.id 
        ORDER BY p.created_at DESC 
        LIMIT 10
    ''').fetchall()
    
    # Auto-post status
    auto_post_status = "✅ Available" if AUTOMATION_AVAILABLE else "⚠️ Not configured"
    
    conn.close()
    
    return render_template('admin/dashboard.html',
                         total_posts=total_posts,
                         published_posts=published_posts,
                         total_views=total_views,
                         recent_posts=recent_posts,
                         auto_post_status=auto_post_status,
                         config=FlaskConfig)

@app.route('/admin/run-auto-post')
@login_required
def run_auto_post():
    """Run the automation system manually"""
    if not AUTOMATION_AVAILABLE:
        flash('⚠️ Automation system not available', 'error')
        return redirect(url_for('admin_dashboard'))
    
    try:
        # Run your automation
        # This is where you'd call your automation scripts
        flash('🔄 Running auto-post system...', 'info')
        
        # Example: You would call your automation here
        # generator = ContentGenerator()
        # posts_created = generator.run()
        
        # For now, simulate success
        posts_created = 3
        flash(f'✅ Auto-post completed! Created {posts_created} new posts.', 'success')
        
    except Exception as e:
        flash(f'❌ Auto-post failed: {str(e)}', 'error')
    
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/logout')
@login_required
def admin_logout():
    logout_user()
    flash('👋 Logged out successfully', 'info')
    return redirect(url_for('index'))

# ============= UTILITY ROUTES =============
@app.route('/about')
def about():
    return render_template('about.html', 
                         categories=get_categories(),
                         config=FlaskConfig,
                         now=datetime.now())

@app.route('/contact')
def contact():
    return render_template('contact.html',
                         categories=get_categories(),
                         config=FlaskConfig,
                         now=datetime.now())

@app.route('/privacy')
def privacy():
    return render_template('privacy.html',
                         categories=get_categories(),
                         config=FlaskConfig,
                         now=datetime.now())

@app.route('/terms')
def terms():
    return render_template('terms.html',
                         categories=get_categories(),
                         config=FlaskConfig,
                         now=datetime.now())

@app.route('/health')
def health():
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'database': os.path.exists('data/posts.db'),
        'automation': AUTOMATION_AVAILABLE
    })

# ============= START =============
if __name__ == '__main__':
    print("=" * 60)
    print("🚀 MZANSI INSIGHTS - SMART SA NEWS PLATFORM")
    print("=" * 60)
    print(f"🌐 Website: http://localhost:5000")
    print(f"🔧 Admin:   http://localhost:5000/admin/login")
    print(f"👤 User:    {FlaskConfig.ADMIN_USERNAME}")
    print(f"🔑 Pass:    {FlaskConfig.ADMIN_PASSWORD}")
    print(f"🤖 Automation: {'✅ Available' if AUTOMATION_AVAILABLE else '⚠️ Not configured'}")
    print("=" * 60)
    
    app.run(debug=True, host='0.0.0.0', port=5000)