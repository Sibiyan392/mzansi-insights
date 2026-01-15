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
import atexit

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
    
    # Content Update - INCREASED for deployment
    UPDATE_INTERVAL_MINUTES = 30
    INITIAL_FETCH_COUNT = 15  # More articles on first fetch
    
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

# Category definitions
CATEGORY_DEFINITIONS = {
    'news': {'name': 'News', 'slug': 'news', 'description': 'Breaking news and current events', 'icon': 'newspaper', 'color': '#4361ee', 'keywords': ['news', 'breaking', 'update', 'latest', 'current', 'report']},
    'business': {'name': 'Business', 'slug': 'business', 'description': 'Business and economic news', 'icon': 'chart-line', 'color': '#7209b7', 'keywords': ['business', 'economy', 'market', 'finance', 'trade', 'investment', 'company']},
    'technology': {'name': 'Technology', 'slug': 'technology', 'description': 'Tech news and innovation', 'icon': 'laptop-code', 'color': '#3498db', 'keywords': ['tech', 'technology', 'digital', 'software', 'internet', 'app', 'cyber']},
    'sports': {'name': 'Sports', 'slug': 'sports', 'description': 'Sports news and updates', 'icon': 'running', 'color': '#2ecc71', 'keywords': ['sport', 'rugby', 'soccer', 'cricket', 'football', 'game', 'match', 'player']},
    'entertainment': {'name': 'Entertainment', 'slug': 'entertainment', 'description': 'Entertainment news', 'icon': 'film', 'color': '#ef476f', 'keywords': ['entertainment', 'movie', 'music', 'celebrity', 'show', 'culture', 'film']},
}

# ============= DATABASE =============
def get_db_path():
    """Get database path - FIXED for Render persistence"""
    # Always use persistent location
    persistent_locations = [
        '/var/data/posts.db',                # Render persistent disk
        '/tmp/persistent_data/posts.db',     # Custom persistent directory
        os.path.join(os.path.dirname(os.path.abspath(__file__)), 'persistent_data', 'posts.db'),  # App directory
    ]
    
    # Try each location
    for db_path in persistent_locations:
        db_dir = os.path.dirname(db_path)
        try:
            if not os.path.exists(db_dir):
                os.makedirs(db_dir, exist_ok=True)
            return db_path
        except:
            continue
    
    # Fallback
    return 'data/posts.db'

def setup_database():
    print("=" * 60)
    print("📄 SETTING UP DATABASE...")
    print("=" * 60)
    
    db_path = get_db_path()
    print(f"📊 Database path: {db_path}")
    
    # Ensure directory exists
    db_dir = os.path.dirname(db_path)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)
        print(f"📁 Created directory: {db_dir}")
    
    # Connect and setup
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
    c.execute('CREATE INDEX IF NOT EXISTS idx_posts_published ON posts(is_published)')
    
    # Admin user
    c.execute("SELECT COUNT(*) FROM users WHERE username = 'admin'")
    if c.fetchone()[0] == 0:
        pwd_hash = generate_password_hash(FlaskConfig.ADMIN_PASSWORD)
        c.execute("INSERT INTO users (username, password_hash) VALUES (?, ?)", ('admin', pwd_hash))
        print("✅ Admin user created")
    
    # Categories
    for slug, cat_data in CATEGORY_DEFINITIONS.items():
        c.execute("SELECT COUNT(*) FROM categories WHERE slug = ?", (slug,))
        if c.fetchone()[0] == 0:
            c.execute("INSERT INTO categories (name, slug, description, icon, color) VALUES (?, ?, ?, ?, ?)",
                     (cat_data['name'], cat_data['slug'], cat_data['description'], cat_data['icon'], cat_data['color']))
            print(f"✅ Category created: {cat_data['name']}")
    
    # Check existing posts
    c.execute("SELECT COUNT(*) FROM posts")
    post_count = c.fetchone()[0]
    
    conn.commit()
    conn.close()
    
    print(f"✅ Database setup complete - {post_count} existing posts")
    print("=" * 60)
    
    return post_count == 0  # Return True if empty

def get_db_connection():
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def detect_category(title, content, source_category='news'):
    title_lower = title.lower()
    content_lower = content.lower() if content else ''
    
    category_scores = {}
    for slug, cat_data in CATEGORY_DEFINITIONS.items():
        score = 0
        for keyword in cat_data['keywords']:
            if keyword in title_lower:
                score += 3
            if keyword in content_lower:
                score += 1
        category_scores[slug] = score
    
    if source_category in category_scores:
        category_scores[source_category] += 2
    
    best_category = max(category_scores.items(), key=lambda x: x[1])
    return best_category[0] if best_category[1] >= 2 else source_category

# ============= CONTENT FETCHER =============
class ContentFetcher:
    def __init__(self):
        self.is_fetching = False
        self.first_fetch_done = False
        
    def generate_slug(self, title):
        slug = re.sub(r'[^a-zA-Z0-9\s-]', '', title.lower())
        slug = re.sub(r'\s+', '-', slug)
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
        if hasattr(entry, 'content'):
            content = entry.content[0].value if entry.content else ''
            img_match = re.search(r'<img[^>]+src="([^"]+)"', content)
            if img_match:
                return img_match.group(1)
        return 'https://images.unsplash.com/photo-1588681664899-f142ff2dc9b1?w=400'
    
    def clean_text(self, text):
        if not text:
            return ""
        text = re.sub(r'<[^>]+>', '', text)
        text = text.replace('&nbsp;', ' ').replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
        text = text.replace('&quot;', '"').replace('&#39;', "'")
        text = ' '.join(text.split())
        return text[:500]
    
    def fetch_articles(self, source, count=10):
        try:
            print(f"📡 Fetching from {source['name']}...")
            
            # Add timeout for faster failure
            feed = feedparser.parse(source['url'])
            
            if not feed.entries:
                print(f"⚠️ No entries from {source['name']}")
                return []
            
            articles = []
            for entry in feed.entries[:count]:
                title = entry.get('title', 'Untitled')
                if not title or title == 'Untitled' or len(title) < 10:
                    continue
                    
                content = ''
                if hasattr(entry, 'summary'):
                    content = self.clean_text(entry.summary)
                elif hasattr(entry, 'description'):
                    content = self.clean_text(entry.description)
                elif hasattr(entry, 'content'):
                    content = self.clean_text(entry.content[0].value if entry.content else '')
                
                if not content or len(content) < 50:
                    content = f"Read more about {title} on {source['name']}. Click to view the full article."
                
                article = {
                    'title': title,
                    'content': content,
                    'excerpt': content[:200] + '...' if len(content) > 200 else content,
                    'url': entry.get('link', ''),
                    'image_url': self.extract_image(entry),
                    'source_name': source['name'],
                    'source_category': source['category']
                }
                articles.append(article)
            
            print(f"✅ Got {len(articles)} from {source['name']}")
            return articles
            
        except Exception as e:
            print(f"❌ Error from {source['name']}: {e}")
            return []
    
    def save_article(self, article):
        try:
            conn = get_db_connection()
            slug = self.generate_slug(article['title'])
            
            # Check if exists (by slug or title)
            existing = conn.execute(
                "SELECT id FROM posts WHERE slug = ? OR title = ?", 
                (slug, article['title'])
            ).fetchone()
            
            if existing:
                conn.close()
                return False
            
            detected_category = detect_category(
                article['title'], 
                article['content'], 
                article['source_category']
            )
            
            category = conn.execute(
                "SELECT id FROM categories WHERE slug = ?", 
                (detected_category,)
            ).fetchone()
            
            category_id = category['id'] if category else 1
            
            conn.execute('''INSERT INTO posts 
                (title, slug, content, excerpt, image_url, source_url, 
                 category_id, category, source_name, views, is_published)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)''',
                (article['title'], slug, article['content'], article['excerpt'], 
                 article['image_url'], article['url'], category_id, 
                 detected_category, article['source_name'], random.randint(50, 200)))
            
            conn.commit()
            conn.close()
            print(f"✅ Saved: {article['title'][:50]}... → {detected_category}")
            return True
            
        except Exception as e:
            print(f"❌ Save error: {e}")
            return False
    
    def fetch_all_sources(self, initial=False):
        print("\n" + "="*60)
        print("🚀 FETCHING CONTENT" + (" (INITIAL LOAD)" if initial else ""))
        print("="*60)
        
        total_saved = 0
        count_per_source = FlaskConfig.INITIAL_FETCH_COUNT if initial else 8
        
        # Shuffle sources for better distribution
        sources = FlaskConfig.NEWS_SOURCES.copy()
        random.shuffle(sources)
        
        for source in sources:
            if not source.get('enabled', True):
                continue
            
            articles = self.fetch_articles(source, count=count_per_source)
            for article in articles:
                if self.save_article(article):
                    total_saved += 1
                    # After first few articles, we have something to show
                    if initial and total_saved >= 5:
                        print(f"⚡ Quick-load: Got {total_saved} articles, continuing in background...")
            
            # Very short delay
            time.sleep(0.5)
        
        print("="*60)
        print(f"🎯 TOTAL FETCHED: {total_saved} NEW ARTICLES!")
        print("="*60)
        
        if initial:
            self.first_fetch_done = True
        
        return total_saved
    
    def immediate_fetch(self):
        """IMMEDIATE fetch - blocks until we get SOME data"""
        print("⚡⚡⚡ STARTING IMMEDIATE FETCH ⚡⚡⚡")
        
        total_saved = 0
        # Just fetch from top 3 sources first for speed
        quick_sources = FlaskConfig.NEWS_SOURCES[:3]
        
        for source in quick_sources:
            articles = self.fetch_articles(source, count=5)
            for article in articles:
                if self.save_article(article):
                    total_saved += 1
                    if total_saved >= 10:  # We have enough to show
                        break
            if total_saved >= 10:
                break
        
        print(f"⚡ IMMEDIATE FETCH COMPLETE: {total_saved} articles ready!")
        return total_saved
    
    def start_auto_fetch(self, needs_initial_data=False):
        def fetch_loop():
            print("⏳ Starting fetch scheduler...")
            
            # **IMMEDIATE FETCH - BLOCKING**
            print("⚡ PERFORMING IMMEDIATE FETCH (BLOCKING)...")
            immediate_count = self.immediate_fetch()
            
            if immediate_count == 0 and needs_initial_data:
                print("⚠️ Immediate fetch got 0 articles, doing full fetch...")
                self.fetch_all_sources(initial=True)
            elif needs_initial_data and immediate_count < 20:
                print(f"🔄 Got {immediate_count} articles, fetching more in background...")
                # Start background full fetch
                bg_thread = threading.Thread(target=self.fetch_all_sources, args=(True,), daemon=True)
                bg_thread.start()
            else:
                print(f"✅ {immediate_count} articles ready for display!")
            
            # Regular updates
            print(f"⏰ Scheduled updates every {FlaskConfig.UPDATE_INTERVAL_MINUTES} minutes")
            while True:
                try:
                    time.sleep(FlaskConfig.UPDATE_INTERVAL_MINUTES * 60)
                    print(f"\n🔄 Running scheduled update...")
                    self.fetch_all_sources(initial=False)
                except Exception as e:
                    print(f"❌ Update error: {e}")
                    time.sleep(300)
        
        if not self.is_fetching:
            self.is_fetching = True
            thread = threading.Thread(target=fetch_loop, daemon=True)
            thread.start()
            print("✅ Auto-fetch service started")

# ============= FLASK APP =============
app = Flask(__name__)
app.config.from_object(FlaskConfig)

print("=" * 60)
print("🇿🇦 MZANSI INSIGHTS - STARTING...")
print("=" * 60)

# Setup database FIRST
db_is_empty = setup_database()

# Initialize fetcher
fetcher = ContentFetcher()

# **CRITICAL: Start fetcher BEFORE any requests**
print("🚀 Starting content fetcher BEFORE server starts...")
fetcher.start_auto_fetch(needs_initial_data=True)

# Wait a moment for initial fetch to start
print("⏳ Waiting 2 seconds for initial fetch to begin...")
time.sleep(2)

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

def convert_post_row(row):
    post_dict = dict(row)
    post_dict['formatted_date'] = get_time_ago(post_dict.get('created_at', ''))
    
    try:
        conn = get_db_connection()
        category = conn.execute(
            "SELECT * FROM categories WHERE id = ?", 
            (post_dict.get('category_id', 1),)
        ).fetchone()
        conn.close()
        
        if category:
            post_dict['category_ref'] = {
                'name': category['name'],
                'slug': category['slug'],
                'icon': category['icon'],
                'color': category['color']
            }
        else:
            post_dict['category_ref'] = {
                'name': 'News',
                'slug': 'news',
                'icon': 'newspaper',
                'color': '#4361ee'
            }
    except:
        post_dict['category_ref'] = {
            'name': 'News',
            'slug': 'news',
            'icon': 'newspaper',
            'color': '#4361ee'
        }
    
    return post_dict

# ============= ROUTES =============
@app.route('/')
def index():
    try:
        conn = get_db_connection()
        
        # Get categories with post counts
        categories = []
        for row in conn.execute("SELECT * FROM categories ORDER BY name").fetchall():
            cat_dict = dict(row)
            post_count = conn.execute(
                "SELECT COUNT(*) FROM posts WHERE category_id = ? AND is_published = 1", 
                (cat_dict['id'],)
            ).fetchone()[0]
            cat_dict['post_count'] = post_count
            categories.append(cat_dict)
        
        # Get latest posts - even if not many, show what we have
        posts_raw = conn.execute(
            "SELECT * FROM posts WHERE is_published = 1 ORDER BY created_at DESC LIMIT 20"
        ).fetchall()
        posts = [convert_post_row(row) for row in posts_raw]
        
        # If no posts yet, check again after short delay (first visitor might trigger fetch)
        if not posts and db_is_empty:
            print("⚠️ No posts yet - checking if fetch is in progress...")
            # Wait a bit and check again
            time.sleep(1)
            posts_raw = conn.execute(
                "SELECT * FROM posts WHERE is_published = 1 ORDER BY created_at DESC LIMIT 20"
            ).fetchall()
            posts = [convert_post_row(row) for row in posts_raw]
        
        # Get trending
        trending_raw = conn.execute(
            "SELECT * FROM posts WHERE is_published = 1 ORDER BY views DESC LIMIT 6"
        ).fetchall()
        trending_posts = [convert_post_row(row) for row in trending_raw]
        
        # Get sources with counts
        sources = []
        for source in FlaskConfig.NEWS_SOURCES:
            article_count = conn.execute(
                "SELECT COUNT(*) FROM posts WHERE source_name = ?", 
                (source['name'],)
            ).fetchone()[0]
            sources.append({**source, 'article_count': article_count})
        
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
        logger.error(f"Home error: {e}")
        # Fallback
        return render_template('index.html', 
                             posts=[], 
                             trending_posts=[], 
                             categories=list(CATEGORY_DEFINITIONS.values()),
                             sources=FlaskConfig.NEWS_SOURCES,
                             config=FlaskConfig, 
                             has_posts=False, 
                             now=datetime.now())

@app.route('/category/<category>')
def category_page(category):
    try:
        conn = get_db_connection()
        
        category_row = conn.execute(
            "SELECT * FROM categories WHERE slug = ?", 
            (category,)
        ).fetchone()
        
        if not category_row:
            conn.close()
            return render_template('404.html', config=FlaskConfig), 404
        
        category_info = dict(category_row)
        
        posts_raw = conn.execute(
            "SELECT * FROM posts WHERE category_id = ? AND is_published = 1 ORDER BY created_at DESC LIMIT 30",
            (category_info['id'],)
        ).fetchall()
        posts = [convert_post_row(row) for row in posts_raw]
        
        categories = [dict(row) for row in conn.execute("SELECT * FROM categories").fetchall()]
        conn.close()
        
        return render_template('category.html', 
                             category=category_info, 
                             posts=posts, 
                             categories=categories,
                             config=FlaskConfig, 
                             now=datetime.now())
                             
    except Exception as e:
        logger.error(f"Category error: {e}")
        return render_template('category.html', 
                             category={'name': category, 'slug': category}, 
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
        
        post = convert_post_row(post_raw)
        
        conn.execute("UPDATE posts SET views = views + 1 WHERE slug = ?", (slug,))
        conn.commit()
        
        related_raw = conn.execute(
            "SELECT * FROM posts WHERE category_id = ? AND slug != ? AND is_published = 1 ORDER BY RANDOM() LIMIT 4",
            (post['category_id'], slug)
        ).fetchall()
        related_posts = [convert_post_row(row) for row in related_raw]
        
        categories = [dict(row) for row in conn.execute("SELECT * FROM categories").fetchall()]
        conn.close()
        
        return render_template('post.html', 
                             post=post, 
                             related_posts=related_posts, 
                             categories=categories,
                             config=FlaskConfig, 
                             now=datetime.now())
                             
    except Exception as e:
        logger.error(f"Post error: {e}")
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
            posts = [convert_post_row(row) for row in posts_raw]
        else:
            posts = []
        
        categories = [dict(row) for row in conn.execute("SELECT * FROM categories").fetchall()]
        conn.close()
        
        return render_template('search.html', 
                             query=query, 
                             posts=posts, 
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

@app.route('/privacy')
def privacy():
    try:
        conn = get_db_connection()
        categories = [dict(row) for row in conn.execute("SELECT * FROM categories").fetchall()]
        conn.close()
    except:
        categories = []
    return render_template('privacy.html', config=FlaskConfig, categories=categories, now=datetime.now())

@app.route('/terms')
def terms():
    try:
        conn = get_db_connection()
        categories = [dict(row) for row in conn.execute("SELECT * FROM categories").fetchall()]
        conn.close()
    except:
        categories = []
    return render_template('terms.html', config=FlaskConfig, categories=categories, now=datetime.now())

@app.route('/contact')
def contact():
    try:
        conn = get_db_connection()
        categories = [dict(row) for row in conn.execute("SELECT * FROM categories").fetchall()]
        conn.close()
    except:
        categories = []
    return render_template('contact.html', config=FlaskConfig, categories=categories, now=datetime.now())

@app.route('/about')
def about():
    try:
        conn = get_db_connection()
        categories = [dict(row) for row in conn.execute("SELECT * FROM categories").fetchall()]
        conn.close()
    except:
        categories = []
    return render_template('about.html', config=FlaskConfig, categories=categories, now=datetime.now())

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
        'fetching_status': 'Active' if fetcher.is_fetching else 'Inactive'
    }
    
    recent = conn.execute("SELECT * FROM posts ORDER BY created_at DESC LIMIT 10").fetchall()
    conn.close()
    
    return render_template('admin/dashboard.html', stats=stats, recent_posts=recent, config=FlaskConfig)

@app.route('/admin/fetch-now')
@login_required
def admin_fetch_now():
    thread = threading.Thread(target=fetcher.fetch_all_sources, daemon=True)
    thread.start()
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
        today = datetime.now().strftime('%Y-%m-%d')
        hour_ago = (datetime.now() - timedelta(hours=1)).strftime('%Y-%m-%d %H:%M:%S')
        
        stats = {
            'posts': conn.execute("SELECT COUNT(*) FROM posts WHERE is_published = 1").fetchone()[0],
            'today_posts': conn.execute("SELECT COUNT(*) FROM posts WHERE is_published = 1 AND date(created_at) = ?", (today,)).fetchone()[0],
            'hour_posts': conn.execute("SELECT COUNT(*) FROM posts WHERE is_published = 1 AND created_at >= ?", (hour_ago,)).fetchone()[0],
            'total_views': conn.execute("SELECT SUM(views) FROM posts").fetchone()[0] or 0,
            'status': 'online',
            'fetching': fetcher.is_fetching,
            'sources_count': len(FlaskConfig.NEWS_SOURCES),
            'time': datetime.now().strftime('%H:%M:%S')
        }
        
        conn.close()
        return jsonify(stats)
        
    except Exception as e:
        logger.error(f"Stats API error: {e}")
        return jsonify({'error': 'Internal server error', 'status': 'error'}), 500

@app.errorhandler(404)
def not_found(e):
    return render_template('404.html', config=FlaskConfig), 404

@app.errorhandler(500)
def server_error(e):
    logger.error(f"500 error: {e}")
    return render_template('500.html', config=FlaskConfig), 500

# ============= START APP =============
if __name__ == '__main__':
    print("=" * 60)
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