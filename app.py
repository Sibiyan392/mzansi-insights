# Python 3.13+ compatibility fix
import fix_cgi

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, g
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
import hashlib
import atexit
import requests
from urllib.parse import urlparse, quote
import schedule
from apscheduler.schedulers.background import BackgroundScheduler
import uuid

# Fix Unicode encoding
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# ============= FLASK CONFIG =============
class FlaskConfig:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-key-please-change-in-production-' + str(uuid.uuid4()))
    SITE_NAME = "Mzansi Insights"
    SITE_DESCRIPTION = "South African News & Updates - Aggregated from Trusted Sources"
    POSTS_PER_PAGE = 12
    ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME', 'admin')
    ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'admin123')
    
    # Adsense IDs
    ADSENSE_ID = os.environ.get('ADSENSE_ID', '')
    ADSENSE_SLOT_BANNER = os.environ.get('ADSENSE_SLOT_BANNER', '')
    ADSENSE_SLOT_INARTICLE = os.environ.get('ADSENSE_SLOT_INARTICLE', '')
    
    # Contact Info
    CONTACT_EMAIL = 'sibiyan4444@gmail.com'
    CONTACT_PHONE = '+27 72 472 8166'
    PHYSICAL_ADDRESS = 'Johannesburg, South Africa'
    SITE_URL = os.environ.get('SITE_URL', 'https://mzansi-insights.onrender.com')
    
    # Content Update
    UPDATE_INTERVAL_MINUTES = int(os.environ.get('UPDATE_INTERVAL_MINUTES', '30'))
    
    # Debug settings
    DEBUG = os.environ.get('DEBUG', 'False').lower() == 'true'
    PORT = int(os.environ.get('PORT', 5000))
    
    # Render specific
    RENDER = os.environ.get('RENDER', False)

# ============= DATABASE SETUP WITH PERSISTENCE =============
def get_db_path():
    """Get database path with Render persistence"""
    if os.environ.get('RENDER'):
        # Render persistent volume
        data_dir = '/opt/render/project/src/data'
        os.makedirs(data_dir, exist_ok=True)
        return os.path.join(data_dir, 'posts.db')
    else:
        # Local development
        data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
        os.makedirs(data_dir, exist_ok=True)
        return os.path.join(data_dir, 'posts.db')

def init_database():
    """Initialize database connection"""
    db_path = get_db_path()
    logger.info(f"Database path: {db_path}")
    
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    
    # Enable WAL mode for better concurrency
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA synchronous=NORMAL')
    
    return conn

def setup_database():
    """Setup database tables and initial data"""
    logger.info("=" * 60)
    logger.info("SETTING UP DATABASE...")
    logger.info("=" * 60)
    
    try:
        conn = init_database()
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
            color TEXT,
            post_count INTEGER DEFAULT 0
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
            pub_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (category_id) REFERENCES categories(id)
        )''')
        
        # Indexes
        c.execute('CREATE INDEX IF NOT EXISTS idx_posts_slug ON posts(slug)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_posts_category ON posts(category_id)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_posts_pub_date ON posts(pub_date DESC)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_posts_created ON posts(created_at DESC)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_posts_views ON posts(views DESC)')
        
        # Create admin user if not exists
        c.execute("SELECT COUNT(*) FROM users WHERE username = ?", (FlaskConfig.ADMIN_USERNAME,))
        if c.fetchone()[0] == 0:
            pwd_hash = generate_password_hash(FlaskConfig.ADMIN_PASSWORD)
            c.execute("INSERT INTO users (username, password_hash) VALUES (?, ?)", 
                     (FlaskConfig.ADMIN_USERNAME, pwd_hash))
            logger.info("✅ Admin user created")
        
        # Define categories
        CATEGORIES = [
            ('News', 'news', 'Breaking news and current events', 'newspaper', '#4361ee'),
            ('Business', 'business', 'Business and economic news', 'chart-line', '#7209b7'),
            ('Technology', 'technology', 'Tech news and innovation', 'laptop-code', '#3498db'),
            ('Sports', 'sports', 'Sports news and updates', 'running', '#2ecc71'),
            ('Entertainment', 'entertainment', 'Entertainment news', 'film', '#ef476f'),
            ('Jobs', 'jobs', 'Employment opportunities', 'briefcase', '#06d6a0'),
            ('Grants', 'grants', 'Grants and SASSA information', 'hand-holding-usd', '#ff9e00'),
            ('Government', 'government', 'Government updates', 'landmark', '#2c3e50'),
            ('Health', 'health', 'Health and wellness', 'heartbeat', '#e74c3c'),
            ('Education', 'education', 'Education news', 'graduation-cap', '#9b59b6'),
        ]
        
        # Insert/Update categories
        for name, slug, desc, icon, color in CATEGORIES:
            c.execute("SELECT id FROM categories WHERE slug = ?", (slug,))
            if c.fetchone() is None:
                c.execute("INSERT INTO categories (name, slug, description, icon, color) VALUES (?, ?, ?, ?, ?)",
                         (name, slug, desc, icon, color))
                logger.info(f"✅ Category created: {name}")
        
        # Check if we need sample posts
        c.execute("SELECT COUNT(*) FROM posts")
        post_count = c.fetchone()[0]
        
        if post_count == 0:
            logger.info("📝 Adding sample posts...")
            sample_posts = [
                ("Breaking: Major Economic Announcement Expected", 
                 "The South African government is set to make a major economic announcement this afternoon that could impact markets and business sectors across the country.", 
                 "news", "News24", "https://images.unsplash.com/photo-1588681664899-f142ff2dc9b1?w=800"),
                ("Tech Giant Announces 1000 New Jobs in Cape Town", 
                 "A major technology company is expanding its South African operations with a new R&D center in Cape Town, creating over 1000 new high-tech jobs.", 
                 "business", "BusinessTech", "https://images.unsplash.com/photo-1497366754035-f200968a6e72?w=800"),
                ("Springboks Prepare for Championship Defense", 
                 "The national rugby team begins intensive training for the upcoming championship season with new coaching strategies and player selections.", 
                 "sports", "Sport24", "https://images.unsplash.com/photo-1546519638-68e109498ffc?w=800"),
                ("New Grant Applications Open for Students", 
                 "Applications for the 2024 student grant program are now open with increased funding amounts and expanded eligibility criteria for South African students.", 
                 "grants", "IOL", "https://images.unsplash.com/photo-1523050854058-8df90110c9f1?w=800"),
                ("Government Announces Infrastructure Projects", 
                 "Billions allocated for new infrastructure development including roads, schools, and hospitals across multiple provinces to boost economic growth.", 
                 "government", "TimesLive", "https://images.unsplash.com/photo-1486406146926-c627a92ad1ab?w=800"),
            ]
            
            for title, content, category, source, image in sample_posts:
                slug_base = re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')
                slug = f"{slug_base[:80]}-{hashlib.md5(title.encode()).hexdigest()[:6]}"
                excerpt = content[:150] + '...' if len(content) > 150 else content
                
                c.execute("SELECT id FROM categories WHERE slug = ?", (category,))
                category_row = c.fetchone()
                category_id = category_row[0] if category_row else 1
                
                c.execute('''INSERT INTO posts 
                    (title, slug, content, excerpt, image_url, source_url, 
                     category_id, category, source_name, views, is_published)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)''',
                    (title, slug, content, excerpt, image, '#', 
                     category_id, category, source, random.randint(50, 500)))
            
            logger.info("✅ Sample posts added")
        
        # Update category counts
        c.execute("SELECT id FROM categories")
        for cat in c.fetchall():
            count = conn.execute("SELECT COUNT(*) FROM posts WHERE category_id = ?", (cat[0],)).fetchone()[0]
            conn.execute("UPDATE categories SET post_count = ? WHERE id = ?", (count, cat[0]))
        
        conn.commit()
        conn.close()
        
        logger.info("✅ Database setup complete")
        logger.info("=" * 60)
        return True
        
    except Exception as e:
        logger.error(f"❌ Database setup failed: {e}", exc_info=True)
        return False

def get_db_connection():
    """Get database connection with error handling"""
    try:
        return init_database()
    except Exception as e:
        logger.error(f"Database connection error: {e}")
        # Return mock connection to prevent crashes
        class MockConnection:
            def execute(self, *args, **kwargs):
                class MockCursor:
                    def fetchall(self): return []
                    def fetchone(self): return None
                    def __iter__(self): return iter([])
                return MockCursor()
            def commit(self): pass
            def close(self): pass
            def cursor(self): return self.execute()
        return MockConnection()

# ============= CONTENT FETCHER =============
class ContentFetcher:
    def __init__(self):
        self.is_fetching = False
        self.last_fetch_time = None
        self.last_fetch_count = 0
        
        # News Sources with better configuration
        self.NEWS_SOURCES = [
            {'name': 'News24', 'url': 'https://www.news24.com/feed', 'category': 'news', 'color': '#4361ee', 'icon': 'newspaper', 'enabled': True},
            {'name': 'TimesLive', 'url': 'https://www.timeslive.co.za/feed/', 'category': 'news', 'color': '#7209b7', 'icon': 'newspaper', 'enabled': True},
            {'name': 'IOL', 'url': 'https://www.iol.co.za/rss', 'category': 'news', 'color': '#e63946', 'icon': 'newspaper', 'enabled': True},
            {'name': 'Moneyweb', 'url': 'https://www.moneyweb.co.za/feed/', 'category': 'business', 'color': '#1dd1a1', 'icon': 'chart-line', 'enabled': True},
            {'name': 'BusinessTech', 'url': 'https://businesstech.co.za/news/feed/', 'category': 'business', 'color': '#3742fa', 'icon': 'laptop-code', 'enabled': True},
            {'name': 'Daily Maverick', 'url': 'https://www.dailymaverick.co.za/feed/', 'category': 'news', 'color': '#f77f00', 'icon': 'newspaper', 'enabled': True},
            {'name': 'MyBroadband', 'url': 'https://mybroadband.co.za/news/feed', 'category': 'technology', 'color': '#9b59b6', 'icon': 'wifi', 'enabled': True},
            {'name': 'TechCentral', 'url': 'https://techcentral.co.za/feed/', 'category': 'technology', 'color': '#3498db', 'icon': 'microchip', 'enabled': True},
            {'name': 'Sport24', 'url': 'https://www.sport24.co.za/feed', 'category': 'sports', 'color': '#2ecc71', 'icon': 'running', 'enabled': True},
            {'name': 'The Citizen', 'url': 'https://www.citizen.co.za/feed/', 'category': 'news', 'color': '#d62828', 'icon': 'newspaper', 'enabled': True},
        ]
    
    def fetch_feed(self, source):
        """Fetch a single RSS feed with retry"""
        max_retries = 2
        for attempt in range(max_retries):
            try:
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Accept': 'application/rss+xml, application/xml, text/xml, */*',
                    'Accept-Language': 'en-US,en;q=0.9',
                    'Connection': 'keep-alive',
                }
                
                # Use feedparser with custom headers
                feed = feedparser.parse(source['url'], request_headers=headers, timeout=15)
                
                if feed.bozo and feed.bozo_exception:
                    logger.warning(f"Feed parse warning {source['name']}: {feed.bozo_exception}")
                
                if feed.entries:
                    return feed
                    
            except Exception as e:
                logger.warning(f"Attempt {attempt+1} failed for {source['name']}: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2)
        
        return None
    
    def extract_image(self, entry, category='news'):
        """Extract image URL from entry"""
        try:
            # Check various image sources
            if hasattr(entry, 'media_content') and entry.media_content:
                for media in entry.media_content:
                    if media.get('type', '').startswith('image/'):
                        img_url = media.get('url', '')
                        if img_url and img_url.startswith('http'):
                            return img_url
            
            if hasattr(entry, 'media_thumbnail') and entry.media_thumbnail:
                for thumb in entry.media_thumbnail:
                    img_url = thumb.get('url', '')
                    if img_url and img_url.startswith('http'):
                        return img_url
            
            if hasattr(entry, 'enclosures') and entry.enclosures:
                for enc in entry.enclosures:
                    if enc.get('type', '').startswith('image/'):
                        img_url = enc.get('href', '')
                        if img_url and img_url.startswith('http'):
                            return img_url
            
            # Extract from content/summary
            content = entry.get('summary', entry.get('description', ''))
            if content:
                import re
                img_match = re.search(r'<img[^>]+src="([^">]+)"', content)
                if img_match:
                    img_url = img_match.group(1)
                    if img_url and img_url.startswith('http'):
                        return img_url
            
        except Exception as e:
            logger.debug(f"Image extraction error: {e}")
        
        # Fallback images by category
        fallback_images = {
            'news': 'https://images.unsplash.com/photo-1588681664899-f142ff2dc9b1?w=800&auto=format&fit=crop',
            'business': 'https://images.unsplash.com/photo-1497366754035-f200968a6e72?w=800&auto=format&fit=crop',
            'sports': 'https://images.unsplash.com/photo-1546519638-68e109498ffc?w=800&auto=format&fit=crop',
            'technology': 'https://images.unsplash.com/photo-1519389950473-47ba0277781c?w=800&auto=format&fit=crop',
            'entertainment': 'https://images.unsplash.com/photo-1493225457124-a3eb161ffa5f?w=800&auto=format&fit=crop',
            'grants': 'https://images.unsplash.com/photo-1523050854058-8df90110c9f1?w=800&auto=format&fit=crop',
            'government': 'https://images.unsplash.com/photo-1486406146926-c627a92ad1ab?w=800&auto=format&fit=crop',
            'health': 'https://images.unsplash.com/photo-1576091160399-112ba8d25d1f?w=800&auto=format&fit=crop',
            'education': 'https://images.unsplash.com/photo-1523050854058-8df90110c9f1?w=800&auto=format&fit=crop',
            'jobs': 'https://images.unsplash.com/photo-1497366754035-f200968a6e72?w=800&auto=format&fit=crop',
        }
        
        return fallback_images.get(category, fallback_images['news'])
    
    def clean_content(self, text):
        """Clean HTML content"""
        if not text:
            return ""
        
        # Remove HTML tags
        text = re.sub(r'<[^>]+>', '', text)
        
        # Decode HTML entities
        replacements = {
            '&nbsp;': ' ', '&amp;': '&', '&lt;': '<', '&gt;': '>',
            '&quot;': '"', '&#39;': "'", '&rsquo;': "'", '&lsquo;': "'"
        }
        
        for entity, replacement in replacements.items():
            text = text.replace(entity, replacement)
        
        # Clean whitespace
        text = ' '.join(text.split())
        
        return text[:2000]  # Limit length
    
    def fetch_and_save(self, force=False):
        """Fetch and save articles from all sources"""
        if self.is_fetching and not force:
            logger.info("Already fetching, skipping...")
            return 0
        
        self.is_fetching = True
        total_saved = 0
        
        try:
            logger.info("⚡ STARTING CONTENT FETCH...")
            conn = get_db_connection()
            
            for source in [s for s in self.NEWS_SOURCES if s.get('enabled', True)]:
                try:
                    logger.info(f"📡 Fetching from {source['name']}...")
                    feed = self.fetch_feed(source)
                    
                    if not feed or not feed.entries:
                        logger.warning(f"  No entries from {source['name']}")
                        continue
                    
                    source_saved = 0
                    for entry in feed.entries[:8]:  # Limit to 8 per source
                        try:
                            title = entry.get('title', '').strip()
                            if not title or len(title) < 10:
                                continue
                            
                            # Generate unique slug
                            slug_base = re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')
                            slug_hash = hashlib.md5(title.encode()).hexdigest()[:6]
                            slug = f"{slug_base[:70]}-{slug_hash}"
                            
                            # Check if article already exists
                            existing = conn.execute(
                                "SELECT id FROM posts WHERE slug = ? OR (title = ? AND source_name = ?)",
                                (slug, title[:100], source['name'])
                            ).fetchone()
                            
                            if existing:
                                continue
                            
                            # Prepare content
                            raw_content = entry.get('summary', entry.get('description', ''))
                            content = self.clean_content(raw_content)
                            
                            if not content or len(content) < 50:
                                content = title
                            
                            excerpt = content[:200] + '...' if len(content) > 200 else content
                            
                            # Get image
                            image_url = self.extract_image(entry, source['category'])
                            
                            # Get category ID
                            cat_row = conn.execute(
                                "SELECT id FROM categories WHERE slug = ?", 
                                (source['category'],)
                            ).fetchone()
                            category_id = cat_row[0] if cat_row else 1
                            
                            # Get publication date
                            pub_date = datetime.now()
                            if hasattr(entry, 'published_parsed') and entry.published_parsed:
                                try:
                                    pub_date = datetime(*entry.published_parsed[:6])
                                except:
                                    pass
                            
                            # Insert the article
                            conn.execute('''INSERT INTO posts 
                                (title, slug, content, excerpt, image_url, source_url, 
                                 category_id, category, source_name, views, is_published, pub_date)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)''',
                                (title, slug, content, excerpt, image_url, 
                                 entry.get('link', '#'), category_id, source['category'],
                                 source['name'], random.randint(10, 50), pub_date))
                            
                            source_saved += 1
                            total_saved += 1
                            
                            if source_saved <= 3:  # Log first 3
                                logger.info(f"  ✅ Saved: {title[:60]}...")
                            
                        except Exception as e:
                            logger.debug(f"    Article error: {e}")
                            continue
                    
                    if source_saved > 0:
                        logger.info(f"✅ {source['name']}: {source_saved} new articles")
                    else:
                        logger.info(f"ℹ️ {source['name']}: No new articles")
                    
                except Exception as e:
                    logger.error(f"❌ Source {source['name']} failed: {e}")
                    continue
            
            # Update category counts
            if total_saved > 0:
                conn.execute("SELECT id FROM categories")
                for cat in conn.fetchall():
                    count = conn.execute(
                        "SELECT COUNT(*) FROM posts WHERE category_id = ?", 
                        (cat[0],)
                    ).fetchone()[0]
                    conn.execute(
                        "UPDATE categories SET post_count = ? WHERE id = ?", 
                        (count, cat[0])
                    )
            
            conn.commit()
            conn.close()
            
            self.last_fetch_time = datetime.now()
            self.last_fetch_count = total_saved
            
            if total_saved > 0:
                logger.info(f"🎯 FETCH COMPLETE: {total_saved} NEW ARTICLES!")
            else:
                logger.info("✅ Fetch complete: No new articles found")
            
            return total_saved
            
        except Exception as e:
            logger.error(f"❌ FETCH ERROR: {e}", exc_info=True)
            return 0
        finally:
            self.is_fetching = False

# ============= FLASK APP =============
app = Flask(__name__)
app.config.from_object(FlaskConfig)

print("=" * 60)
print("🇿🇦 MZANSI INSIGHTS - STARTING ON RENDER...")
print("=" * 60)

# Setup database
db_ready = setup_database()

# Initialize fetcher
fetcher = ContentFetcher()

# DO IMMEDIATE FETCH ON STARTUP - BLOCKING
print("🚀 FORCING IMMEDIATE FETCH ON STARTUP...")
initial_fetched = fetcher.fetch_and_save(force=True)
print(f"✅ Initial fetch: {initial_fetched} articles")

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'admin_login'

class User(UserMixin):
    def __init__(self, id, username):
        self.id = id
        self.username = username

@login_manager.user_loader
def load_user(user_id):
    try:
        conn = get_db_connection()
        user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        conn.close()
        return User(user['id'], user['username']) if user else None
    except:
        return None

# Helper functions
def get_time_ago(date_str):
    """Convert date to relative time"""
    try:
        if not date_str:
            return "Recently"
        
        if isinstance(date_str, str):
            post_date = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
        elif isinstance(date_str, datetime):
            post_date = date_str
        else:
            return "Recently"
        
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
        return "Just now"
    except:
        return "Recently"

def prepare_post(post_row):
    """Prepare post for template"""
    if not post_row:
        return None
    
    post = dict(post_row)
    
    # Format dates
    post['formatted_date'] = get_time_ago(post.get('pub_date') or post.get('created_at', ''))
    post['full_date'] = post.get('pub_date', post.get('created_at', ''))
    
    # Get category info
    try:
        conn = get_db_connection()
        category = conn.execute(
            "SELECT * FROM categories WHERE id = ?", 
            (post.get('category_id', 1),)
        ).fetchone()
        conn.close()
        
        if category:
            post['category_ref'] = {
                'name': category['name'],
                'slug': category['slug'],
                'icon': category['icon'],
                'color': category['color']
            }
        else:
            post['category_ref'] = {
                'name': 'News',
                'slug': 'news',
                'icon': 'newspaper',
                'color': '#4361ee'
            }
    except:
        post['category_ref'] = {
            'name': 'News',
            'slug': 'news',
            'icon': 'newspaper',
            'color': '#4361ee'
        }
    
    return post

def get_categories_with_counts():
    """Get all categories with post counts"""
    try:
        conn = get_db_connection()
        categories = []
        cat_rows = conn.execute(
            "SELECT * FROM categories ORDER BY name"
        ).fetchall()
        
        for cat in cat_rows:
            cat_dict = dict(cat)
            categories.append(cat_dict)
        
        conn.close()
        return categories
    except:
        return []

# ============= ALL ROUTES =============
@app.route('/')
def index():
    """Home page"""
    try:
        conn = get_db_connection()
        
        # Featured/Latest post
        featured_raw = conn.execute(
            "SELECT * FROM posts WHERE is_published = 1 ORDER BY pub_date DESC LIMIT 1"
        ).fetchone()
        featured = prepare_post(featured_raw) if featured_raw else None
        
        # Latest posts (excluding featured)
        posts_raw = conn.execute(
            "SELECT * FROM posts WHERE is_published = 1 AND id != ? ORDER BY pub_date DESC LIMIT 11",
            (featured['id'] if featured else 0,)
        ).fetchall()
        posts = [prepare_post(row) for row in posts_raw]
        
        # Trending posts
        trending_raw = conn.execute(
            "SELECT * FROM posts WHERE is_published = 1 ORDER BY views DESC, pub_date DESC LIMIT 6"
        ).fetchall()
        trending_posts = [prepare_post(row) for row in trending_raw]
        
        # Categories
        categories = get_categories_with_counts()
        
        # Sources
        sources = fetcher.NEWS_SOURCES
        
        conn.close()
        
        return render_template('index.html',
                             featured_post=featured,
                             posts=posts,
                             trending_posts=trending_posts,
                             categories=categories,
                             sources=sources,
                             config=FlaskConfig,
                             now=datetime.now())
                             
    except Exception as e:
        logger.error(f"Home error: {e}")
        return render_template('index.html',
                             featured_post=None,
                             posts=[],
                             trending_posts=[],
                             categories=get_categories_with_counts(),
                             sources=fetcher.NEWS_SOURCES,
                             config=FlaskConfig,
                             now=datetime.now())

@app.route('/category/<category_slug>')
def category_page(category_slug):
    """Category page"""
    try:
        conn = get_db_connection()
        
        # Get category
        category = conn.execute(
            "SELECT * FROM categories WHERE slug = ?", 
            (category_slug,)
        ).fetchone()
        
        if not category:
            return render_template('404.html', config=FlaskConfig), 404
        
        category = dict(category)
        
        # Get posts for this category
        posts_raw = conn.execute(
            "SELECT * FROM posts WHERE category_id = ? AND is_published = 1 ORDER BY pub_date DESC LIMIT 50",
            (category['id'],)
        ).fetchall()
        posts = [prepare_post(row) for row in posts_raw]
        
        # All categories for sidebar
        categories = get_categories_with_counts()
        
        conn.close()
        
        return render_template('category.html',
                             category=category,
                             posts=posts,
                             categories=categories,
                             config=FlaskConfig,
                             now=datetime.now())
                             
    except Exception as e:
        logger.error(f"Category error: {e}")
        return render_template('404.html', config=FlaskConfig), 404

@app.route('/post/<slug>')
def post_detail(slug):
    """Post detail page"""
    try:
        conn = get_db_connection()
        
        # Get post
        post_raw = conn.execute(
            "SELECT * FROM posts WHERE slug = ? AND is_published = 1", 
            (slug,)
        ).fetchone()
        
        if not post_raw:
            conn.close()
            return render_template('404.html', config=FlaskConfig), 404
        
        post = prepare_post(post_raw)
        
        # Update views
        conn.execute("UPDATE posts SET views = views + 1 WHERE slug = ?", (slug,))
        conn.commit()
        
        # Get related posts
        related_raw = conn.execute(
            "SELECT * FROM posts WHERE category_id = ? AND slug != ? AND is_published = 1 ORDER BY pub_date DESC LIMIT 4",
            (post['category_id'], slug)
        ).fetchall()
        
        # If not enough related, get latest
        if len(related_raw) < 4:
            extra = conn.execute(
                "SELECT * FROM posts WHERE slug != ? AND is_published = 1 ORDER BY pub_date DESC LIMIT ?",
                (slug, 4 - len(related_raw))
            ).fetchall()
            related_raw = list(related_raw) + list(extra)
        
        related_posts = [prepare_post(row) for row in related_raw]
        
        conn.close()
        
        return render_template('post.html',
                             post=post,
                             related_posts=related_posts,
                             config=FlaskConfig,
                             now=datetime.now())
                             
    except Exception as e:
        logger.error(f"Post error: {e}")
        return render_template('404.html', config=FlaskConfig), 404

@app.route('/search')
def search():
    """Search page"""
    query = request.args.get('q', '').strip()
    page = request.args.get('page', 1, type=int)
    per_page = 12
    
    try:
        conn = get_db_connection()
        
        posts = []
        total = 0
        
        if query and len(query) >= 2:
            search_term = f'%{query}%'
            
            # Get total count
            count_row = conn.execute(
                "SELECT COUNT(*) FROM posts WHERE (title LIKE ? OR content LIKE ?) AND is_published = 1",
                (search_term, search_term)
            ).fetchone()
            total = count_row[0] if count_row else 0
            
            # Get paginated results
            offset = (page - 1) * per_page
            posts_raw = conn.execute(
                "SELECT * FROM posts WHERE (title LIKE ? OR content LIKE ?) AND is_published = 1 ORDER BY pub_date DESC LIMIT ? OFFSET ?",
                (search_term, search_term, per_page, offset)
            ).fetchall()
            posts = [prepare_post(row) for row in posts_raw]
        
        # Get categories for sidebar
        categories = get_categories_with_counts()
        
        conn.close()
        
        total_pages = (total + per_page - 1) // per_page
        
        return render_template('search.html',
                             query=query,
                             posts=posts,
                             categories=categories,
                             page=page,
                             total_pages=total_pages,
                             total=total,
                             config=FlaskConfig,
                             now=datetime.now())
                             
    except Exception as e:
        logger.error(f"Search error: {e}")
        return render_template('search.html',
                             query=query,
                             posts=[],
                             categories=get_categories_with_counts(),
                             page=1,
                             total_pages=1,
                             total=0,
                             config=FlaskConfig,
                             now=datetime.now())

@app.route('/sources')
def sources():
    """Sources page"""
    try:
        conn = get_db_connection()
        
        # Get sources with counts
        sources_list = []
        for source in fetcher.NEWS_SOURCES:
            if source.get('enabled', True):
                count_row = conn.execute(
                    "SELECT COUNT(*) FROM posts WHERE source_name = ? AND is_published = 1", 
                    (source['name'],)
                ).fetchone()
                article_count = count_row[0] if count_row else 0
                
                sources_list.append({
                    'name': source['name'],
                    'url': source['url'],
                    'category': source['category'],
                    'color': source['color'],
                    'icon': source['icon'],
                    'article_count': article_count,
                    'last_fetch': fetcher.last_fetch_time.strftime('%Y-%m-%d %H:%M') if fetcher.last_fetch_time else 'Never'
                })
        
        conn.close()
        
        return render_template('sources.html',
                             sources=sources_list,
                             categories=get_categories_with_counts(),
                             config=FlaskConfig,
                             now=datetime.now())
                             
    except Exception as e:
        logger.error(f"Sources error: {e}")
        return render_template('sources.html',
                             sources=[],
                             categories=get_categories_with_counts(),
                             config=FlaskConfig,
                             now=datetime.now())

# ============= STATIC PAGES =============
@app.route('/about')
def about():
    return render_template('about.html',
                         categories=get_categories_with_counts(),
                         config=FlaskConfig,
                         now=datetime.now())

@app.route('/disclaimer')
def disclaimer():
    return render_template('disclaimer.html',
                         categories=get_categories_with_counts(),
                         config=FlaskConfig,
                         now=datetime.now())

@app.route('/privacy')
def privacy():
    return render_template('privacy.html',
                         categories=get_categories_with_counts(),
                         config=FlaskConfig,
                         now=datetime.now())

@app.route('/terms')
def terms():
    return render_template('terms.html',
                         categories=get_categories_with_counts(),
                         config=FlaskConfig,
                         now=datetime.now())

@app.route('/contact')
def contact():
    return render_template('contact.html',
                         categories=get_categories_with_counts(),
                         config=FlaskConfig,
                         now=datetime.now())

@app.route('/sitemap')
def sitemap():
    try:
        conn = get_db_connection()
        posts = conn.execute(
            "SELECT slug, title, pub_date FROM posts WHERE is_published = 1 ORDER BY pub_date DESC LIMIT 100"
        ).fetchall()
        conn.close()
        
        return render_template('sitemap.html',
                             posts=posts,
                             categories=get_categories_with_counts(),
                             config=FlaskConfig,
                             now=datetime.now())
    except:
        return render_template('sitemap.html',
                             posts=[],
                             categories=get_categories_with_counts(),
                             config=FlaskConfig,
                             now=datetime.now())

# ============= API ENDPOINTS =============
@app.route('/api/live-news')
def live_news():
    """Live news API for ticker"""
    try:
        conn = get_db_connection()
        posts_raw = conn.execute(
            """SELECT p.*, c.color, c.name as category_name 
               FROM posts p 
               LEFT JOIN categories c ON p.category_id = c.id 
               WHERE p.is_published = 1 
               ORDER BY p.pub_date DESC 
               LIMIT 8"""
        ).fetchall()
        conn.close()
        
        articles = []
        for post in posts_raw:
            post_dict = dict(post)
            title = post_dict['title']
            if len(title) > 80:
                title = title[:77] + '...'
            
            articles.append({
                'title': title,
                'category': post_dict.get('category_name', 'News'),
                'color': post_dict.get('color', '#4361ee'),
                'time_ago': get_time_ago(post_dict.get('pub_date', ''))
            })
        
        return jsonify({
            'status': 'success', 
            'articles': articles,
            'last_updated': datetime.now().strftime('%H:%M:%S')
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error', 
            'articles': [],
            'last_updated': datetime.now().strftime('%H:%M:%S')
        })

@app.route('/api/fetch-now')
def api_fetch_now():
    """Manually trigger fetch"""
    if fetcher.is_fetching:
        return jsonify({
            'status': 'already_fetching', 
            'message': 'Fetch already in progress'
        })
    
    threading.Thread(target=fetcher.fetch_and_save, daemon=True).start()
    return jsonify({
        'status': 'started', 
        'message': 'Content fetch started in background'
    })

@app.route('/api/stats')
def api_stats():
    """Site statistics"""
    try:
        conn = get_db_connection()
        
        posts_count = conn.execute(
            "SELECT COUNT(*) FROM posts WHERE is_published = 1"
        ).fetchone()[0]
        
        total_views = conn.execute(
            "SELECT SUM(views) FROM posts"
        ).fetchone()[0] or 0
        
        categories_count = conn.execute(
            "SELECT COUNT(*) FROM categories"
        ).fetchone()[0]
        
        conn.close()
        
        return jsonify({
            'posts': posts_count,
            'total_views': total_views,
            'categories': categories_count,
            'sources': len([s for s in fetcher.NEWS_SOURCES if s.get('enabled', True)]),
            'last_fetch': fetcher.last_fetch_time.isoformat() if fetcher.last_fetch_time else None,
            'last_fetch_count': fetcher.last_fetch_count,
            'status': 'online',
            'time': datetime.now().strftime('%H:%M:%S'),
            'fetching': fetcher.is_fetching
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error', 
            'error': str(e)
        })

# ============= ADMIN ROUTES =============
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
        'sources': len(fetcher.NEWS_SOURCES),
        'fetching_status': 'Active' if fetcher.is_fetching else 'Idle',
        'last_fetch': fetcher.last_fetch_time.strftime('%Y-%m-%d %H:%M:%S') if fetcher.last_fetch_time else 'Never',
        'last_fetch_count': fetcher.last_fetch_count
    }
    
    recent = conn.execute(
        "SELECT * FROM posts ORDER BY created_at DESC LIMIT 10"
    ).fetchall()
    
    conn.close()
    
    return render_template('admin/dashboard.html',
                         stats=stats,
                         recent_posts=recent,
                         config=FlaskConfig)

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

# ============= ERROR HANDLERS =============
@app.errorhandler(404)
def not_found(e):
    return render_template('404.html', config=FlaskConfig), 404

@app.errorhandler(500)
def server_error(e):
    logger.error(f"500 error: {e}")
    return render_template('500.html', config=FlaskConfig), 500

# ============= BACKGROUND SCHEDULER =============
def schedule_fetcher():
    """Schedule regular content fetching"""
    def run_fetch():
        try:
            logger.info("🔄 Running scheduled fetch...")
            fetched = fetcher.fetch_and_save()
            if fetched > 0:
                logger.info(f"✅ Scheduled fetch complete: {fetched} new articles")
            else:
                logger.info("✅ Scheduled fetch complete: No new articles")
        except Exception as e:
            logger.error(f"❌ Scheduled fetch error: {e}")
    
    # Create scheduler
    scheduler = BackgroundScheduler()
    
    # Schedule fetch every 30 minutes
    scheduler.add_job(
        run_fetch,
        'interval',
        minutes=FlaskConfig.UPDATE_INTERVAL_MINUTES,
        id='content_fetch',
        next_run_time=datetime.now() + timedelta(seconds=10)  # Start 10 seconds after startup
    )
    
    scheduler.start()
    logger.info(f"✅ Scheduler started - Fetching every {FlaskConfig.UPDATE_INTERVAL_MINUTES} minutes")
    
    # Shut down the scheduler when exiting the app
    atexit.register(lambda: scheduler.shutdown())

# Start the scheduler
schedule_fetcher()

# ============= DEBUG ROUTE =============
@app.route('/debug')
def debug():
    """Debug information"""
    try:
        conn = get_db_connection()
        
        # Get counts
        total_posts = conn.execute("SELECT COUNT(*) FROM posts").fetchone()[0]
        published_posts = conn.execute("SELECT COUNT(*) FROM posts WHERE is_published = 1").fetchone()[0]
        categories = conn.execute("SELECT COUNT(*) FROM categories").fetchone()[0]
        
        # Latest posts
        latest_posts = conn.execute(
            "SELECT title, created_at, source_name FROM posts ORDER BY created_at DESC LIMIT 5"
        ).fetchall()
        
        conn.close()
        
        return jsonify({
            'status': 'ok',
            'database_path': get_db_path(),
            'database_exists': os.path.exists(get_db_path()),
            'posts': {
                'total': total_posts,
                'published': published_posts,
                'latest': [dict(post) for post in latest_posts]
            },
            'categories': categories,
            'sources': len(fetcher.NEWS_SOURCES),
            'fetcher': {
                'is_fetching': fetcher.is_fetching,
                'last_fetch_time': fetcher.last_fetch_time.isoformat() if fetcher.last_fetch_time else None,
                'last_fetch_count': fetcher.last_fetch_count
            },
            'config': {
                'update_interval': FlaskConfig.UPDATE_INTERVAL_MINUTES,
                'site_url': FlaskConfig.SITE_URL,
                'debug': FlaskConfig.DEBUG,
                'port': FlaskConfig.PORT
            }
        })
        
    except Exception as e:
        return jsonify({'status': 'error', 'error': str(e)})

# ============= START APP =============
if __name__ == '__main__':
    print(f"🌐 Site URL: {FlaskConfig.SITE_URL}")
    print(f"🔐 Admin: {FlaskConfig.SITE_URL}/admin/login")
    print(f"📧 Contact: {FlaskConfig.CONTACT_EMAIL}")
    print(f"📱 Phone: {FlaskConfig.CONTACT_PHONE}")
    print(f"📊 Sources: {len(fetcher.NEWS_SOURCES)} active")
    print(f"⏰ Auto-update: Every {FlaskConfig.UPDATE_INTERVAL_MINUTES} minutes")
    print(f"🗄️ Database: {get_db_path()}")
    print("=" * 60)
    
    # Run the app
    port = int(os.environ.get('PORT', 5000))
    app.run(
        debug=FlaskConfig.DEBUG,
        host='0.0.0.0',
        port=port,
        threaded=True,
        use_reloader=False  # Disable reloader for background threads
    )