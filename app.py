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
import sys
import io
import logging
import json

# Fix Unicode encoding for Windows console
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
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
    
    # Contact Info
    CONTACT_EMAIL = 'sibiyan4444@gmail.com'
    CONTACT_PHONE = '+27 72 472 8166'
    PHYSICAL_ADDRESS = 'Johannesburg, South Africa'
    SITE_URL = os.environ.get('SITE_URL', 'https://mzansi-insights.onrender.com')
    
    # Content Update
    UPDATE_INTERVAL_MINUTES = 30
    INITIAL_FETCH_COUNT = 15
    
    # News Sources - ALL SOURCES
    NEWS_SOURCES = [
        {'name': 'News24', 'url': 'https://www.news24.com/feed', 'category': 'news', 'enabled': True, 'color': '#4361ee', 'icon': 'newspaper'},
        {'name': 'TimesLive', 'url': 'https://www.timeslive.co.za/feed/', 'category': 'news', 'enabled': True, 'color': '#7209b7', 'icon': 'newspaper'},
        {'name': 'IOL', 'url': 'https://www.iol.co.za/rss', 'category': 'news', 'enabled': True, 'color': '#e63946', 'icon': 'newspaper'},
        {'name': 'Moneyweb', 'url': 'https://www.moneyweb.co.za/feed/', 'category': 'business', 'enabled': True, 'color': '#1dd1a1', 'icon': 'chart-line'},
        {'name': 'BusinessTech', 'url': 'https://businesstech.co.za/news/feed/', 'category': 'business', 'enabled': True, 'color': '#3742fa', 'icon': 'laptop-code'},
        {'name': 'Daily Maverick', 'url': 'https://www.dailymaverick.co.za/feed/', 'category': 'news', 'enabled': True, 'color': '#f77f00', 'icon': 'newspaper'},
        {'name': 'MyBroadband', 'url': 'https://mybroadband.co.za/news/feed', 'category': 'technology', 'enabled': True, 'color': '#9b59b6', 'icon': 'wifi'},
        {'name': 'TechCentral', 'url': 'https://techcentral.co.za/feed/', 'category': 'technology', 'enabled': True, 'color': '#3498db', 'icon': 'microchip'},
        {'name': 'Sport24', 'url': 'https://www.sport24.co.za/feed', 'category': 'sports', 'enabled': True, 'color': '#2ecc71', 'icon': 'running'},
        {'name': 'The Citizen', 'url': 'https://www.citizen.co.za/feed/', 'category': 'news', 'enabled': True, 'color': '#d62828', 'icon': 'newspaper'},
    ]

# Category definitions - MATCH YOUR HTML
CATEGORY_DEFINITIONS = {
    'news': {'name': 'News', 'slug': 'news', 'description': 'Breaking news and current events', 'icon': 'newspaper', 'color': '#4361ee', 'keywords': ['news', 'breaking', 'update', 'latest', 'current', 'report']},
    'business': {'name': 'Business', 'slug': 'business', 'description': 'Business and economic news', 'icon': 'chart-line', 'color': '#7209b7', 'keywords': ['business', 'economy', 'market', 'finance', 'trade', 'investment', 'company']},
    'technology': {'name': 'Technology', 'slug': 'technology', 'description': 'Tech news and innovation', 'icon': 'laptop-code', 'color': '#3498db', 'keywords': ['tech', 'technology', 'digital', 'software', 'internet', 'app', 'cyber']},
    'sports': {'name': 'Sports', 'slug': 'sports', 'description': 'Sports news and updates', 'icon': 'running', 'color': '#2ecc71', 'keywords': ['sport', 'rugby', 'soccer', 'cricket', 'football', 'game', 'match', 'player']},
    'entertainment': {'name': 'Entertainment', 'slug': 'entertainment', 'description': 'Entertainment news', 'icon': 'film', 'color': '#ef476f', 'keywords': ['entertainment', 'movie', 'music', 'celebrity', 'show', 'culture', 'film']},
    'jobs': {'name': 'Jobs', 'slug': 'jobs', 'description': 'Employment opportunities', 'icon': 'briefcase', 'color': '#06d6a0', 'keywords': ['job', 'career', 'employment', 'vacancy', 'work', 'hiring']},
    'grants': {'name': 'Grants', 'slug': 'grants', 'description': 'Grants and SASSA information', 'icon': 'hand-holding-usd', 'color': '#ff9e00', 'keywords': ['grant', 'sassa', 'funding', 'financial aid', 'bursary', 'scholarship']},
    'government': {'name': 'Government', 'slug': 'government', 'description': 'Government updates', 'icon': 'landmark', 'color': '#2c3e50', 'keywords': ['government', 'ministry', 'department', 'official', 'policy']},
    'health': {'name': 'Health', 'slug': 'health', 'description': 'Health and wellness', 'icon': 'heartbeat', 'color': '#e74c3c', 'keywords': ['health', 'medical', 'hospital', 'doctor', 'wellness']},
    'education': {'name': 'Education', 'slug': 'education', 'description': 'Education news', 'icon': 'graduation-cap', 'color': '#9b59b6', 'keywords': ['education', 'school', 'university', 'learn', 'student']},
}

# ============= DATABASE =============
def get_db_path():
    """Get database path - FIXED for Render persistence"""
    # Try multiple locations
    locations = [
        '/var/data/posts.db',  # Render persistent disk
        '/tmp/persistent_data/posts.db',
        os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'posts.db'),
        'posts.db'
    ]
    
    for db_path in locations:
        db_dir = os.path.dirname(db_path)
        try:
            if not os.path.exists(db_dir):
                os.makedirs(db_dir, exist_ok=True)
            return db_path
        except:
            continue
    
    return 'posts.db'  # Final fallback

def setup_database():
    print("=" * 60)
    print("📄 SETTING UP DATABASE...")
    print("=" * 60)
    
    db_path = get_db_path()
    print(f"📊 Database path: {db_path}")
    
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    # Users table
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # Categories table
    c.execute('''CREATE TABLE IF NOT EXISTS categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        slug TEXT UNIQUE NOT NULL,
        description TEXT,
        icon TEXT,
        color TEXT
    )''')
    
    # Posts table
    c.execute('''CREATE TABLE IF NOT EXISTS posts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        slug TEXT UNIQUE NOT NULL,
        content TEXT NOT NULL,
        excerpt TEXT,
        image_url TEXT,
        source_url TEXT,
        category_id INTEGER,
        category TEXT DEFAULT 'news',
        author TEXT DEFAULT 'Mzansi Insights',
        views INTEGER DEFAULT 0,
        source_name TEXT,
        is_published BOOLEAN DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (category_id) REFERENCES categories(id)
    )''')
    
    # Indexes
    c.execute('CREATE INDEX IF NOT EXISTS idx_posts_slug ON posts(slug)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_posts_category ON posts(category_id)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_posts_created ON posts(created_at)')
    
    # Admin user
    c.execute("SELECT COUNT(*) FROM users WHERE username = 'admin'")
    if c.fetchone()[0] == 0:
        pwd_hash = generate_password_hash(FlaskConfig.ADMIN_PASSWORD)
        c.execute("INSERT INTO users (username, password_hash) VALUES (?, ?)", ('admin', pwd_hash))
        print("✅ Admin user created")
    
    # Categories - ALL categories from HTML
    for slug, cat_data in CATEGORY_DEFINITIONS.items():
        c.execute("SELECT COUNT(*) FROM categories WHERE slug = ?", (slug,))
        if c.fetchone()[0] == 0:
            c.execute("INSERT INTO categories (name, slug, description, icon, color) VALUES (?, ?, ?, ?, ?)",
                     (cat_data['name'], cat_data['slug'], cat_data['description'], cat_data['icon'], cat_data['color']))
            print(f"✅ Category created: {cat_data['name']}")
    
    # Check existing posts
    c.execute("SELECT COUNT(*) FROM posts")
    post_count = c.fetchone()[0]
    
    # Add sample posts if empty
    if post_count == 0:
        print("📝 Adding sample posts...")
        sample_posts = [
            ("Breaking: Major Economic Announcement Expected", "The South African government is set to make a major economic announcement this afternoon.", "news", "News24", "https://images.unsplash.com/photo-1588681664899-f142ff2dc9b1?w=800"),
            ("Tech Giant Announces 1000 New Jobs in Cape Town", "A major technology company is expanding its South African operations.", "business", "BusinessTech", "https://images.unsplash.com/photo-1497366754035-f200968a6e72?w=800"),
            ("Springboks Prepare for Championship Defense", "The national rugby team begins training for the upcoming season.", "sports", "Sport24", "https://images.unsplash.com/photo-1546519638-68e109498ffc?w=800"),
            ("New Grant Applications Open for Students", "Applications for the 2024 student grant program are now open.", "grants", "IOL", "https://images.unsplash.com/photo-1523050854058-8df90110c9f1?w=800"),
            ("Government Announces Infrastructure Projects", "Billions allocated for new infrastructure development.", "government", "TimesLive", "https://images.unsplash.com/photo-1486406146926-c627a92ad1ab?w=800"),
        ]
        
        for title, content, category, source, image in sample_posts:
            slug = re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')
            excerpt = content[:150] + '...' if len(content) > 150 else content
            
            # Get category ID
            c.execute("SELECT id FROM categories WHERE slug = ?", (category,))
            category_row = c.fetchone()
            category_id = category_row[0] if category_row else 1
            
            c.execute('''INSERT INTO posts 
                (title, slug, content, excerpt, image_url, source_url, 
                 category_id, category, source_name, views, is_published)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)''',
                (title, slug, content, excerpt, image, '#', 
                 category_id, category, source, random.randint(50, 500)))
        
        print("✅ Sample posts added")
    
    conn.commit()
    conn.close()
    
    # Verify
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM posts")
    post_count = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM categories")
    cat_count = c.fetchone()[0]
    conn.close()
    
    print(f"✅ Database setup complete - {post_count} posts, {cat_count} categories")
    print("=" * 60)
    
    return post_count == 0

def get_db_connection():
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

# ============= CONTENT FETCHER =============
class ContentFetcher:
    def __init__(self):
        self.is_fetching = False
        
    def generate_slug(self, title):
        slug = re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')
        return slug[:100] or 'post-' + str(int(time.time()))
    
    def extract_image(self, entry):
        if hasattr(entry, 'media_content') and entry.media_content:
            return entry.media_content[0].get('url', '')
        if hasattr(entry, 'media_thumbnail') and entry.media_thumbnail:
            return entry.media_thumbnail[0].get('url', '')
        if hasattr(entry, 'enclosures') and entry.enclosures:
            for enc in entry.enclosures:
                if enc.get('type', '').startswith('image/'):
                    return enc.get('href', '')
        return 'https://images.unsplash.com/photo-1588681664899-f142ff2dc9b1?w=800'
    
    def clean_text(self, text):
        if not text:
            return ""
        text = re.sub(r'<[^>]+>', '', text)
        text = text.replace('&nbsp;', ' ').replace('&amp;', '&')
        text = ' '.join(text.split())
        return text[:500]
    
    def fetch_and_save(self):
        """Simple fetch that ensures we have data"""
        try:
            print("⚡ FETCHING DATA NOW...")
            conn = get_db_connection()
            
            # Quick fetch from News24 only for speed
            feed = feedparser.parse('https://www.news24.com/feed')
            
            saved = 0
            if feed.entries:
                for entry in feed.entries[:10]:  # Just 10 articles for speed
                    title = entry.get('title', '')
                    if not title:
                        continue
                    
                    # Check if already exists
                    c = conn.cursor()
                    c.execute("SELECT id FROM posts WHERE title = ?", (title,))
                    if c.fetchone():
                        continue
                    
                    # Prepare article
                    content = self.clean_text(entry.get('summary', entry.get('description', '')))
                    excerpt = content[:200] + '...' if len(content) > 200 else content
                    slug = self.generate_slug(title)
                    image = self.extract_image(entry)
                    
                    # Insert
                    c.execute('''INSERT INTO posts 
                        (title, slug, content, excerpt, image_url, source_url, 
                         category, source_name, views, is_published)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)''',
                        (title, slug, content, excerpt, image, 
                         entry.get('link', '#'), 'news', 'News24', 
                         random.randint(50, 500)))
                    
                    saved += 1
                    print(f"✅ Saved: {title[:50]}...")
            
            conn.commit()
            conn.close()
            print(f"🎯 FETCHED {saved} NEW ARTICLES!")
            return saved
            
        except Exception as e:
            print(f"❌ Fetch error: {e}")
            return 0

# ============= FLASK APP =============
app = Flask(__name__)
app.config.from_object(FlaskConfig)

print("=" * 60)
print("🇿🇦 MZANSI INSIGHTS - STARTING...")
print("=" * 60)

# Setup database FIRST
db_is_empty = setup_database()

# Initialize fetcher and fetch immediately
fetcher = ContentFetcher()

# DO IMMEDIATE FETCH - BLOCKING
if db_is_empty:
    print("🚀 FETCHING DATA IMMEDIATELY...")
    fetched = fetcher.fetch_and_save()
    print(f"✅ Initial fetch complete: {fetched} articles")
else:
    print("📊 Database already has data")
    
    # Still fetch fresh data in background
    print("🔄 Fetching fresh data in background...")
    threading.Thread(target=fetcher.fetch_and_save, daemon=True).start()

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
    return User(user['id'], user['username']) if user else None

def get_time_ago(date_str):
    try:
        post_date = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
        diff = datetime.now() - post_date
        
        if diff.days > 365:
            return f"{diff.days // 365} year{'s' if diff.days // 365 > 1 else ''} ago"
        elif diff.days > 30:
            return f"{diff.days // 30} month{'s' if diff.days // 30 > 1 else ''} ago"
        elif diff.days > 0:
            return f"{diff.days} day{'s' if diff.days > 1 else ''} ago"
        elif diff.seconds > 3600:
            return f"{diff.seconds // 3600} hour{'s' if diff.seconds // 3600 > 1 else ''} ago"
        elif diff.seconds > 60:
            return f"{diff.seconds // 60} minute{'s' if diff.seconds // 60 > 1 else ''} ago"
        return "Just now"
    except:
        return "Recently"

def prepare_post(post_row):
    """Prepare post data for template"""
    post = dict(post_row)
    post['formatted_date'] = get_time_ago(post.get('created_at', ''))
    
    # Get category info
    conn = get_db_connection()
    category = conn.execute("SELECT * FROM categories WHERE id = ?", (post.get('category_id', 1),)).fetchone()
    conn.close()
    
    if category:
        post['category_ref'] = {
            'name': category['name'],
            'slug': category['slug'],
            'icon': category['icon'],
            'color': category['color']
        }
    else:
        # Fallback
        cat_slug = post.get('category', 'news')
        cat_data = CATEGORY_DEFINITIONS.get(cat_slug, CATEGORY_DEFINITIONS['news'])
        post['category_ref'] = {
            'name': cat_data['name'],
            'slug': cat_data['slug'],
            'icon': cat_data['icon'],
            'color': cat_data['color']
        }
    
    return post

# ============= ROUTES =============
@app.route('/')
def index():
    """Home page - ALWAYS SHOWS DATA"""
    try:
        conn = get_db_connection()
        
        # Get latest posts
        posts_raw = conn.execute(
            "SELECT * FROM posts WHERE is_published = 1 ORDER BY created_at DESC LIMIT 20"
        ).fetchall()
        posts = [prepare_post(row) for row in posts_raw]
        
        # Get trending posts
        trending_raw = conn.execute(
            "SELECT * FROM posts WHERE is_published = 1 ORDER BY views DESC LIMIT 6"
        ).fetchall()
        trending_posts = [prepare_post(row) for row in trending_raw]
        
        # Get categories
        categories = []
        cat_rows = conn.execute("SELECT * FROM categories").fetchall()
        for cat in cat_rows:
            cat_dict = dict(cat)
            post_count = conn.execute(
                "SELECT COUNT(*) FROM posts WHERE category_id = ?", 
                (cat_dict['id'],)
            ).fetchone()[0]
            cat_dict['post_count'] = post_count
            categories.append(cat_dict)
        
        # Get sources
        sources = []
        for source in FlaskConfig.NEWS_SOURCES:
            article_count = conn.execute(
                "SELECT COUNT(*) FROM posts WHERE source_name = ?", 
                (source['name'],)
            ).fetchone()[0]
            sources.append({
                'name': source['name'],
                'url': source['url'],
                'category': source['category'],
                'enabled': source['enabled'],
                'color': source['color'],
                'icon': source['icon'],
                'article_count': article_count
            })
        
        conn.close()
        
        has_posts = len(posts) > 0
        
        return render_template('index.html',
                             posts=posts,
                             trending_posts=trending_posts,
                             categories=categories,
                             sources=sources,
                             config=FlaskConfig,
                             has_posts=has_posts,
                             now=datetime.now())
                             
    except Exception as e:
        print(f"❌ Home error: {e}")
        # Fallback with sample data
        categories = []
        for slug, cat_data in CATEGORY_DEFINITIONS.items():
            categories.append({
                'name': cat_data['name'],
                'slug': cat_data['slug'],
                'description': cat_data['description'],
                'icon': cat_data['icon'],
                'color': cat_data['color'],
                'post_count': 0
            })
        
        return render_template('index.html',
                             posts=[],
                             trending_posts=[],
                             categories=categories,
                             sources=FlaskConfig.NEWS_SOURCES,
                             config=FlaskConfig,
                             has_posts=False,
                             now=datetime.now())

@app.route('/category/<category_slug>')
def category_page(category_slug):
    try:
        conn = get_db_connection()
        
        # Get category
        category = conn.execute(
            "SELECT * FROM categories WHERE slug = ?", 
            (category_slug,)
        ).fetchone()
        
        if not category:
            # Create dummy category
            cat_data = CATEGORY_DEFINITIONS.get(category_slug, CATEGORY_DEFINITIONS['news'])
            category = {
                'id': 0,
                'name': cat_data['name'],
                'slug': cat_data['slug'],
                'description': cat_data['description'],
                'icon': cat_data['icon'],
                'color': cat_data['color']
            }
        else:
            category = dict(category)
        
        # Get posts for this category
        if category['id'] > 0:
            posts_raw = conn.execute(
                "SELECT * FROM posts WHERE category_id = ? AND is_published = 1 ORDER BY created_at DESC LIMIT 30",
                (category['id'],)
            ).fetchall()
        else:
            posts_raw = []
        
        posts = [prepare_post(row) for row in posts_raw]
        
        # Get all categories for sidebar
        categories = []
        cat_rows = conn.execute("SELECT * FROM categories").fetchall()
        for cat in cat_rows:
            cat_dict = dict(cat)
            post_count = conn.execute(
                "SELECT COUNT(*) FROM posts WHERE category_id = ?", 
                (cat_dict['id'],)
            ).fetchone()[0]
            cat_dict['post_count'] = post_count
            categories.append(cat_dict)
        
        conn.close()
        
        return render_template('category.html',
                             category=category,
                             posts=posts,
                             categories=categories,
                             config=FlaskConfig,
                             now=datetime.now())
                             
    except Exception as e:
        print(f"Category error: {e}")
        return render_template('category.html',
                             category={'name': category_slug.title(), 'slug': category_slug},
                             posts=[],
                             categories=[],
                             config=FlaskConfig,
                             now=datetime.now())

@app.route('/post/<slug>')
def post_detail(slug):
    try:
        conn = get_db_connection()
        
        post_raw = conn.execute("SELECT * FROM posts WHERE slug = ?", (slug,)).fetchone()
        if not post_raw:
            conn.close()
            return render_template('404.html', config=FlaskConfig), 404
        
        post = prepare_post(post_raw)
        
        # Update views
        conn.execute("UPDATE posts SET views = views + 1 WHERE slug = ?", (slug,))
        conn.commit()
        
        # Get related posts
        related_raw = conn.execute(
            "SELECT * FROM posts WHERE category_id = ? AND slug != ? AND is_published = 1 ORDER BY RANDOM() LIMIT 4",
            (post['category_id'], slug)
        ).fetchall()
        related_posts = [prepare_post(row) for row in related_raw]
        
        # Get categories
        categories = []
        for cat in conn.execute("SELECT * FROM categories").fetchall():
            categories.append(dict(cat))
        
        conn.close()
        
        return render_template('post.html',
                             post=post,
                             related_posts=related_posts,
                             categories=categories,
                             config=FlaskConfig,
                             now=datetime.now())
                             
    except Exception as e:
        print(f"Post error: {e}")
        return render_template('404.html', config=FlaskConfig), 404

@app.route('/search')
def search():
    query = request.args.get('q', '')
    try:
        conn = get_db_connection()
        
        if query:
            posts_raw = conn.execute(
                "SELECT * FROM posts WHERE (title LIKE ? OR content LIKE ?) AND is_published = 1 ORDER BY created_at DESC LIMIT 30",
                (f'%{query}%', f'%{query}%')
            ).fetchall()
            posts = [prepare_post(row) for row in posts_raw]
        else:
            posts = []
        
        # Get categories
        categories = []
        for cat in conn.execute("SELECT * FROM categories").fetchall():
            categories.append(dict(cat))
        
        conn.close()
        
        return render_template('search.html',
                             query=query,
                             posts=posts,
                             categories=categories,
                             config=FlaskConfig,
                             now=datetime.now())
                             
    except Exception as e:
        print(f"Search error: {e}")
        return render_template('search.html',
                             query=query,
                             posts=[],
                             categories=[],
                             config=FlaskConfig,
                             now=datetime.now())

@app.route('/sources')
def sources():
    try:
        conn = get_db_connection()
        
        # Get sources with counts
        sources_list = []
        for source in FlaskConfig.NEWS_SOURCES:
            article_count = conn.execute(
                "SELECT COUNT(*) FROM posts WHERE source_name = ?", 
                (source['name'],)
            ).fetchone()[0]
            sources_list.append({
                'name': source['name'],
                'url': source['url'],
                'category': source['category'],
                'color': source['color'],
                'icon': source['icon'],
                'article_count': article_count
            })
        
        # Get categories
        categories = []
        for cat in conn.execute("SELECT * FROM categories").fetchall():
            categories.append(dict(cat))
        
        conn.close()
        
        return render_template('sources.html',
                             sources=sources_list,
                             categories=categories,
                             config=FlaskConfig,
                             now=datetime.now())
                             
    except Exception as e:
        print(f"Sources error: {e}")
        return render_template('sources.html',
                             sources=FlaskConfig.NEWS_SOURCES,
                             categories=[],
                             config=FlaskConfig,
                             now=datetime.now())

@app.route('/api/live-news')
def live_news():
    try:
        conn = get_db_connection()
        posts_raw = conn.execute(
            "SELECT p.*, c.color, c.name as category_name FROM posts p LEFT JOIN categories c ON p.category_id = c.id WHERE p.is_published = 1 ORDER BY p.created_at DESC LIMIT 5"
        ).fetchall()
        conn.close()
        
        articles = []
        for post in posts_raw:
            post_dict = dict(post)
            articles.append({
                'title': post_dict['title'][:80] + '...' if len(post_dict['title']) > 80 else post_dict['title'],
                'category': post_dict.get('category_name', 'News'),
                'color': post_dict.get('color', '#4361ee')
            })
        
        return jsonify({'status': 'success', 'articles': articles})
        
    except Exception as e:
        return jsonify({'status': 'error', 'articles': []})

# Static pages
@app.route('/privacy')
def privacy():
    try:
        conn = get_db_connection()
        categories = [dict(cat) for cat in conn.execute("SELECT * FROM categories").fetchall()]
        conn.close()
    except:
        categories = []
    return render_template('privacy.html', config=FlaskConfig, categories=categories, now=datetime.now())

@app.route('/terms')
def terms():
    try:
        conn = get_db_connection()
        categories = [dict(cat) for cat in conn.execute("SELECT * FROM categories").fetchall()]
        conn.close()
    except:
        categories = []
    return render_template('terms.html', config=FlaskConfig, categories=categories, now=datetime.now())

@app.route('/contact')
def contact():
    try:
        conn = get_db_connection()
        categories = [dict(cat) for cat in conn.execute("SELECT * FROM categories").fetchall()]
        conn.close()
    except:
        categories = []
    return render_template('contact.html', config=FlaskConfig, categories=categories, now=datetime.now())

@app.route('/about')
def about():
    try:
        conn = get_db_connection()
        categories = [dict(cat) for cat in conn.execute("SELECT * FROM categories").fetchall()]
        conn.close()
    except:
        categories = []
    return render_template('about.html', config=FlaskConfig, categories=categories, now=datetime.now())

@app.route('/disclaimer')
def disclaimer():
    try:
        conn = get_db_connection()
        categories = [dict(cat) for cat in conn.execute("SELECT * FROM categories").fetchall()]
        conn.close()
    except:
        categories = []
    return render_template('disclaimer.html', config=FlaskConfig, categories=categories, now=datetime.now())

@app.route('/sitemap')
def sitemap():
    try:
        conn = get_db_connection()
        categories = [dict(cat) for cat in conn.execute("SELECT * FROM categories").fetchall()]
        conn.close()
    except:
        categories = []
    return render_template('sitemap.html', config=FlaskConfig, categories=categories, now=datetime.now())

# Handle missing categories from HTML
@app.route('/category/jobs')
def jobs_category():
    return redirect('/category/business')

@app.route('/category/grants')
def grants_category():
    return redirect('/category/news')

@app.route('/category/health')
def health_category():
    return redirect('/category/news')

@app.route('/category/government')
def government_category():
    return redirect('/category/news')

@app.route('/category/education')
def education_category():
    return redirect('/category/news')

# Admin routes
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
            flash('Logged in successfully!', 'success')
            return redirect('/admin/dashboard')
        else:
            flash('Invalid credentials', 'danger')
    
    return render_template('admin/login.html', config=FlaskConfig)

@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    conn = get_db_connection()
    
    stats = {
        'total_posts': conn.execute("SELECT COUNT(*) FROM posts").fetchone()[0],
        'published_posts': conn.execute("SELECT COUNT(*) FROM posts WHERE is_published = 1").fetchone()[0],
        'total_views': conn.execute("SELECT SUM(views) FROM posts").fetchone()[0] or 0,
        'categories': conn.execute("SELECT COUNT(*) FROM categories").fetchone()[0],
        'sources': len(FlaskConfig.NEWS_SOURCES),
        'fetching_status': 'Active'
    }
    
    recent = conn.execute("SELECT * FROM posts ORDER BY created_at DESC LIMIT 10").fetchall()
    conn.close()
    
    return render_template('admin/dashboard.html', stats=stats, recent_posts=recent, config=FlaskConfig)

@app.route('/admin/fetch-now')
@login_required
def admin_fetch_now():
    threading.Thread(target=fetcher.fetch_and_save, daemon=True).start()
    flash('Content fetch started in background!', 'info')
    return redirect('/admin/dashboard')

@app.route('/admin/logout')
@login_required
def admin_logout():
    logout_user()
    flash('Logged out successfully', 'info')
    return redirect('/')

@app.route('/api/stats')
def api_stats():
    try:
        conn = get_db_connection()
        
        stats = {
            'posts': conn.execute("SELECT COUNT(*) FROM posts WHERE is_published = 1").fetchone()[0],
            'total_views': conn.execute("SELECT SUM(views) FROM posts").fetchone()[0] or 0,
            'status': 'online',
            'sources_count': len(FlaskConfig.NEWS_SOURCES),
            'time': datetime.now().strftime('%H:%M:%S')
        }
        
        conn.close()
        return jsonify(stats)
        
    except Exception as e:
        return jsonify({'error': str(e), 'status': 'error'}), 500

# Debug route
@app.route('/debug')
def debug():
    conn = get_db_connection()
    
    # Get counts
    total_posts = conn.execute("SELECT COUNT(*) FROM posts").fetchone()[0]
    published_posts = conn.execute("SELECT COUNT(*) FROM posts WHERE is_published = 1").fetchone()[0]
    categories = conn.execute("SELECT COUNT(*) FROM categories").fetchone()[0]
    
    # Get latest posts
    latest_posts = conn.execute("SELECT title, created_at, source_name FROM posts ORDER BY created_at DESC LIMIT 5").fetchall()
    
    conn.close()
    
    return jsonify({
        'status': 'ok',
        'database': get_db_path(),
        'posts': {
            'total': total_posts,
            'published': published_posts,
            'latest': [dict(post) for post in latest_posts]
        },
        'categories': categories,
        'sources': len(FlaskConfig.NEWS_SOURCES),
        'fetching': fetcher.is_fetching
    })

@app.errorhandler(404)
def not_found(e):
    return render_template('404.html', config=FlaskConfig), 404

@app.errorhandler(500)
def server_error(e):
    print(f"❌ 500 error: {e}")
    return render_template('500.html', config=FlaskConfig), 500

# Start background fetcher
def start_background_fetcher():
    """Start periodic fetching"""
    def fetch_loop():
        while True:
            try:
                time.sleep(FlaskConfig.UPDATE_INTERVAL_MINUTES * 60)
                print(f"\n🔄 Running scheduled fetch...")
                fetcher.fetch_and_save()
            except Exception as e:
                print(f"❌ Fetch error in loop: {e}")
                time.sleep(300)  # Wait 5 minutes on error
    
    fetcher.is_fetching = True
    thread = threading.Thread(target=fetch_loop, daemon=True)
    thread.start()
    print("✅ Background fetcher started")

# Start the background fetcher
start_background_fetcher()

# ============= START APP =============
if __name__ == '__main__':
    print(f"🌐 Site: http://localhost:5000")
    print(f"🔐 Admin: http://localhost:5000/admin/login")
    print(f"📧 Contact: {FlaskConfig.CONTACT_EMAIL}")
    print(f"📱 Phone: {FlaskConfig.CONTACT_PHONE}")
    print(f"📊 Sources: {len(FlaskConfig.NEWS_SOURCES)}")
    print("=" * 60)
    
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port, threaded=True)
else:
    print("🚀 App started on Render!")
    print(f"📧 Contact: {FlaskConfig.CONTACT_EMAIL}")
    print(f"📊 Tracking {len(FlaskConfig.NEWS_SOURCES)} news sources")
    print(f"⏰ Updates every {FlaskConfig.UPDATE_INTERVAL_MINUTES} minutes")