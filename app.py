# Python 3.13+ compatibility fix
import fix_cgi

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_login import LoginManager, login_user, logout_user, login_required, current_user, UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import os
import sqlite3
import feedparser
import threading
import time
import random
import re
import json
import requests
import sys
import io
import logging

# Fix Unicode encoding for Windows console
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============= FLASK CONFIG =============
class FlaskConfig:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-key-change-me-now-12345'
    SITE_NAME = "Mzansi Insights"
    SITE_DESCRIPTION = "South African News & Updates - Aggregated from Trusted Sources"
    POSTS_PER_PAGE = 12
    ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME', 'admin')
    ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'admin123')
    
    # Adsense IDs
    ADSENSE_ID = os.environ.get('ADSENSE_ID', 'YOUR_ADSENSE_ID_HERE')
    ADSENSE_SLOT_BANNER = "1234567890"
    ADSENSE_SLOT_INARTICLE = "1234567891"
    ADSENSE_SLOT_SQUARE = "1234567892"
    ADSENSE_SLOT_SEARCH = "1234567893"
    
    # Contact Info - USE YOUR REAL INFO
    CONTACT_EMAIL = 'sibiyan4444@gmail.com'
    CONTACT_PHONE = '+27 72 472 8166'
    PHYSICAL_ADDRESS = 'Johannesburg, South Africa'
    SITE_URL = os.environ.get('SITE_URL', 'https://mzansi-insights.onrender.com')
    
    # Content Update
    UPDATE_INTERVAL_MINUTES = 30
    
    # News Sources - SIMPLIFIED
    NEWS_SOURCES = [
        {'name': 'News24', 'url': 'https://www.news24.com/feed', 'category': 'news'},
        {'name': 'TimesLive', 'url': 'https://www.timeslive.co.za/feed/', 'category': 'news'},
        {'name': 'Moneyweb', 'url': 'https://www.moneyweb.co.za/feed/', 'category': 'business'},
        {'name': 'BusinessTech', 'url': 'https://businesstech.co.za/news/feed/', 'category': 'business'},
        {'name': 'MyBroadband', 'url': 'https://mybroadband.co.za/news/feed', 'category': 'technology'},
    ]

# ============= DATABASE =============
def get_db_path():
    """Get the database path"""
    if 'RENDER' in os.environ:
        return '/tmp/posts.db'
    else:
        os.makedirs('data', exist_ok=True)
        return 'data/posts.db'

def setup_database():
    """Initialize database"""
    print("🔄 Setting up database...")
    db_path = get_db_path()
    
    # Create directory if needed
    if '/' in db_path:
        db_dir = os.path.dirname(db_path)
        os.makedirs(db_dir, exist_ok=True)
    
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    # Create tables
    c.execute('''
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            slug TEXT UNIQUE NOT NULL,
            content TEXT NOT NULL,
            excerpt TEXT,
            image_url TEXT,
            source_url TEXT,
            category TEXT DEFAULT 'news',
            author TEXT DEFAULT 'Mzansi Insights',
            views INTEGER DEFAULT 0,
            source_name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create admin user
    c.execute("SELECT COUNT(*) FROM users WHERE username = 'admin'")
    if c.fetchone()[0] == 0:
        pwd_hash = generate_password_hash(FlaskConfig.ADMIN_PASSWORD)
        c.execute("INSERT INTO users (username, password_hash) VALUES (?, ?)", 
                 ('admin', pwd_hash))
        print("✅ Created admin user")
    
    conn.commit()
    conn.close()
    print("✅ Database setup complete")
    return True

def get_db_connection():
    """Get database connection"""
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

# ============= CONTENT FETCHER =============
class ContentFetcher:
    def __init__(self):
        self.is_fetching = False
        
    def generate_slug(self, title):
        """Generate URL-friendly slug"""
        slug = re.sub(r'[^a-zA-Z0-9\s-]', '', title.lower())
        slug = re.sub(r'\s+', '-', slug)
        return slug[:100] or 'post-' + str(int(time.time()))
    
    def extract_image(self, entry):
        """Extract image from feed entry"""
        # Try different methods to get image
        if hasattr(entry, 'media_content') and entry.media_content:
            return entry.media_content[0].get('url', '')
        if hasattr(entry, 'media_thumbnail') and entry.media_thumbnail:
            return entry.media_thumbnail[0].get('url', '')
        if hasattr(entry, 'enclosures') and entry.enclosures:
            for enc in entry.enclosures:
                if enc.get('type', '').startswith('image/'):
                    return enc.get('href', '')
        return ''
    
    def clean_text(self, text):
        """Clean HTML from text"""
        if not text:
            return ""
        # Remove HTML tags
        text = re.sub(r'<[^>]+>', '', text)
        # Clean entities
        text = text.replace('&nbsp;', ' ').replace('&amp;', '&')
        text = text.replace('&lt;', '<').replace('&gt;', '>')
        text = ' '.join(text.split())
        return text[:300]
    
    def fetch_articles(self, source, count=10):
        """Fetch articles from a source"""
        try:
            print(f"📡 Fetching from {source['name']}...")
            feed = feedparser.parse(source['url'])
            
            if not feed.entries:
                print(f"⚠️ No entries from {source['name']}")
                return []
            
            articles = []
            for entry in feed.entries[:count]:
                title = entry.get('title', 'Untitled')
                if not title or title == 'Untitled':
                    continue
                    
                link = entry.get('link', '')
                
                # Get content
                content = ''
                if hasattr(entry, 'summary'):
                    content = self.clean_text(entry.summary)
                elif hasattr(entry, 'description'):
                    content = self.clean_text(entry.description)
                
                # Skip if no content
                if not content:
                    content = f"Read the full article on {source['name']} about {title}"
                
                # Create article
                article = {
                    'title': title,
                    'content': content,
                    'excerpt': content[:200] + '...' if len(content) > 200 else content,
                    'url': link,
                    'image_url': self.extract_image(entry) or 'https://images.unsplash.com/photo-1588681664899-f142ff2dc9b1?w=400',
                    'source_name': source['name'],
                    'category': source['category']
                }
                articles.append(article)
            
            print(f"✅ Got {len(articles)} from {source['name']}")
            return articles
            
        except Exception as e:
            print(f"❌ Error from {source['name']}: {e}")
            return []
    
    def save_article(self, article):
        """Save article to database"""
        try:
            conn = get_db_connection()
            
            # Generate slug
            slug = self.generate_slug(article['title'])
            
            # Check if exists
            existing = conn.execute("SELECT id FROM posts WHERE slug = ?", (slug,)).fetchone()
            if existing:
                conn.close()
                return False
            
            # Save to database
            conn.execute('''
                INSERT INTO posts (title, slug, content, excerpt, image_url, source_url, 
                                 category, source_name, views)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                article['title'],
                slug,
                article['content'],
                article['excerpt'],
                article['image_url'],
                article['url'],
                article['category'],
                article['source_name'],
                random.randint(10, 100)
            ))
            
            conn.commit()
            conn.close()
            print(f"✅ Saved: {article['title'][:60]}...")
            return True
            
        except Exception as e:
            print(f"❌ Save error: {e}")
            return False
    
    def fetch_all_sources(self):
        """Fetch from all sources"""
        print("\n" + "="*60)
        print("🚀 FETCHING CONTENT FROM ALL SOURCES")
        print("="*60)
        
        total_saved = 0
        for source in FlaskConfig.NEWS_SOURCES:
            articles = self.fetch_articles(source, count=8)
            for article in articles:
                if self.save_article(article):
                    total_saved += 1
            time.sleep(2)  # Be nice
        
        print("="*60)
        print(f"🎯 FETCHED {total_saved} NEW ARTICLES!")
        print("="*60)
        return total_saved
    
    def start_auto_fetch(self):
        """Start automatic fetching"""
        def fetch_loop():
            # Initial wait
            time.sleep(10)
            # First fetch
            self.fetch_all_sources()
            
            # Regular updates
            while True:
                try:
                    time.sleep(FlaskConfig.UPDATE_INTERVAL_MINUTES * 60)
                    print(f"\n⏰ Running scheduled update...")
                    self.fetch_all_sources()
                except Exception as e:
                    print(f"❌ Update error: {e}")
                    time.sleep(300)
        
        if not self.is_fetching:
            self.is_fetching = True
            thread = threading.Thread(target=fetch_loop, daemon=True)
            thread.start()
            print("✅ Auto-fetch started")

# ============= FLASK APP =============
app = Flask(__name__)
app.config.from_object(FlaskConfig)

# Setup database
print("=" * 60)
print("🇿🇦 MZANSI INSIGHTS - READY TO GO!")
print("=" * 60)
setup_database()

# Initialize fetcher
fetcher = ContentFetcher()

# Start auto-fetch immediately
fetcher.start_auto_fetch()

# Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'admin_login'

class User(UserMixin):
    def __init__(self, id, username):
        self.id = id
        self.username = username

@login_manager.user_loader
def load_user(user_id):
    conn = get_db_connection()
    user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    if user:
        return User(user['id'], user['username'])
    return None

# ============= HELPER FUNCTIONS =============
def get_time_ago(date_str):
    """Get human readable time"""
    try:
        post_date = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
        diff = datetime.now() - post_date
        
        if diff.days > 365:
            years = diff.days // 365
            return f"{years} year{'s' if years > 1 else ''} ago"
        elif diff.days > 30:
            months = diff.days // 30
            return f"{months} month{'s' if months > 1 else ''} ago"
        elif diff.days > 0:
            return f"{diff.days} day{'s' if diff.days > 1 else ''} ago"
        elif diff.seconds > 3600:
            hours = diff.seconds // 3600
            return f"{hours} hour{'s' if hours > 1 else ''} ago"
        elif diff.seconds > 60:
            minutes = diff.seconds // 60
            return f"{minutes} minute{'s' if minutes > 1 else ''} ago"
        else:
            return "Just now"
    except:
        return "Recently"

# ============= ROUTES =============
@app.route('/')
def index():
    """Homepage"""
    try:
        conn = get_db_connection()
        
        # Get categories
        categories = ['news', 'business', 'technology', 'sports', 'entertainment']
        
        # Get latest posts
        posts = conn.execute('''
            SELECT * FROM posts 
            ORDER BY created_at DESC 
            LIMIT 20
        ''').fetchall()
        
        # Convert to list of dicts
        posts_list = []
        for post in posts:
            post_dict = dict(post)
            post_dict['formatted_date'] = get_time_ago(post_dict.get('created_at', ''))
            posts_list.append(post_dict)
        
        # Get trending (most viewed)
        trending = conn.execute('''
            SELECT * FROM posts 
            ORDER BY views DESC 
            LIMIT 6
        ''').fetchall()
        
        trending_list = []
        for post in trending:
            post_dict = dict(post)
            post_dict['formatted_date'] = get_time_ago(post_dict.get('created_at', ''))
            trending_list.append(post_dict)
        
        conn.close()
        
        # Check if we have posts
        has_posts = len(posts_list) > 0
        
        return render_template('index.html',
                             posts=posts_list,
                             trending_posts=trending_list,
                             categories=categories,
                             sources=FlaskConfig.NEWS_SOURCES,
                             config=FlaskConfig,
                             has_posts=has_posts,
                             now=datetime.now())
    except Exception as e:
        logger.error(f"Home error: {e}")
        return render_template('index.html',
                             posts=[],
                             trending_posts=[],
                             categories=[],
                             sources=FlaskConfig.NEWS_SOURCES,
                             config=FlaskConfig,
                             has_posts=False,
                             now=datetime.now())

@app.route('/category/<category>')
def category_page(category):
    """Category page"""
    try:
        conn = get_db_connection()
        
        # Get posts in category
        posts = conn.execute('''
            SELECT * FROM posts 
            WHERE category = ? 
            ORDER BY created_at DESC 
            LIMIT 30
        ''', (category,)).fetchall()
        
        posts_list = []
        for post in posts:
            post_dict = dict(post)
            post_dict['formatted_date'] = get_time_ago(post_dict.get('created_at', ''))
            posts_list.append(post_dict)
        
        conn.close()
        
        categories = ['news', 'business', 'technology', 'sports', 'entertainment']
        
        return render_template('category.html',
                             category=category,
                             posts=posts_list,
                             categories=categories,
                             config=FlaskConfig,
                             now=datetime.now())
    except Exception as e:
        logger.error(f"Category error: {e}")
        return render_template('category.html',
                             category=category,
                             posts=[],
                             categories=[],
                             config=FlaskConfig,
                             now=datetime.now())

@app.route('/post/<slug>')
def post_detail(slug):
    """Post detail page"""
    try:
        conn = get_db_connection()
        
        # Get post
        post = conn.execute("SELECT * FROM posts WHERE slug = ?", (slug,)).fetchone()
        if not post:
            conn.close()
            return render_template('404.html', config=FlaskConfig), 404
        
        post_dict = dict(post)
        post_dict['formatted_date'] = get_time_ago(post_dict.get('created_at', ''))
        
        # Increment views
        conn.execute("UPDATE posts SET views = views + 1 WHERE slug = ?", (slug,))
        conn.commit()
        
        # Get related posts
        related = conn.execute('''
            SELECT * FROM posts 
            WHERE category = ? AND slug != ? 
            ORDER BY RANDOM() 
            LIMIT 4
        ''', (post_dict['category'], slug)).fetchall()
        
        related_list = []
        for rel in related:
            rel_dict = dict(rel)
            rel_dict['formatted_date'] = get_time_ago(rel_dict.get('created_at', ''))
            related_list.append(rel_dict)
        
        conn.close()
        
        categories = ['news', 'business', 'technology', 'sports', 'entertainment']
        
        return render_template('post.html',
                             post=post_dict,
                             related_posts=related_list,
                             categories=categories,
                             config=FlaskConfig,
                             now=datetime.now())
    except Exception as e:
        logger.error(f"Post error: {e}")
        return render_template('404.html', config=FlaskConfig), 404

@app.route('/search')
def search():
    """Search page"""
    query = request.args.get('q', '')
    try:
        conn = get_db_connection()
        
        if query:
            posts = conn.execute('''
                SELECT * FROM posts 
                WHERE title LIKE ? OR content LIKE ? 
                ORDER BY created_at DESC 
                LIMIT 30
            ''', (f'%{query}%', f'%{query}%')).fetchall()
        else:
            posts = []
        
        posts_list = []
        for post in posts:
            post_dict = dict(post)
            post_dict['formatted_date'] = get_time_ago(post_dict.get('created_at', ''))
            posts_list.append(post_dict)
        
        conn.close()
        
        categories = ['news', 'business', 'technology', 'sports', 'entertainment']
        
        return render_template('search.html',
                             query=query,
                             posts=posts_list,
                             categories=categories,
                             config=FlaskConfig,
                             now=datetime.now())
    except Exception as e:
        logger.error(f"Search error: {e}")
        return render_template('search.html',
                             query=query,
                             posts=[],
                             categories=[],
                             config=FlaskConfig,
                             now=datetime.now())

# ============= REQUIRED PAGES =============
@app.route('/privacy')
def privacy():
    categories = ['news', 'business', 'technology', 'sports', 'entertainment']
    return render_template('privacy.html', config=FlaskConfig, categories=categories, now=datetime.now())

@app.route('/terms')
def terms():
    categories = ['news', 'business', 'technology', 'sports', 'entertainment']
    return render_template('terms.html', config=FlaskConfig, categories=categories, now=datetime.now())

@app.route('/contact')
def contact():
    categories = ['news', 'business', 'technology', 'sports', 'entertainment']
    return render_template('contact.html', config=FlaskConfig, categories=categories, now=datetime.now())

@app.route('/about')
def about():
    categories = ['news', 'business', 'technology', 'sports', 'entertainment']
    return render_template('about.html', config=FlaskConfig, categories=categories, now=datetime.now())

# ============= ADMIN =============
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        conn = get_db_connection()
        user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        conn.close()
        
        if user and check_password_hash(user['password_hash'], password):
            user_obj = User(user['id'], user['username'])
            login_user(user_obj)
            flash('Logged in!', 'success')
            return redirect('/admin/dashboard')
        else:
            flash('Wrong credentials', 'danger')
    
    return render_template('admin/login.html', config=FlaskConfig)

@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    conn = get_db_connection()
    
    stats = {
        'total_posts': conn.execute("SELECT COUNT(*) FROM posts").fetchone()[0],
        'total_views': conn.execute("SELECT SUM(views) FROM posts").fetchone()[0] or 0,
    }
    
    recent = conn.execute("SELECT * FROM posts ORDER BY created_at DESC LIMIT 10").fetchall()
    
    conn.close()
    
    return render_template('admin/dashboard.html',
                         stats=stats,
                         recent_posts=recent,
                         config=FlaskConfig)

@app.route('/admin/fetch-now')
@login_required
def admin_fetch_now():
    thread = threading.Thread(target=fetcher.fetch_all_sources, daemon=True)
    thread.start()
    flash('Fetch started!', 'info')
    return redirect('/admin/dashboard')

@app.route('/admin/logout')
@login_required
def admin_logout():
    logout_user()
    flash('Logged out', 'info')
    return redirect('/')

# ============= API =============
@app.route('/api/stats')
def api_stats():
    conn = get_db_connection()
    total = conn.execute("SELECT COUNT(*) FROM posts").fetchone()[0]
    conn.close()
    
    return jsonify({
        'posts': total,
        'status': 'online',
        'time': datetime.now().strftime('%H:%M:%S')
    })

# ============= ERROR HANDLERS =============
@app.errorhandler(404)
def not_found(e):
    return render_template('404.html', config=FlaskConfig), 404

@app.errorhandler(500)
def server_error(e):
    return render_template('500.html', config=FlaskConfig), 500

# ============= START APP =============
if __name__ == '__main__':
    print(f"🌐 Site: http://localhost:5000")
    print(f"🔑 Admin: http://localhost:5000/admin/login")
    print(f"📧 Contact: {FlaskConfig.CONTACT_EMAIL}")
    print(f"📱 Phone: {FlaskConfig.CONTACT_PHONE}")
    print("=" * 60)
    
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)
else:
    print("🚀 App started on Render!")
    print(f"📧 Your contact: {FlaskConfig.CONTACT_EMAIL}")