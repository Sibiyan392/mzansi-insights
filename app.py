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
    
    # Adsense IDs (EMPTY - YOU MUST GET YOUR OWN FROM GOOGLE)
    ADSENSE_ID = os.environ.get('ADSENSE_ID', 'YOUR_ADSENSE_ID_HERE')
    ADSENSE_SLOT_BANNER = "1234567890"
    ADSENSE_SLOT_INARTICLE = "1234567891"
    ADSENSE_SLOT_SQUARE = "1234567892"
    ADSENSE_SLOT_SEARCH = "1234567893"
    ADSENSE_SLOT_SOURCES = "1234567894"
    ADSENSE_SLOT_CATEGORY = "1234567895"
    ADSENSE_SLOT_INFEED = "1234567896"
    
    # Adsense Compliance Requirements
    CONTACT_EMAIL = os.environ.get('CONTACT_EMAIL', 'contact@mzansi-insights.co.za')
    CONTACT_PHONE = os.environ.get('CONTACT_PHONE', '+27 11 123 4567')
    PHYSICAL_ADDRESS = os.environ.get('PHYSICAL_ADDRESS', 'Johannesburg, South Africa')
    SITE_URL = os.environ.get('SITE_URL', 'https://mzansi-insights.onrender.com')
    
    # Content Update Configuration
    UPDATE_INTERVAL_MINUTES = int(os.environ.get('UPDATE_INTERVAL_MINUTES', 30))
    MAX_SOURCES = 15
    
    # ENHANCED News Sources Configuration with MORE sources
    NEWS_SOURCES = [
        {
            'name': 'News24',
            'url': 'https://www.news24.com/feed',
            'category': 'news',
            'country': 'ZA',
            'enabled': True,
            'color': '#4361ee',
            'icon': 'newspaper'
        },
        {
            'name': 'TimesLive',
            'url': 'https://www.timeslive.co.za/feed/',
            'category': 'news',
            'country': 'ZA',
            'enabled': True,
            'color': '#7209b7',
            'icon': 'newspaper'
        },
        {
            'name': 'Moneyweb',
            'url': 'https://www.moneyweb.co.za/feed/',
            'category': 'business',
            'country': 'ZA',
            'enabled': True,
            'color': '#1dd1a1',
            'icon': 'chart-line'
        },
        {
            'name': 'BusinessTech',
            'url': 'https://businesstech.co.za/news/feed/',
            'category': 'business',
            'country': 'ZA',
            'enabled': True,
            'color': '#3742fa',
            'icon': 'laptop-code'
        },
        {
            'name': 'TechCentral',
            'url': 'https://techcentral.co.za/feed/',
            'category': 'technology',
            'country': 'ZA',
            'enabled': True,
            'color': '#3498db',
            'icon': 'microchip'
        },
        {
            'name': 'MyBroadband',
            'url': 'https://mybroadband.co.za/news/feed',
            'category': 'technology',
            'country': 'ZA',
            'enabled': True,
            'color': '#9b59b6',
            'icon': 'wifi'
        },
        {
            'name': 'SA Government',
            'url': 'https://www.gov.za/rss.xml',
            'category': 'government',
            'country': 'ZA',
            'enabled': True,
            'color': '#2c3e50',
            'icon': 'landmark'
        },
        {
            'name': 'Eskom',
            'url': 'https://www.eskom.co.za/rss/',
            'category': 'news',
            'country': 'ZA',
            'enabled': True,
            'color': '#ff9f43',
            'icon': 'bolt'
        },
        {
            'name': 'SA People News',
            'url': 'https://www.sapeople.com/feed/',
            'category': 'entertainment',
            'country': 'ZA',
            'enabled': True,
            'color': '#ef476f',
            'icon': 'users'
        },
        {
            'name': 'SAPS News',
            'url': 'https://www.saps.gov.za/news/rss.php',
            'category': 'news',
            'country': 'ZA',
            'enabled': True,
            'color': '#34495e',
            'icon': 'shield-alt'
        },
        {
            'name': 'Department of Health',
            'url': 'https://www.health.gov.za/feed/',
            'category': 'health',
            'country': 'ZA',
            'enabled': True,
            'color': '#e74c3c',
            'icon': 'heartbeat'
        },
        {
            'name': 'Sport24',
            'url': 'https://www.sport24.co.za/feed',
            'category': 'sports',
            'country': 'ZA',
            'enabled': True,
            'color': '#2ecc71',
            'icon': 'running'
        }
    ]

# ============= ENHANCED CATEGORIES =============
CATEGORY_DEFINITIONS = {
    'news': {
        'name': 'News',
        'slug': 'news',
        'description': 'Breaking news, current events, and daily updates from across South Africa',
        'icon': 'newspaper',
        'color': '#4361ee',
        'keywords': ['news', 'breaking', 'update', 'latest', 'current', 'today']
    },
    'jobs': {
        'name': 'Jobs',
        'slug': 'jobs',
        'description': 'Employment opportunities, vacancies, career development, and job market insights',
        'icon': 'briefcase',
        'color': '#06d6a0',
        'keywords': ['job', 'vacancy', 'employment', 'career', 'hiring', 'work', 'position', 'recruitment']
    },
    'grants': {
        'name': 'Grants',
        'slug': 'grants',
        'description': 'SASSA grants, government funding, social assistance, and financial support programs',
        'icon': 'hand-holding-usd',
        'color': '#ff9e00',
        'keywords': ['grant', 'sassa', 'funding', 'assistance', 'support', 'welfare', 'subsidy']
    },
    'entertainment': {
        'name': 'Entertainment',
        'slug': 'entertainment',
        'description': 'Movies, music, celebrities, arts, culture, and entertainment industry news',
        'icon': 'film',
        'color': '#ef476f',
        'keywords': ['entertainment', 'movie', 'music', 'celebrity', 'film', 'show', 'art', 'culture']
    },
    'business': {
        'name': 'Business',
        'slug': 'business',
        'description': 'Business news, economic updates, market analysis, and financial insights',
        'icon': 'chart-line',
        'color': '#7209b7',
        'keywords': ['business', 'economy', 'market', 'finance', 'trade', 'investment', 'company', 'corporate']
    },
    'technology': {
        'name': 'Technology',
        'slug': 'technology',
        'description': 'Tech news, innovation, gadgets, software, internet, and digital transformation',
        'icon': 'laptop-code',
        'color': '#3498db',
        'keywords': ['tech', 'technology', 'digital', 'software', 'internet', 'innovation', 'gadget', 'app']
    },
    'sports': {
        'name': 'Sports',
        'slug': 'sports',
        'description': 'Sports news, match results, fixtures, athlete profiles, and sporting events',
        'icon': 'running',
        'color': '#2ecc71',
        'keywords': ['sport', 'rugby', 'soccer', 'cricket', 'football', 'athlete', 'game', 'match']
    },
    'health': {
        'name': 'Health',
        'slug': 'health',
        'description': 'Health news, medical updates, wellness tips, and healthcare information',
        'icon': 'heartbeat',
        'color': '#e74c3c',
        'keywords': ['health', 'medical', 'wellness', 'healthcare', 'doctor', 'hospital', 'disease', 'treatment']
    },
    'government': {
        'name': 'Government',
        'slug': 'government',
        'description': 'Government announcements, policy updates, legislation, and public services',
        'icon': 'landmark',
        'color': '#2c3e50',
        'keywords': ['government', 'policy', 'legislation', 'parliament', 'minister', 'department', 'public']
    },
    'education': {
        'name': 'Education',
        'slug': 'education',
        'description': 'Education news, school updates, university information, and learning resources',
        'icon': 'graduation-cap',
        'color': '#9b59b6',
        'keywords': ['education', 'school', 'university', 'student', 'learning', 'teacher', 'academic']
    }
}

# ============= DATABASE =============
def get_db_path():
    """Get the database path that works in both local and Render environments"""
    if 'RENDER' in os.environ:
        # On Render, use a persistent path
        return '/tmp/posts.db'
    else:
        # Local development
        os.makedirs('data', exist_ok=True)
        return 'data/posts.db'

def setup_database():
    """Initialize database with proper tables and categories"""
    print("🔄 Setting up database...")
    db_path = get_db_path()
    
    # Create directory if it doesn't exist
    if '/' in db_path:
        db_dir = os.path.dirname(db_path)
        os.makedirs(db_dir, exist_ok=True)
    
    conn = sqlite3.connect(db_path)
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
            description TEXT,
            icon TEXT,
            color TEXT
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
            source_name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (category_id) REFERENCES categories(id)
        )
    ''')
    
    # Create indexes for better performance
    c.execute('CREATE INDEX IF NOT EXISTS idx_posts_slug ON posts(slug)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_posts_category ON posts(category_id)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_posts_created ON posts(created_at)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_posts_views ON posts(views)')
    
    # Insert admin user
    c.execute("SELECT COUNT(*) FROM users WHERE username = 'admin'")
    if c.fetchone()[0] == 0:
        pwd_hash = generate_password_hash(FlaskConfig.ADMIN_PASSWORD)
        c.execute("INSERT INTO users (username, password_hash) VALUES (?, ?)", 
                 ('admin', pwd_hash))
        print("✅ Created admin user")
    
    # Insert all categories from CATEGORY_DEFINITIONS
    categories_added = 0
    for slug, cat_data in CATEGORY_DEFINITIONS.items():
        c.execute("SELECT COUNT(*) FROM categories WHERE slug = ?", (slug,))
        if c.fetchone()[0] == 0:
            c.execute("""
                INSERT INTO categories (name, slug, description, icon, color) 
                VALUES (?, ?, ?, ?, ?)
            """, (cat_data['name'], cat_data['slug'], cat_data['description'], 
                  cat_data['icon'], cat_data['color']))
            categories_added += 1
    
    conn.commit()
    conn.close()
    print(f"✅ Database setup complete - Added {categories_added} categories")
    return True

def get_db_connection():
    """Get database connection with row factory"""
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

# ============= INTELLIGENT CATEGORY DETECTION =============
def detect_category(title, content, source_category='news'):
    """Enhanced category detection using keywords and source category"""
    title_lower = title.lower()
    content_lower = content.lower() if content else ''
    combined_text = title_lower + ' ' + content_lower
    
    # Score each category
    category_scores = {}
    for slug, cat_data in CATEGORY_DEFINITIONS.items():
        score = 0
        for keyword in cat_data['keywords']:
            if keyword in title_lower:
                score += 3  # Title matches are weighted more
            if keyword in content_lower:
                score += 1  # Content matches are weighted less
        category_scores[slug] = score
    
    # Boost score for source category
    if source_category in category_scores:
        category_scores[source_category] += 2
    
    # Get category with highest score
    best_category = max(category_scores.items(), key=lambda x: x[1])
    
    # If no good match, use source category
    if best_category[1] < 2:
        return source_category
    
    return best_category[0]

# ============= CONTENT UPDATER CLASS =============
class ContentUpdater:
    def __init__(self):
        self.is_running = False
        self.update_thread = None
    
    def generate_slug(self, title):
        """Generate URL-friendly slug from title"""
        slug = re.sub(r'[^a-zA-Z0-9\s-]', '', title.lower())
        slug = re.sub(r'\s+', '-', slug)
        slug = slug[:100]  # Limit length
        return slug or 'post-' + str(int(time.time()))
    
    def extract_image_url(self, entry):
        """Extract image URL from feed entry"""
        # Try media:content
        if hasattr(entry, 'media_content') and entry.media_content:
            return entry.media_content[0].get('url', '')
        
        # Try media:thumbnail
        if hasattr(entry, 'media_thumbnail') and entry.media_thumbnail:
            return entry.media_thumbnail[0].get('url', '')
        
        # Try enclosures
        if hasattr(entry, 'enclosures') and entry.enclosures:
            for enclosure in entry.enclosures:
                if enclosure.get('type', '').startswith('image/'):
                    return enclosure.get('href', '')
        
        # Try to find image in content
        if hasattr(entry, 'content'):
            content = entry.content[0].value if entry.content else ''
            img_match = re.search(r'<img[^>]+src="([^"]+)"', content)
            if img_match:
                return img_match.group(1)
        
        return None
    
    def clean_content(self, text):
        """Clean and format content"""
        if not text:
            return ""
        
        # Remove HTML tags
        text = re.sub(r'<[^>]+>', '', text)
        
        # Decode HTML entities
        text = text.replace('&nbsp;', ' ')
        text = text.replace('&amp;', '&')
        text = text.replace('&lt;', '<')
        text = text.replace('&gt;', '>')
        text = text.replace('&quot;', '"')
        
        # Remove extra whitespace
        text = ' '.join(text.split())
        
        return text[:500]  # Limit excerpt length
    
    def fetch_from_source(self, source):
        """Fetch articles from a single RSS source"""
        try:
            print(f"📡 Fetching from {source['name']}...")
            feed = feedparser.parse(source['url'])
            
            if not feed.entries:
                print(f"⚠️ No entries found for {source['name']}")
                return []
            
            articles = []
            for entry in feed.entries[:10]:  # Get latest 10 articles
                title = entry.get('title', 'Untitled')
                link = entry.get('link', '')
                
                # Get content
                content = ''
                if hasattr(entry, 'summary'):
                    content = self.clean_content(entry.summary)
                elif hasattr(entry, 'description'):
                    content = self.clean_content(entry.description)
                elif hasattr(entry, 'content'):
                    content = self.clean_content(entry.content[0].value if entry.content else '')
                
                # Get publish date
                pub_date = entry.get('published_parsed') or entry.get('updated_parsed')
                
                article = {
                    'title': title,
                    'content': content,
                    'excerpt': content[:300] + '...' if len(content) > 300 else content,
                    'url': link,
                    'image_url': self.extract_image_url(entry),
                    'source_name': source['name'],
                    'source_category': source['category'],
                    'pub_date': pub_date
                }
                
                articles.append(article)
            
            print(f"✅ Fetched {len(articles)} articles from {source['name']}")
            return articles
            
        except Exception as e:
            print(f"❌ Error fetching from {source['name']}: {e}")
            return []
    
    def save_article(self, article, conn):
        """Save article to database with intelligent category detection"""
        try:
            slug = self.generate_slug(article['title'])
            
            # Check if article already exists
            existing = conn.execute("SELECT id FROM posts WHERE slug = ?", (slug,)).fetchone()
            if existing:
                return False
            
            # Detect category intelligently
            detected_category = detect_category(
                article['title'], 
                article['content'], 
                article['source_category']
            )
            
            # Get category ID
            category = conn.execute(
                "SELECT id FROM categories WHERE slug = ?", 
                (detected_category,)
            ).fetchone()
            
            category_id = category['id'] if category else 1  # Default to first category
            
            # Insert article
            conn.execute("""
                INSERT INTO posts (title, slug, content, excerpt, image_url, source_url, 
                                 category_id, source_name, is_auto_generated, views)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
            """, (
                article['title'],
                slug,
                article['content'],
                article['excerpt'],
                article['image_url'],
                article['url'],
                category_id,
                article['source_name'],
                random.randint(10, 500)  # Random initial views
            ))
            
            conn.commit()
            print(f"✅ Saved: {article['title'][:50]}... → {detected_category}")
            return True
            
        except Exception as e:
            print(f"❌ Error saving article: {e}")
            return False
    
    def update_content_database(self):
        """Main update function"""
        print("\n" + "="*70)
        print("🔄 STARTING CONTENT UPDATE")
        print("="*70)
        
        conn = get_db_connection()
        total_new = 0
        
        for source in FlaskConfig.NEWS_SOURCES:
            if not source.get('enabled', True):
                continue
            
            articles = self.fetch_from_source(source)
            
            for article in articles:
                if self.save_article(article, conn):
                    total_new += 1
            
            time.sleep(1)  # Be nice to servers
        
        conn.close()
        
        print("="*70)
        print(f"✅ UPDATE COMPLETE - Added {total_new} new articles")
        print("="*70 + "\n")
    
    def start_auto_updates(self):
        """Start automatic content updates"""
        def update_loop():
            while True:
                try:
                    self.update_content_database()
                    print(f"⏰ Next update in {FlaskConfig.UPDATE_INTERVAL_MINUTES} minutes...")
                    time.sleep(FlaskConfig.UPDATE_INTERVAL_MINUTES * 60)
                except Exception as e:
                    print(f"❌ Update error: {e}")
                    time.sleep(300)  # Wait 5 minutes on error
        
        if not self.is_running:
            self.is_running = True
            self.update_thread = threading.Thread(target=update_loop, daemon=True)
            self.update_thread.start()
            print("✅ Auto-update service started")

# ============= FLASK APP SETUP =============
app = Flask(__name__)
app.config.from_object(FlaskConfig)

# Initialize database when app starts
print("=" * 70)
print("🇿🇦 MZANSI INSIGHTS - ENHANCED VERSION 2.0")
print("=" * 70)
setup_database()

# Flask-Login setup
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
    user_data = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    if user_data:
        return User(user_data['id'], user_data['username'])
    return None

# Initialize content updater
content_updater = ContentUpdater()

# ============= HELPER FUNCTIONS =============
def get_time_ago(date_str):
    """Convert timestamp to human-readable time ago"""
    try:
        post_date = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
        now = datetime.now()
        diff = now - post_date
        
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
        else:
            return "Just now"
    except:
        return "Recently"

def convert_post_row(row):
    """Convert database row to dictionary with category info"""
    post_dict = dict(row)
    post_dict['formatted_date'] = get_time_ago(post_dict.get('created_at', ''))
    
    # Get category info
    conn = get_db_connection()
    category = conn.execute("SELECT * FROM categories WHERE id = ?", 
                           (post_dict.get('category_id', 1),)).fetchone()
    conn.close()
    
    if category:
        post_dict['category_ref'] = {
            'name': category['name'],
            'slug': category['slug'],
            'icon': category['icon'],
            'color': category['color']
        }
    else:
        # Fallback category
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
    """Homepage with latest posts"""
    try:
        conn = get_db_connection()
        
        # Get all categories with post counts
        categories = []
        for cat_row in conn.execute("SELECT * FROM categories ORDER BY name").fetchall():
            cat_dict = dict(cat_row)
            post_count = conn.execute(
                "SELECT COUNT(*) as count FROM posts WHERE category_id = ? AND is_published = 1",
                (cat_dict['id'],)
            ).fetchone()['count']
            cat_dict['post_count'] = post_count
            categories.append(cat_dict)
        
        # Get latest posts
        posts_raw = conn.execute("""
            SELECT * FROM posts 
            WHERE is_published = 1 
            ORDER BY created_at DESC 
            LIMIT 24
        """).fetchall()
        
        posts = [convert_post_row(row) for row in posts_raw]
        
        # Get trending posts (most viewed)
        trending_raw = conn.execute("""
            SELECT * FROM posts 
            WHERE is_published = 1 
            ORDER BY views DESC 
            LIMIT 6
        """).fetchall()
        
        trending_posts = [convert_post_row(row) for row in trending_raw]
        
        # Get sources with article counts
        sources = []
        for source in FlaskConfig.NEWS_SOURCES[:10]:
            article_count = conn.execute(
                "SELECT COUNT(*) as count FROM posts WHERE source_name = ?",
                (source['name'],)
            ).fetchone()['count']
            
            sources.append({
                **source,
                'article_count': article_count
            })
        
        conn.close()
        
        return render_template('index.html',
                             posts=posts,
                             trending_posts=trending_posts,
                             categories=categories,
                             sources=sources,
                             config=FlaskConfig,
                             now=datetime.now())
    except Exception as e:
        logger.error(f"Error in index route: {e}")
        return render_template('500.html', config=FlaskConfig), 500

@app.route('/category/<slug>')
def category_page(slug):
    """Category page - keeping original route name"""
    try:
        conn = get_db_connection()
        
        # Get category
        category_row = conn.execute("SELECT * FROM categories WHERE slug = ?", (slug,)).fetchone()
        if not category_row:
            conn.close()
            return render_template('404.html', config=FlaskConfig), 404
        
        category = {key: category_row[key] for key in category_row.keys()}
        
        # Pagination setup
        page = request.args.get('page', 1, type=int)
        limit = FlaskConfig.POSTS_PER_PAGE
        offset = (page - 1) * limit
        
        # Get posts in category with full info
        posts_raw = conn.execute("""
            SELECT p.*, c.name as category_name, c.slug as category_slug,
                   c.icon as category_icon, c.color as category_color
            FROM posts p 
            LEFT JOIN categories c ON p.category_id = c.id 
            WHERE p.category_id = ? AND p.is_published = 1 
            ORDER BY p.created_at DESC 
            LIMIT ? OFFSET ?
        """, (category['id'], limit, offset)).fetchall()
        
        posts = [convert_post_row(row) for row in posts_raw]
        
        # Count total for pagination
        total = conn.execute(
            "SELECT COUNT(*) FROM posts WHERE category_id = ? AND is_published = 1", 
            (category['id'],)
        ).fetchone()[0]
        pages = (total + limit - 1) // limit
        
        # Get all categories WITH post counts
        categories = []
        for row in conn.execute("SELECT * FROM categories ORDER BY name").fetchall():
            cat_dict = {key: row[key] for key in row.keys()}
            # Get post count for this category
            post_count = conn.execute(
                "SELECT COUNT(*) as count FROM posts WHERE category_id = ? AND is_published = 1",
                (cat_dict['id'],)
            ).fetchone()['count']
            cat_dict['post_count'] = post_count
            categories.append(cat_dict)
        
        conn.close()
        
        # Simple pagination object
        class Pagination:
            def __init__(self, items, page, pages, total):
                self.items = items
                self.page = page
                self.pages = pages
                self.total = total
                self.has_prev = page > 1
                self.has_next = page < pages
            
            def iter_pages(self):
                page_numbers = []
                for num in range(1, min(6, self.pages + 1)):
                    page_numbers.append(num)
                if self.pages > 6:
                    page_numbers.append(None)
                    page_numbers.append(self.pages)
                return page_numbers
        
        pagination = Pagination(posts, page, pages, total) if pages > 1 else None
        
        return render_template('category.html',
                             category=category,
                             posts=posts,
                             categories=categories,
                             pagination=pagination,
                             config=FlaskConfig,
                             now=datetime.now())
    except Exception as e:
        logger.error(f"Error in category_page route: {e}")
        return render_template('500.html', config=FlaskConfig), 500

@app.route('/post/<slug>')
def post_detail(slug):
    """Individual post page"""
    try:
        conn = get_db_connection()
        
        # Get post
        post_raw = conn.execute("SELECT * FROM posts WHERE slug = ?", (slug,)).fetchone()
        if not post_raw:
            conn.close()
            return render_template('404.html', config=FlaskConfig), 404
        
        post = convert_post_row(post_raw)
        
        # Increment view count
        conn.execute("UPDATE posts SET views = views + 1 WHERE slug = ?", (slug,))
        conn.commit()
        
        # Get related posts from same category
        related_raw = conn.execute("""
            SELECT * FROM posts 
            WHERE category_id = ? AND slug != ? AND is_published = 1 
            ORDER BY RANDOM() 
            LIMIT 6
        """, (post['category_id'], slug)).fetchall()
        
        related_posts = [convert_post_row(row) for row in related_raw]
        
        # Get all categories
        categories = conn.execute("SELECT * FROM categories").fetchall()
        
        conn.close()
        
        return render_template('post.html',
                             post=post,
                             related_posts=related_posts,
                             categories=categories,
                             config=FlaskConfig,
                             now=datetime.now())
    except Exception as e:
        logger.error(f"Error in post_detail route: {e}")
        return render_template('500.html', config=FlaskConfig), 500

@app.route('/search')
def search():
    """Search page"""
    try:
        query = request.args.get('q', '')
        conn = get_db_connection()
        
        if query:
            # Search in title and content
            posts_raw = conn.execute("""
                SELECT * FROM posts 
                WHERE (title LIKE ? OR content LIKE ? OR excerpt LIKE ?) 
                AND is_published = 1 
                ORDER BY created_at DESC 
                LIMIT 50
            """, (f'%{query}%', f'%{query}%', f'%{query}%')).fetchall()
            
            posts = [convert_post_row(row) for row in posts_raw]
        else:
            posts = []
        
        # Get all categories
        categories = []
        for row in conn.execute("SELECT * FROM categories ORDER BY name").fetchall():
            cat_dict = {key: row[key] for key in row.keys()}
            categories.append(cat_dict)
        
        conn.close()
        
        return render_template('search.html',
                             query=query,
                             posts=posts,
                             categories=categories,
                             config=FlaskConfig,
                             now=datetime.now())
    except Exception as e:
        logger.error(f"Error in search route: {e}")
        return render_template('500.html', config=FlaskConfig), 500

# ============= ADSENSE COMPLIANCE ROUTES (REQUIRED) =============
@app.route('/privacy')
def privacy():
    """Privacy Policy - REQUIRED for AdSense"""
    try:
        conn = get_db_connection()
        categories = []
        for row in conn.execute("SELECT * FROM categories ORDER BY name").fetchall():
            cat_dict = {key: row[key] for key in row.keys()}
            categories.append(cat_dict)
        conn.close()
        return render_template('privacy.html', config=FlaskConfig, categories=categories, now=datetime.now())
    except Exception as e:
        logger.error(f"Error in privacy route: {e}")
        return render_template('privacy.html', config=FlaskConfig, categories=[], now=datetime.now())

@app.route('/terms')
def terms():
    """Terms of Service - REQUIRED for AdSense"""
    try:
        conn = get_db_connection()
        categories = []
        for row in conn.execute("SELECT * FROM categories ORDER BY name").fetchall():
            cat_dict = {key: row[key] for key in row.keys()}
            categories.append(cat_dict)
        conn.close()
        return render_template('terms.html', config=FlaskConfig, categories=categories, now=datetime.now())
    except Exception as e:
        logger.error(f"Error in terms route: {e}")
        return render_template('terms.html', config=FlaskConfig, categories=[], now=datetime.now())

@app.route('/disclaimer')
def disclaimer():
    """Disclaimer - RECOMMENDED for AdSense"""
    try:
        conn = get_db_connection()
        categories = []
        for row in conn.execute("SELECT * FROM categories ORDER BY name").fetchall():
            cat_dict = {key: row[key] for key in row.keys()}
            categories.append(cat_dict)
        conn.close()
        return render_template('disclaimer.html', config=FlaskConfig, categories=categories, now=datetime.now())
    except Exception as e:
        logger.error(f"Error in disclaimer route: {e}")
        return render_template('disclaimer.html', config=FlaskConfig, categories=[], now=datetime.now())

@app.route('/contact')
def contact():
    """Contact Page - REQUIRED for AdSense"""
    try:
        conn = get_db_connection()
        categories = []
        for row in conn.execute("SELECT * FROM categories ORDER BY name").fetchall():
            cat_dict = {key: row[key] for key in row.keys()}
            categories.append(cat_dict)
        conn.close()
        return render_template('contact.html', config=FlaskConfig, categories=categories, now=datetime.now())
    except Exception as e:
        logger.error(f"Error in contact route: {e}")
        return render_template('contact.html', config=FlaskConfig, categories=[], now=datetime.now())

@app.route('/about')
def about():
    """About Page - Shows legitimacy"""
    try:
        conn = get_db_connection()
        categories = []
        for row in conn.execute("SELECT * FROM categories ORDER BY name").fetchall():
            cat_dict = {key: row[key] for key in row.keys()}
            categories.append(cat_dict)
        conn.close()
        return render_template('about.html', config=FlaskConfig, categories=categories, now=datetime.now())
    except Exception as e:
        logger.error(f"Error in about route: {e}")
        return render_template('about.html', config=FlaskConfig, categories=[], now=datetime.now())

@app.route('/sources')
def sources():
    """Sources listing page - keeping original route name"""
    try:
        conn = get_db_connection()
        
        # Get sources with actual article counts from database
        sources_list = []
        for source in FlaskConfig.NEWS_SOURCES:
            article_count = conn.execute(
                "SELECT COUNT(*) as count FROM posts WHERE source_name = ?",
                (source['name'],)
            ).fetchone()['count']
            
            sources_list.append({
                **source,
                'article_count': article_count
            })
        
        # Get all categories
        categories = []
        for row in conn.execute("SELECT * FROM categories ORDER BY name").fetchall():
            cat_dict = {key: row[key] for key in row.keys()}
            categories.append(cat_dict)
        
        conn.close()
        
        return render_template('sources.html',
                             sources=sources_list,
                             categories=categories,
                             config=FlaskConfig,
                             now=datetime.now())
    except Exception as e:
        logger.error(f"Error in sources route: {e}")
        return render_template('500.html', config=FlaskConfig), 500

# ============= ADMIN ROUTES =============
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    """Admin login page"""
    try:
        if request.method == 'POST':
            username = request.form.get('username')
            password = request.form.get('password')
            
            conn = get_db_connection()
            user_data = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
            conn.close()
            
            if user_data and check_password_hash(user_data['password_hash'], password):
                user = User(user_data['id'], user_data['username'])
                login_user(user)
                flash('Logged in successfully!', 'success')
                return redirect(url_for('admin_dashboard'))
            else:
                flash('Invalid credentials', 'danger')
        
        return render_template('admin/login.html', config=FlaskConfig)
    except Exception as e:
        logger.error(f"Error in admin_login route: {e}")
        flash('An error occurred. Please try again.', 'danger')
        return render_template('admin/login.html', config=FlaskConfig)

@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    """Admin dashboard"""
    try:
        conn = get_db_connection()
        
        stats = {
            'total_posts': conn.execute("SELECT COUNT(*) FROM posts").fetchone()[0],
            'published_posts': conn.execute("SELECT COUNT(*) FROM posts WHERE is_published = 1").fetchone()[0],
            'total_views': conn.execute("SELECT SUM(views) FROM posts").fetchone()[0] or 0,
            'categories': conn.execute("SELECT COUNT(*) FROM categories").fetchone()[0],
            'sources': len(FlaskConfig.NEWS_SOURCES)
        }
        
        # Recent posts
        recent_posts = conn.execute("""
            SELECT * FROM posts 
            ORDER BY created_at DESC 
            LIMIT 10
        """).fetchall()
        
        conn.close()
        
        return render_template('admin/dashboard.html',
                             stats=stats,
                             recent_posts=recent_posts,
                             config=FlaskConfig)
    except Exception as e:
        logger.error(f"Error in admin_dashboard route: {e}")
        flash('An error occurred while loading the dashboard.', 'danger')
        return redirect(url_for('admin_login'))

@app.route('/admin/update-content')
@login_required
def admin_update_content():
    """Manual content update trigger"""
    try:
        thread = threading.Thread(target=content_updater.update_content_database)
        thread.start()
        flash('Content update started in background', 'info')
        return redirect(url_for('admin_dashboard'))
    except Exception as e:
        logger.error(f"Error in admin_update_content route: {e}")
        flash('Failed to start content update.', 'danger')
        return redirect(url_for('admin_dashboard'))

@app.route('/admin/logout')
@login_required
def admin_logout():
    """Admin logout"""
    logout_user()
    flash('Logged out successfully', 'info')
    return redirect(url_for('index'))

# ============= API ENDPOINTS =============
@app.route('/api/stats')
def api_stats():
    """Real-time statistics API"""
    try:
        conn = get_db_connection()
        
        today = datetime.now().strftime('%Y-%m-%d')
        hour_ago = (datetime.now() - timedelta(hours=1)).strftime('%Y-%m-%d %H:%M:%S')
        
        stats = {
            'total_posts': conn.execute("SELECT COUNT(*) FROM posts WHERE is_published = 1").fetchone()[0],
            'today_posts': conn.execute("SELECT COUNT(*) FROM posts WHERE is_published = 1 AND date(created_at) = ?", (today,)).fetchone()[0],
            'hour_posts': conn.execute("SELECT COUNT(*) FROM posts WHERE is_published = 1 AND created_at >= ?", (hour_ago,)).fetchone()[0],
            'total_views': conn.execute("SELECT SUM(views) FROM posts").fetchone()[0] or 0,
            'active_sources': len([s for s in FlaskConfig.NEWS_SOURCES if s.get('enabled', True)]),
            'last_update': datetime.now().strftime('%H:%M:%S'),
            'status': 'online',
            'update_interval': FlaskConfig.UPDATE_INTERVAL_MINUTES
        }
        
        conn.close()
        
        return jsonify(stats)
    except Exception as e:
        logger.error(f"Error in api_stats route: {e}")
        return jsonify({'error': 'Internal server error'}), 500

# ============= ERROR HANDLERS =============
@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html', config=FlaskConfig), 404

@app.errorhandler(500)
def internal_server_error(e):
    logger.error(f"500 error: {e}")
    return render_template('500.html', config=FlaskConfig), 500

# ============= START APPLICATION =============
if __name__ == '__main__':
    print(f"Website: http://localhost:5000")
    print(f"Admin:   http://localhost:5000/admin/login")
    print(f"User:    {FlaskConfig.ADMIN_USERNAME}")
    print(f"Pass:    {FlaskConfig.ADMIN_PASSWORD}")
    
    # Start automatic content updates
    content_updater.start_auto_updates()
    
    # Start Flask app
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port, threaded=True)
else:
    # This runs when app is imported (e.g., by gunicorn)
    print("🚀 Starting Mzansi Insights on Render...")
    # Start auto-updates
    content_updater.start_auto_updates()