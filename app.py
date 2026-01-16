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
import atexit
import requests
from urllib.parse import urlparse, quote
import hashlib

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
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-key-change-me-in-production-2024')
    SITE_NAME = "Mzansi Insights"
    SITE_DESCRIPTION = "South African News & Updates - Aggregated from Trusted Sources"
    POSTS_PER_PAGE = 12
    ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME', 'admin')
    ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'admin123')
    
    # Adsense IDs
    ADSENSE_ID = os.environ.get('ADSENSE_ID', 'ca-pub-0000000000000000')
    
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

# ============= DATABASE SETUP =============
def get_db_path():
    """Get database path"""
    if os.environ.get('RENDER'):
        # Render persistent storage
        db_dir = '/opt/render/project/src/data'
    else:
        # Local development
        db_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
    
    try:
        if not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)
        return os.path.join(db_dir, 'posts.db')
    except:
        return 'posts.db'

def setup_database():
    """Setup database tables"""
    logger.info("Setting up database...")
    
    try:
        db_path = get_db_path()
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
            pub_date TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (category_id) REFERENCES categories(id)
        )''')
        
        # Indexes
        c.execute('CREATE INDEX IF NOT EXISTS idx_posts_slug ON posts(slug)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_posts_category ON posts(category_id)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_posts_pub_date ON posts(pub_date)')
        
        # Create admin user
        c.execute("SELECT COUNT(*) FROM users WHERE username = ?", (FlaskConfig.ADMIN_USERNAME,))
        if c.fetchone()[0] == 0:
            pwd_hash = generate_password_hash(FlaskConfig.ADMIN_PASSWORD)
            c.execute("INSERT INTO users (username, password_hash) VALUES (?, ?)", 
                     (FlaskConfig.ADMIN_USERNAME, pwd_hash))
            logger.info("Admin user created")
        
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
        
        # Insert categories
        for name, slug, desc, icon, color in CATEGORIES:
            c.execute("SELECT COUNT(*) FROM categories WHERE slug = ?", (slug,))
            if c.fetchone()[0] == 0:
                c.execute("INSERT INTO categories (name, slug, description, icon, color) VALUES (?, ?, ?, ?, ?)",
                         (name, slug, desc, icon, color))
                logger.info(f"Category created: {name}")
        
        # Check if we need sample posts
        c.execute("SELECT COUNT(*) FROM posts")
        if c.fetchone()[0] == 0:
            logger.info("Adding sample posts...")
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
                
                c.execute("SELECT id FROM categories WHERE slug = ?", (category,))
                category_row = c.fetchone()
                category_id = category_row[0] if category_row else 1
                
                c.execute('''INSERT INTO posts 
                    (title, slug, content, excerpt, image_url, source_url, 
                     category_id, category, source_name, views, is_published, pub_date)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, datetime('now'))''',
                    (title, slug, content, excerpt, image, '#', 
                     category_id, category, source, random.randint(50, 500)))
            
            logger.info("Sample posts added")
        
        conn.commit()
        conn.close()
        logger.info("Database setup complete")
        return True
        
    except Exception as e:
        logger.error(f"Database setup failed: {e}")
        return False

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
        self.last_fetch = None
        
        # News Sources with better configuration
        self.NEWS_SOURCES = [
            {
                'name': 'News24',
                'url': 'https://www.news24.com/feed',
                'category': 'news',
                'color': '#4361ee',
                'icon': 'newspaper',
                'enabled': True
            },
            {
                'name': 'TimesLive',
                'url': 'https://www.timeslive.co.za/feed/',
                'category': 'news',
                'color': '#7209b7',
                'icon': 'newspaper',
                'enabled': True
            },
            {
                'name': 'IOL',
                'url': 'https://www.iol.co.za/rss',
                'category': 'news',
                'color': '#e63946',
                'icon': 'newspaper',
                'enabled': True
            },
            {
                'name': 'Moneyweb',
                'url': 'https://www.moneyweb.co.za/feed/',
                'category': 'business',
                'color': '#1dd1a1',
                'icon': 'chart-line',
                'enabled': True
            },
            {
                'name': 'BusinessTech',
                'url': 'https://businesstech.co.za/news/feed/',
                'category': 'business',
                'color': '#3742fa',
                'icon': 'laptop-code',
                'enabled': True
            },
            {
                'name': 'Daily Maverick',
                'url': 'https://www.dailymaverick.co.za/feed/',
                'category': 'news',
                'color': '#f77f00',
                'icon': 'newspaper',
                'enabled': True
            },
            {
                'name': 'MyBroadband',
                'url': 'https://mybroadband.co.za/news/feed',
                'category': 'technology',
                'color': '#9b59b6',
                'icon': 'wifi',
                'enabled': True
            },
            {
                'name': 'TechCentral',
                'url': 'https://techcentral.co.za/feed/',
                'category': 'technology',
                'color': '#3498db',
                'icon': 'microchip',
                'enabled': True
            },
            {
                'name': 'Sport24',
                'url': 'https://www.sport24.co.za/feed',
                'category': 'sports',
                'color': '#2ecc71',
                'icon': 'running',
                'enabled': True
            },
            {
                'name': 'The Citizen',
                'url': 'https://www.citizen.co.za/feed/',
                'category': 'news',
                'color': '#d62828',
                'icon': 'newspaper',
                'enabled': True
            },
        ]
    
    def fetch_feed(self, source):
        """Fetch a single RSS feed"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'application/rss+xml, application/xml, text/xml, */*',
                'Accept-Language': 'en-US,en;q=0.9',
            }
            
            # Try to fetch with requests first for better error handling
            try:
                response = requests.get(source['url'], headers=headers, timeout=10)
                if response.status_code == 200:
                    feed = feedparser.parse(response.content)
                else:
                    feed = feedparser.parse(source['url'], request_headers=headers, timeout=10)
            except:
                feed = feedparser.parse(source['url'], request_headers=headers, timeout=10)
            
            return feed
        
        except Exception as e:
            logger.warning(f"Error fetching {source['name']}: {e}")
            return None
    
    def fetch_and_save(self):
        """Fetch and save articles"""
        if self.is_fetching:
            return 0
        
        self.is_fetching = True
        total_saved = 0
        
        try:
            logger.info("Starting content fetch...")
            conn = get_db_connection()
            
            for source in [s for s in self.NEWS_SOURCES if s.get('enabled', True)]:
                try:
                    feed = self.fetch_feed(source)
                    if not feed or not feed.entries:
                        continue
                    
                    saved = 0
                    for entry in feed.entries[:8]:  # Limit per source
                        try:
                            title = entry.get('title', '').strip()
                            if not title:
                                continue
                            
                            # Generate unique slug
                            slug_base = re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')
                            slug_hash = hashlib.md5(title.encode()).hexdigest()[:8]
                            slug = f"{slug_base[:80]}-{slug_hash}"
                            
                            # Check if exists
                            existing = conn.execute(
                                "SELECT id FROM posts WHERE slug = ?", (slug,)
                            ).fetchone()
                            if existing:
                                continue
                            
                            # Get content
                            content = entry.get('summary', entry.get('description', ''))
                            if content:
                                content = re.sub(r'<[^>]+>', '', content)
                                content = content.replace('&nbsp;', ' ').replace('&amp;', '&')
                                content = ' '.join(content.split())
                            else:
                                content = title
                            
                            excerpt = content[:200] + '...' if len(content) > 200 else content
                            
                            # Get image
                            image_url = self.extract_image(entry, source['category'])
                            
                            # Get category ID
                            cat_row = conn.execute(
                                "SELECT id FROM categories WHERE slug = ?", (source['category'],)
                            ).fetchone()
                            category_id = cat_row[0] if cat_row else 1
                            
                            # Insert
                            conn.execute('''INSERT INTO posts 
                                (title, slug, content, excerpt, image_url, source_url, 
                                 category_id, category, source_name, views, is_published, pub_date)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, datetime('now'))''',
                                (title, slug, content, excerpt, image_url,
                                 entry.get('link', '#'), category_id, source['category'],
                                 source['name'], random.randint(10, 100)))
                            
                            saved += 1
                            total_saved += 1
                            
                        except Exception as e:
                            continue
                    
                    if saved > 0:
                        logger.info(f"  {source['name']}: {saved} new")
                    
                except Exception as e:
                    logger.warning(f"Failed {source['name']}: {e}")
                    continue
            
            conn.commit()
            conn.close()
            
            self.last_fetch = datetime.now()
            logger.info(f"Fetch complete: {total_saved} new articles")
            return total_saved
            
        except Exception as e:
            logger.error(f"Fetch error: {e}")
            return 0
        finally:
            self.is_fetching = False
    
    def extract_image(self, entry, category):
        """Extract image from entry"""
        # Check various image sources
        image_sources = [
            lambda: entry.get('media_content', [{}])[0].get('url', '') if hasattr(entry, 'media_content') and entry.media_content else '',
            lambda: entry.get('media_thumbnail', [{}])[0].get('url', '') if hasattr(entry, 'media_thumbnail') and entry.media_thumbnail else '',
            lambda: entry.get('enclosures', [{}])[0].get('href', '') if hasattr(entry, 'enclosures') and entry.enclosures and entry.enclosures[0].get('type', '').startswith('image/') else '',
        ]
        
        for source in image_sources:
            img = source()
            if img and img.startswith('http'):
                return img
        
        # Fallback images
        fallbacks = {
            'news': 'https://images.unsplash.com/photo-1588681664899-f142ff2dc9b1?w=800&auto=format&fit=crop',
            'business': 'https://images.unsplash.com/photo-1497366754035-f200968a6e72?w=800&auto=format&fit=crop',
            'sports': 'https://images.unsplash.com/photo-1546519638-68e109498ffc?w=800&auto=format&fit=crop',
            'technology': 'https://images.unsplash.com/photo-1519389950473-47ba0277781c?w=800&auto=format&fit=crop',
            'entertainment': 'https://images.unsplash.com/photo-1493225457124-a3eb161ffa5f?w=800&auto=format&fit=crop',
        }
        
        return fallbacks.get(category, fallbacks['news'])

# ============= FLASK APP =============
app = Flask(__name__)
app.config.from_object(FlaskConfig)

print("=" * 60)
print("🇿🇦 MZANSI INSIGHTS - STARTING...")
print("=" * 60)

# Setup database
setup_database()

# Initialize fetcher
fetcher = ContentFetcher()

# Start initial fetch
print("Fetching initial content...")
fetcher.fetch_and_save()

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
    try:
        if isinstance(date_str, str):
            post_date = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
        else:
            return "Recently"
        
        diff = datetime.now() - post_date
        
        if diff.days > 365:
            return f"{diff.days // 365}y ago"
        elif diff.days > 30:
            return f"{diff.days // 30}mo ago"
        elif diff.days > 0:
            return f"{diff.days}d ago"
        elif diff.seconds > 3600:
            return f"{diff.seconds // 3600}h ago"
        elif diff.seconds > 60:
            return f"{diff.seconds // 60}m ago"
        return "Just now"
    except:
        return "Recently"

def prepare_post(post_row):
    """Prepare post for template"""
    if not post_row:
        return None
    
    post = dict(post_row)
    post['formatted_date'] = get_time_ago(post.get('pub_date') or post.get('created_at', ''))
    
    # Get category info
    try:
        conn = get_db_connection()
        category = conn.execute(
            "SELECT * FROM categories WHERE id = ?", 
            (post.get('category_id', 1),)
        ).fetchone()
        conn.close()
        
        if category:
            post['category_ref'] = dict(category)
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

# ============= ROUTES =============
@app.route('/')
def index():
    """Home page"""
    try:
        conn = get_db_connection()
        
        # Latest posts
        posts_raw = conn.execute(
            "SELECT * FROM posts WHERE is_published = 1 ORDER BY pub_date DESC LIMIT 12"
        ).fetchall()
        posts = [prepare_post(row) for row in posts_raw]
        
        # Trending posts
        trending_raw = conn.execute(
            "SELECT * FROM posts WHERE is_published = 1 ORDER BY views DESC LIMIT 6"
        ).fetchall()
        trending_posts = [prepare_post(row) for row in trending_raw]
        
        # Categories
        categories = []
        cat_rows = conn.execute("SELECT * FROM categories ORDER BY name").fetchall()
        for cat in cat_rows:
            cat_dict = dict(cat)
            post_count = conn.execute(
                "SELECT COUNT(*) FROM posts WHERE category_id = ? AND is_published = 1", 
                (cat_dict['id'],)
            ).fetchone()[0]
            cat_dict['post_count'] = post_count
            categories.append(cat_dict)
        
        conn.close()
        
        return render_template('index.html',
                             posts=posts,
                             trending_posts=trending_posts,
                             categories=categories,
                             sources=fetcher.NEWS_SOURCES,
                             config=FlaskConfig,
                             has_posts=len(posts) > 0,
                             now=datetime.now())
                             
    except Exception as e:
        logger.error(f"Home error: {e}")
        return render_template('index.html',
                             posts=[],
                             trending_posts=[],
                             categories=[],
                             sources=fetcher.NEWS_SOURCES,
                             config=FlaskConfig,
                             has_posts=False,
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
        
        # Get posts
        posts_raw = conn.execute(
            "SELECT * FROM posts WHERE category_id = ? AND is_published = 1 ORDER BY pub_date DESC LIMIT 50",
            (category['id'],)
        ).fetchall()
        posts = [prepare_post(row) for row in posts_raw]
        
        # Get all categories for sidebar
        categories = []
        cat_rows = conn.execute("SELECT * FROM categories ORDER BY name").fetchall()
        for cat in cat_rows:
            cat_dict = dict(cat)
            post_count = conn.execute(
                "SELECT COUNT(*) FROM posts WHERE category_id = ? AND is_published = 1", 
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
        logger.error(f"Category error: {e}")
        return render_template('404.html', config=FlaskConfig), 404

@app.route('/post/<slug>')
def post_detail(slug):
    """Post detail page"""
    try:
        conn = get_db_connection()
        
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
            total_row = conn.execute(
                "SELECT COUNT(*) FROM posts WHERE (title LIKE ? OR content LIKE ?) AND is_published = 1",
                (search_term, search_term)
            ).fetchone()
            total = total_row[0] if total_row else 0
            
            # Get paginated results
            offset = (page - 1) * per_page
            posts_raw = conn.execute(
                "SELECT * FROM posts WHERE (title LIKE ? OR content LIKE ?) AND is_published = 1 ORDER BY pub_date DESC LIMIT ? OFFSET ?",
                (search_term, search_term, per_page, offset)
            ).fetchall()
            posts = [prepare_post(row) for row in posts_raw]
        
        # Get categories for sidebar
        categories = []
        cat_rows = conn.execute("SELECT * FROM categories ORDER BY name").fetchall()
        for cat in cat_rows:
            categories.append(dict(cat))
        
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
                             categories=[],
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
        
        # Get sources with article counts
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
                    'last_fetch': fetcher.last_fetch.strftime('%Y-%m-%d %H:%M') if fetcher.last_fetch else 'Never'
                })
        
        # Get categories for sidebar
        categories = []
        cat_rows = conn.execute("SELECT * FROM categories ORDER BY name").fetchall()
        for cat in cat_rows:
            categories.append(dict(cat))
        
        conn.close()
        
        return render_template('sources.html',
                             sources=sources_list,
                             categories=categories,
                             config=FlaskConfig,
                             now=datetime.now())
                             
    except Exception as e:
        logger.error(f"Sources error: {e}")
        return render_template('sources.html',
                             sources=fetcher.NEWS_SOURCES,
                             categories=[],
                             config=FlaskConfig,
                             now=datetime.now())

@app.route('/about')
def about():
    """About page"""
    try:
        conn = get_db_connection()
        categories = [dict(cat) for cat in conn.execute("SELECT * FROM categories ORDER BY name").fetchall()]
        conn.close()
    except:
        categories = []
    
    return render_template('about.html',
                         categories=categories,
                         config=FlaskConfig,
                         now=datetime.now())

@app.route('/disclaimer')
def disclaimer():
    """Disclaimer page"""
    try:
        conn = get_db_connection()
        categories = [dict(cat) for cat in conn.execute("SELECT * FROM categories ORDER BY name").fetchall()]
        conn.close()
    except:
        categories = []
    
    return render_template('disclaimer.html',
                         categories=categories,
                         config=FlaskConfig,
                         now=datetime.now())

# Static pages
@app.route('/privacy')
def privacy():
    try:
        conn = get_db_connection()
        categories = [dict(cat) for cat in conn.execute("SELECT * FROM categories ORDER BY name").fetchall()]
        conn.close()
    except:
        categories = []
    
    return render_template('privacy.html',
                         categories=categories,
                         config=FlaskConfig,
                         now=datetime.now())

@app.route('/terms')
def terms():
    try:
        conn = get_db_connection()
        categories = [dict(cat) for cat in conn.execute("SELECT * FROM categories ORDER BY name").fetchall()]
        conn.close()
    except:
        categories = []
    
    return render_template('terms.html',
                         categories=categories,
                         config=FlaskConfig,
                         now=datetime.now())

@app.route('/contact')
def contact():
    try:
        conn = get_db_connection()
        categories = [dict(cat) for cat in conn.execute("SELECT * FROM categories ORDER BY name").fetchall()]
        conn.close()
    except:
        categories = []
    
    return render_template('contact.html',
                         categories=categories,
                         config=FlaskConfig,
                         now=datetime.now())

@app.route('/sitemap')
def sitemap():
    try:
        conn = get_db_connection()
        categories = [dict(cat) for cat in conn.execute("SELECT * FROM categories ORDER BY name").fetchall()]
        posts = conn.execute("SELECT slug, title, pub_date FROM posts WHERE is_published = 1 ORDER BY pub_date DESC LIMIT 100").fetchall()
        conn.close()
        
        return render_template('sitemap.html',
                             categories=categories,
                             posts=posts,
                             config=FlaskConfig,
                             now=datetime.now())
    except:
        return render_template('sitemap.html',
                             categories=[],
                             posts=[],
                             config=FlaskConfig,
                             now=datetime.now())

# API endpoints
@app.route('/api/live-news')
def live_news():
    """Live news API for ticker"""
    try:
        conn = get_db_connection()
        posts_raw = conn.execute(
            "SELECT p.*, c.color, c.name as category_name FROM posts p LEFT JOIN categories c ON p.category_id = c.id WHERE p.is_published = 1 ORDER BY p.pub_date DESC LIMIT 10"
        ).fetchall()
        conn.close()
        
        articles = []
        for post in posts_raw:
            post_dict = dict(post)
            articles.append({
                'title': post_dict['title'][:80] + '...' if len(post_dict['title']) > 80 else post_dict['title'],
                'category': post_dict.get('category_name', 'News'),
                'color': post_dict.get('color', '#4361ee'),
                'time_ago': get_time_ago(post_dict.get('pub_date', ''))
            })
        
        return jsonify({'status': 'success', 'articles': articles})
        
    except Exception as e:
        return jsonify({'status': 'error', 'articles': []})

@app.route('/api/fetch-now')
def api_fetch_now():
    """Manually trigger fetch"""
    if fetcher.is_fetching:
        return jsonify({'status': 'already_fetching', 'message': 'Fetch already in progress'})
    
    threading.Thread(target=fetcher.fetch_and_save, daemon=True).start()
    return jsonify({'status': 'started', 'message': 'Content fetch started in background'})

@app.route('/api/stats')
def api_stats():
    """Site statistics"""
    try:
        conn = get_db_connection()
        
        stats = {
            'posts': conn.execute("SELECT COUNT(*) FROM posts WHERE is_published = 1").fetchone()[0],
            'total_views': conn.execute("SELECT SUM(views) FROM posts").fetchone()[0] or 0,
            'categories': conn.execute("SELECT COUNT(*) FROM categories").fetchone()[0],
            'sources': len([s for s in fetcher.NEWS_SOURCES if s.get('enabled', True)]),
            'last_fetch': fetcher.last_fetch.isoformat() if fetcher.last_fetch else None,
            'status': 'online',
            'time': datetime.now().strftime('%H:%M:%S')
        }
        
        conn.close()
        return jsonify(stats)
        
    except Exception as e:
        return jsonify({'status': 'error', 'error': str(e)})

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
        'sources': len(fetcher.NEWS_SOURCES),
        'fetching_status': 'Active' if fetcher.is_fetching else 'Idle'
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
    threading.Thread(target=fetcher.fetch_and_save, daemon=True).start()
    flash('Content fetch started in background!', 'info')
    return redirect('/admin/dashboard')

@app.route('/admin/logout')
@login_required
def admin_logout():
    logout_user()
    flash('Logged out successfully', 'info')
    return redirect('/')

# Error handlers
@app.errorhandler(404)
def not_found(e):
    return render_template('404.html', config=FlaskConfig), 404

@app.errorhandler(500)
def server_error(e):
    logger.error(f"500 error: {e}")
    return render_template('500.html', config=FlaskConfig), 500

# ============= BACKGROUND FETCHER =============
def start_background_fetcher():
    """Start periodic fetching"""
    def fetch_loop():
        while True:
            try:
                time.sleep(FlaskConfig.UPDATE_INTERVAL_MINUTES * 60)
                logger.info("Running scheduled fetch...")
                fetcher.fetch_and_save()
            except Exception as e:
                logger.error(f"Background fetch error: {e}")
                time.sleep(300)
    
    thread = threading.Thread(target=fetch_loop, daemon=True)
    thread.start()
    logger.info("Background fetcher started")

# Start background fetcher
start_background_fetcher()

# ============= START APP =============
if __name__ == '__main__':
    print(f"🌐 Site URL: {FlaskConfig.SITE_URL}")
    print(f"📧 Contact: {FlaskConfig.CONTACT_EMAIL}")
    print(f"📊 Sources: {len(fetcher.NEWS_SOURCES)}")
    print(f"⏰ Updates every {FlaskConfig.UPDATE_INTERVAL_MINUTES} minutes")
    print("=" * 60)
    
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=FlaskConfig.DEBUG, host='0.0.0.0', port=port, threaded=True)