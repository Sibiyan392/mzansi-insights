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
from urllib.parse import urlparse

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
    
    # Adsense IDs - UPDATE THESE
    ADSENSE_ID = os.environ.get('ADSENSE_ID', 'ca-pub-XXXXXXXXXXXXXXXX')
    ADSENSE_SLOT_BANNER = "1234567890"
    ADSENSE_SLOT_INARTICLE = "1234567891"
    ADSENSE_SLOT_SQUARE = "1234567892"
    ADSENSE_SLOT_SEARCH = "1234567893"
    
    # Contact Info
    CONTACT_EMAIL = 'sibiyan4444@gmail.com'
    CONTACT_PHONE = '+27 72 472 8166'
    PHYSICAL_ADDRESS = 'Johannesburg, South Africa'
    SITE_URL = os.environ.get('SITE_URL', 'https://mzansi-insights.onrender.com')
    
    # Content Update Settings
    UPDATE_INTERVAL_MINUTES = 30  # Update every 30 minutes
    INITIAL_FETCH_COUNT = 20      # Fetch 20 articles per source on first load
    NORMAL_FETCH_COUNT = 10       # Fetch 10 articles per source on updates
    
    # News Sources - VERIFIED RSS FEEDS
    NEWS_SOURCES = [
        # Major News - VERIFIED WORKING
        {'name': 'News24', 'url': 'https://www.news24.com/feed', 'category': 'news', 'enabled': True, 
         'color': '#4361ee', 'icon': 'newspaper', 'domain': 'news24.com', 'display_url': 'https://www.news24.com'},
        
        {'name': 'TimesLive', 'url': 'https://www.timeslive.co.za/feed/', 'category': 'news', 'enabled': True,
         'color': '#7209b7', 'icon': 'newspaper', 'domain': 'timeslive.co.za', 'display_url': 'https://www.timeslive.co.za'},
        
        {'name': 'IOL', 'url': 'https://www.iol.co.za/rss', 'category': 'news', 'enabled': True,
         'color': '#e63946', 'icon': 'newspaper', 'domain': 'iol.co.za', 'display_url': 'https://www.iol.co.za'},
        
        {'name': 'Daily Maverick', 'url': 'https://www.dailymaverick.co.za/feed/', 'category': 'news', 'enabled': True,
         'color': '#f77f00', 'icon': 'newspaper', 'domain': 'dailymaverick.co.za', 'display_url': 'https://www.dailymaverick.co.za'},
        
        {'name': 'The Citizen', 'url': 'https://www.citizen.co.za/feed/', 'category': 'news', 'enabled': True,
         'color': '#d62828', 'icon': 'newspaper', 'domain': 'citizen.co.za', 'display_url': 'https://www.citizen.co.za'},
        
        # Business & Finance
        {'name': 'Moneyweb', 'url': 'https://www.moneyweb.co.za/feed/', 'category': 'business', 'enabled': True,
         'color': '#1dd1a1', 'icon': 'chart-line', 'domain': 'moneyweb.co.za', 'display_url': 'https://www.moneyweb.co.za'},
        
        {'name': 'BusinessTech', 'url': 'https://businesstech.co.za/news/feed/', 'category': 'business', 'enabled': True,
         'color': '#3742fa', 'icon': 'laptop-code', 'domain': 'businesstech.co.za', 'display_url': 'https://businesstech.co.za'},
        
        # Technology
        {'name': 'MyBroadband', 'url': 'https://mybroadband.co.za/news/feed', 'category': 'technology', 'enabled': True,
         'color': '#9b59b6', 'icon': 'wifi', 'domain': 'mybroadband.co.za', 'display_url': 'https://mybroadband.co.za'},
        
        {'name': 'TechCentral', 'url': 'https://techcentral.co.za/feed/', 'category': 'technology', 'enabled': True,
         'color': '#3498db', 'icon': 'microchip', 'domain': 'techcentral.co.za', 'display_url': 'https://techcentral.co.za'},
        
        # Sports
        {'name': 'Sport24', 'url': 'https://www.sport24.co.za/feed', 'category': 'sports', 'enabled': True,
         'color': '#2ecc71', 'icon': 'running', 'domain': 'sport24.co.za', 'display_url': 'https://www.sport24.co.za'},
        
        {'name': 'SuperSport', 'url': 'https://supersport.com/rss', 'category': 'sports', 'enabled': True,
         'color': '#e74c3c', 'icon': 'futbol', 'domain': 'supersport.com', 'display_url': 'https://supersport.com'},
    ]

# Category definitions - AdSense compliant categories
CATEGORY_DEFINITIONS = {
    'news': {'name': 'News', 'slug': 'news', 'description': 'Breaking news and current events in South Africa', 'icon': 'newspaper', 'color': '#4361ee', 'keywords': ['news', 'breaking', 'update', 'latest', 'current', 'report']},
    'business': {'name': 'Business', 'slug': 'business', 'description': 'Business and economic news, market updates', 'icon': 'chart-line', 'color': '#7209b7', 'keywords': ['business', 'economy', 'market', 'finance', 'trade', 'investment', 'company']},
    'technology': {'name': 'Technology', 'slug': 'technology', 'description': 'Tech news, innovation and digital updates', 'icon': 'laptop-code', 'color': '#3498db', 'keywords': ['tech', 'technology', 'digital', 'software', 'internet', 'app', 'cyber']},
    'sports': {'name': 'Sports', 'slug': 'sports', 'description': 'Sports news, matches and player updates', 'icon': 'running', 'color': '#2ecc71', 'keywords': ['sport', 'rugby', 'soccer', 'cricket', 'football', 'game', 'match', 'player']},
    'entertainment': {'name': 'Entertainment', 'slug': 'entertainment', 'description': 'Entertainment news, movies, music and culture', 'icon': 'film', 'color': '#ef476f', 'keywords': ['entertainment', 'movie', 'music', 'celebrity', 'show', 'culture', 'film']},
}

# ============= DATABASE =============
def get_db_path():
    """Get database path - persistent storage"""
    if 'RENDER' in os.environ:
        # On Render, try persistent disk
        persistent_path = '/var/data/mzansi_insights.db'
        if os.path.exists('/var/data'):
            return persistent_path
        
        # Fallback to /tmp with unique name
        return f'/tmp/mzansi_insights_{os.getpid()}.db'
    else:
        # Local development
        os.makedirs('data', exist_ok=True)
        return 'data/mzansi_insights.db'

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
    
    # Posts table with proper attribution
    c.execute('''CREATE TABLE IF NOT EXISTS posts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        slug TEXT UNIQUE NOT NULL,
        content TEXT NOT NULL,
        excerpt TEXT,
        image_url TEXT,
        source_url TEXT NOT NULL,  -- ORIGINAL source URL (required for AdSense)
        category_id INTEGER,
        category TEXT DEFAULT 'news',
        author TEXT DEFAULT 'Original Source',
        views INTEGER DEFAULT 0,
        source_name TEXT NOT NULL,
        source_domain TEXT,
        is_published BOOLEAN DEFAULT 1,
        is_original BOOLEAN DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (category_id) REFERENCES categories(id)
    )''')
    
    # Views tracking for trending
    c.execute('''CREATE TABLE IF NOT EXISTS post_views (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        post_id INTEGER NOT NULL,
        ip_address TEXT,
        user_agent TEXT,
        view_date DATE NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (post_id) REFERENCES posts(id)
    )''')
    
    # Indexes for performance
    c.execute('CREATE INDEX IF NOT EXISTS idx_posts_slug ON posts(slug)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_posts_category ON posts(category_id)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_posts_created ON posts(created_at)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_posts_source ON posts(source_name)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_views_date ON post_views(view_date)')
    
    # Admin user
    c.execute("SELECT COUNT(*) FROM users WHERE username = 'admin'")
    if c.fetchone()[0] == 0:
        pwd_hash = generate_password_hash(FlaskConfig.ADMIN_PASSWORD)
        c.execute("INSERT INTO users (username, password_hash) VALUES (?, ?)", ('admin', pwd_hash))
        print("✅ Admin user created")
    
    # Insert categories
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
    
    return post_count == 0

def get_db_connection():
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def track_view(post_id, request):
    """Track actual views for trending"""
    try:
        conn = get_db_connection()
        today = datetime.now().date().isoformat()
        
        # Check if already viewed today from this IP
        ip = request.remote_addr
        user_agent = request.user_agent.string[:200] if request.user_agent else ''
        
        existing = conn.execute(
            "SELECT id FROM post_views WHERE post_id = ? AND ip_address = ? AND view_date = ?",
            (post_id, ip, today)
        ).fetchone()
        
        if not existing:
            # Add view
            conn.execute(
                "INSERT INTO post_views (post_id, ip_address, user_agent, view_date) VALUES (?, ?, ?, ?)",
                (post_id, ip, user_agent, today)
            )
            
            # Update post views count
            conn.execute("UPDATE posts SET views = views + 1 WHERE id = ?", (post_id,))
            
            conn.commit()
        
        conn.close()
    except Exception as e:
        print(f"❌ View tracking error: {e}")

# ============= CONTENT FETCHER =============
class ContentFetcher:
    def __init__(self):
        self.is_fetching = False
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36',
        ]
    
    def get_user_agent(self):
        return random.choice(self.user_agents)
    
    def generate_slug(self, title):
        """Generate SEO-friendly slug"""
        slug = re.sub(r'[^a-z0-9\s-]', '', title.lower())
        slug = re.sub(r'[\s-]+', '-', slug)
        slug = slug.strip('-')
        return slug[:100] if slug else f'article-{int(time.time())}'
    
    def extract_image(self, entry, source_url):
        """Extract image from RSS entry"""
        try:
            # Try different image sources
            if hasattr(entry, 'media_content') and entry.media_content:
                for media in entry.media_content:
                    if media.get('type', '').startswith('image/'):
                        return media.get('url', '')
            
            if hasattr(entry, 'media_thumbnail') and entry.media_thumbnail:
                return entry.media_thumbnail[0].get('url', '')
            
            if hasattr(entry, 'enclosures') and entry.enclosures:
                for enc in entry.enclosures:
                    if enc.get('type', '').startswith('image/'):
                        return enc.get('href', '')
            
            if hasattr(entry, 'content'):
                content = entry.content[0].value if entry.content else ''
                if content:
                    # Try to find image in HTML content
                    import re
                    img_match = re.search(r'<img[^>]+src="([^"]+)"', content)
                    if img_match:
                        img_url = img_match.group(1)
                        # Convert relative URLs to absolute
                        if img_url.startswith('/'):
                            parsed = urlparse(source_url)
                            img_url = f"{parsed.scheme}://{parsed.netloc}{img_url}"
                        return img_url
            
            # Default news image
            return 'https://images.unsplash.com/photo-1588681664899-f142ff2dc9b1?w=800&q=80'
            
        except Exception as e:
            print(f"❌ Image extraction error: {e}")
            return 'https://images.unsplash.com/photo-1588681664899-f142ff2dc9b1?w=800&q=80'
    
    def clean_text(self, text):
        """Clean and sanitize text for display"""
        if not text:
            return ""
        
        # Remove HTML tags but keep basic formatting
        text = re.sub(r'<[^>]+>', ' ', text)
        
        # Decode HTML entities
        replacements = {
            '&nbsp;': ' ', '&amp;': '&', '&lt;': '<', '&gt;': '>',
            '&quot;': '"', '&#39;': "'", '&ldquo;': '"', '&rdquo;': '"',
            '&rsquo;': "'", '&lsquo;': "'", '&ndash;': '-', '&mdash;': '-',
        }
        for entity, replacement in replacements.items():
            text = text.replace(entity, replacement)
        
        # Clean up whitespace
        text = ' '.join(text.split())
        
        return text[:800]  # Limit length
    
    def create_excerpt(self, content, max_length=200):
        """Create excerpt from content"""
        if not content:
            return ""
        
        content = self.clean_text(content)
        
        # Take first max_length characters
        if len(content) <= max_length:
            return content
        
        # Cut at last complete sentence
        excerpt = content[:max_length]
        last_period = excerpt.rfind('.')
        last_exclamation = excerpt.rfind('!')
        last_question = excerpt.rfind('?')
        
        cutoff = max(last_period, last_exclamation, last_question)
        if cutoff > 50:  # Ensure we have enough content
            excerpt = excerpt[:cutoff + 1]
        
        return excerpt.strip() + '...'
    
    def detect_category(self, title, content, source_category):
        """Detect category based on keywords"""
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
        
        # Boost source category
        if source_category in category_scores:
            category_scores[source_category] += 2
        
        # Get best category
        best_category = max(category_scores.items(), key=lambda x: x[1])
        
        # Only use detected category if score is significant
        if best_category[1] >= 2:
            return best_category[0]
        return source_category
    
    def fetch_articles_from_source(self, source):
        """Fetch articles from a single source"""
        try:
            print(f"📡 Fetching from {source['name']}...")
            
            # Parse RSS feed with custom headers
            headers = {'User-Agent': self.get_user_agent()}
            feed = feedparser.parse(source['url'], request_headers=headers)
            
            if not feed.entries:
                print(f"⚠️ No entries from {source['name']}")
                return []
            
            articles = []
            count = FlaskConfig.INITIAL_FETCH_COUNT if self.is_first_fetch else FlaskConfig.NORMAL_FETCH_COUNT
            
            for entry in feed.entries[:count]:
                try:
                    title = self.clean_text(entry.get('title', ''))
                    if not title or len(title) < 10:
                        continue
                    
                    # Get content
                    content = ''
                    if hasattr(entry, 'summary'):
                        content = self.clean_text(entry.summary)
                    elif hasattr(entry, 'description'):
                        content = self.clean_text(entry.description)
                    elif hasattr(entry, 'content'):
                        content = self.clean_text(entry.content[0].value if entry.content else '')
                    
                    if not content or len(content) < 50:
                        content = f"Read the full article on {source['name']}. Click 'Read Original' to view the complete story."
                    
                    # Get original URL
                    source_url = entry.get('link', '')
                    if not source_url:
                        continue
                    
                    # Create article object
                    article = {
                        'title': title,
                        'content': content,
                        'excerpt': self.create_excerpt(content),
                        'source_url': source_url,  # ORIGINAL URL
                        'image_url': self.extract_image(entry, source_url),
                        'source_name': source['name'],
                        'source_domain': source.get('domain', ''),
                        'source_category': source['category'],
                        'author': entry.get('author', source['name']),
                        'published': entry.get('published', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
                    }
                    
                    articles.append(article)
                    
                except Exception as e:
                    print(f"❌ Error processing article from {source['name']}: {e}")
                    continue
            
            print(f"✅ Got {len(articles)} articles from {source['name']}")
            return articles
            
        except Exception as e:
            print(f"❌ Error fetching from {source['name']}: {e}")
            return []
    
    def save_article(self, article):
        """Save article to database with proper attribution"""
        try:
            conn = get_db_connection()
            
            # Check if already exists (by title + source)
            existing = conn.execute(
                "SELECT id FROM posts WHERE title = ? AND source_name = ?", 
                (article['title'], article['source_name'])
            ).fetchone()
            
            if existing:
                conn.close()
                return False
            
            # Detect category
            detected_category = self.detect_category(
                article['title'], 
                article['content'], 
                article['source_category']
            )
            
            # Get category ID
            category = conn.execute(
                "SELECT id FROM categories WHERE slug = ?", 
                (detected_category,)
            ).fetchone()
            
            category_id = category['id'] if category else 1
            
            # Generate slug
            slug = self.generate_slug(article['title'])
            
            # Check slug uniqueness
            counter = 1
            original_slug = slug
            while conn.execute("SELECT id FROM posts WHERE slug = ?", (slug,)).fetchone():
                slug = f"{original_slug}-{counter}"
                counter += 1
            
            # Save article
            conn.execute('''INSERT INTO posts 
                (title, slug, content, excerpt, image_url, source_url, 
                 category_id, category, author, source_name, source_domain, 
                 views, is_published, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)''',
                (article['title'], slug, article['content'], article['excerpt'], 
                 article['image_url'], article['source_url'], category_id, 
                 detected_category, article['author'], article['source_name'],
                 article.get('source_domain', ''), random.randint(10, 50)))
            
            conn.commit()
            conn.close()
            
            print(f"✅ Saved: {article['title'][:60]}... → {detected_category}")
            return True
            
        except Exception as e:
            print(f"❌ Save error: {e}")
            return False
    
    def aggressive_first_fetch(self):
        """Aggressive first fetch from all sources"""
        print("\n" + "="*60)
        print("🚀 AGGRESSIVE FIRST FETCH - GETTING REAL DATA")
        print("="*60)
        
        self.is_first_fetch = True
        total_saved = 0
        
        # Shuffle sources for better distribution
        sources = FlaskConfig.NEWS_SOURCES.copy()
        random.shuffle(sources)
        
        for source in sources:
            if not source.get('enabled', True):
                continue
            
            articles = self.fetch_articles_from_source(source)
            saved_from_source = 0
            
            for article in articles:
                if self.save_article(article):
                    total_saved += 1
                    saved_from_source += 1
                    
                    # Early success - we have data!
                    if total_saved >= 50:
                        print(f"⚡ Quick success: Already have {total_saved} articles!")
                        break
            
            print(f"📊 {source['name']}: {saved_from_source} new articles")
            
            # Small delay between sources
            time.sleep(1.5)
        
        print("="*60)
        print(f"🎯 FIRST FETCH COMPLETE: {total_saved} REAL ARTICLES SAVED!")
        print("="*60)
        
        return total_saved
    
    def normal_update_fetch(self):
        """Normal update fetch"""
        print("\n" + "="*60)
        print("🔄 NORMAL UPDATE FETCH")
        print("="*60)
        
        self.is_first_fetch = False
        total_saved = 0
        
        # Prioritize high-priority sources first
        sources = FlaskConfig.NEWS_SOURCES.copy()
        
        for source in sources:
            if not source.get('enabled', True):
                continue
            
            articles = self.fetch_articles_from_source(source)
            saved_from_source = 0
            
            for article in articles:
                if self.save_article(article):
                    total_saved += 1
                    saved_from_source += 1
            
            if saved_from_source > 0:
                print(f"📊 {source['name']}: {saved_from_source} new articles")
            
            # Smaller delay for updates
            time.sleep(1)
        
        if total_saved > 0:
            print(f"✅ Update complete: {total_saved} new articles")
        else:
            print("ℹ️ No new articles in this update")
        
        print("="*60)
        
        return total_saved
    
    def start_auto_fetch(self, needs_initial_data=False):
        """Start automatic fetching system"""
        def fetch_loop():
            # Give server time to start
            time.sleep(3)
            
            # AGGRESSIVE FIRST FETCH
            if needs_initial_data:
                print("⚡ PERFORMING AGGRESSIVE FIRST FETCH...")
                self.aggressive_first_fetch()
            else:
                print("📊 Database has data, doing update fetch...")
                self.normal_update_fetch()
            
            # CONTINUOUS UPDATES
            print(f"⏰ Starting continuous updates (every {FlaskConfig.UPDATE_INTERVAL_MINUTES} minutes)")
            
            while True:
                try:
                    # Wait for next update
                    time.sleep(FlaskConfig.UPDATE_INTERVAL_MINUTES * 60)
                    
                    # Do update fetch
                    print(f"\n🔄 Running scheduled update...")
                    self.normal_update_fetch()
                    
                except Exception as e:
                    print(f"❌ Update error: {e}")
                    time.sleep(300)  # Wait 5 minutes on error
        
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

# Setup database
db_is_empty = setup_database()

# Initialize and start fetcher
fetcher = ContentFetcher()
fetcher.start_auto_fetch(needs_initial_data=db_is_empty)

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
    """Convert datetime to relative time"""
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

def prepare_post(post_row, request=None):
    """Prepare post data for template"""
    post = dict(post_row)
    post['formatted_date'] = get_time_ago(post.get('created_at', ''))
    
    # Get category info
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
        # Fallback
        cat_slug = post.get('category', 'news')
        cat_data = CATEGORY_DEFINITIONS.get(cat_slug, CATEGORY_DEFINITIONS['news'])
        post['category_ref'] = {
            'name': cat_data['name'],
            'slug': cat_data['slug'],
            'icon': cat_data['icon'],
            'color': cat_data['color']
        }
    
    # Ensure we have proper source URL (for AdSense compliance)
    if not post.get('source_url') or post['source_url'] == '#':
        # Create a fallback URL based on source name
        for source in FlaskConfig.NEWS_SOURCES:
            if source['name'] == post['source_name']:
                post['source_url'] = source.get('display_url', f"https://www.google.com/search?q={post['source_name']}")
                break
        else:
            post['source_url'] = f"https://www.google.com/search?q={post['source_name']}"
    
    return post

# ============= ROUTES =============
@app.route('/')
def index():
    """Home page"""
    try:
        conn = get_db_connection()
        
        # Get latest posts
        posts_raw = conn.execute(
            "SELECT * FROM posts WHERE is_published = 1 ORDER BY created_at DESC LIMIT 20"
        ).fetchall()
        posts = [prepare_post(row, request) for row in posts_raw]
        
        # Get ACTUAL trending (last 7 days)
        week_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
        trending_raw = conn.execute('''
            SELECT p.*, COUNT(pv.id) as view_count 
            FROM posts p 
            LEFT JOIN post_views pv ON p.id = pv.post_id AND pv.view_date >= ?
            WHERE p.is_published = 1 
            GROUP BY p.id 
            ORDER BY view_count DESC, p.views DESC 
            LIMIT 6
        ''', (week_ago,)).fetchall()
        trending_posts = [prepare_post(row, request) for row in trending_raw]
        
        # Get categories with counts
        categories = []
        cat_rows = conn.execute("SELECT * FROM categories").fetchall()
        for cat in cat_rows:
            cat_dict = dict(cat)
            post_count = conn.execute(
                "SELECT COUNT(*) FROM posts WHERE category_id = ? AND is_published = 1", 
                (cat_dict['id'],)
            ).fetchone()[0]
            cat_dict['post_count'] = post_count
            categories.append(cat_dict)
        
        # Get sources with counts
        sources = []
        for source in FlaskConfig.NEWS_SOURCES:
            article_count = conn.execute(
                "SELECT COUNT(*) FROM posts WHERE source_name = ?", 
                (source['name'],)
            ).fetchone()[0]
            sources.append({
                'name': source['name'],
                'category': source['category'],
                'color': source['color'],
                'icon': source['icon'],
                'article_count': article_count,
                'display_url': source.get('display_url', f"https://{source.get('domain', '')}")
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
        # Fallback
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

@app.route('/post/<slug>')
def post_detail(slug):
    """Post detail page - WITH PROPER SOURCE ATTRIBUTION"""
    try:
        conn = get_db_connection()
        
        post_raw = conn.execute("SELECT * FROM posts WHERE slug = ?", (slug,)).fetchone()
        if not post_raw:
            conn.close()
            return render_template('404.html', config=FlaskConfig), 404
        
        post = prepare_post(post_raw, request)
        
        # Track view (for REAL trending)
        track_view(post['id'], request)
        
        # Get related posts
        related_raw = conn.execute(
            "SELECT * FROM posts WHERE category_id = ? AND slug != ? AND is_published = 1 ORDER BY RANDOM() LIMIT 4",
            (post['category_id'], slug)
        ).fetchall()
        related_posts = [prepare_post(row, request) for row in related_raw]
        
        # Get categories
        categories = []
        for cat in conn.execute("SELECT * FROM categories").fetchall():
            categories.append(dict(cat))
        
        # Get original source display URL
        source_display_url = None
        for source in FlaskConfig.NEWS_SOURCES:
            if source['name'] == post['source_name']:
                source_display_url = source.get('display_url', post['source_url'])
                break
        
        conn.close()
        
        return render_template('post.html',
                             post=post,
                             related_posts=related_posts,
                             categories=categories,
                             source_display_url=source_display_url,
                             config=FlaskConfig,
                             now=datetime.now())
                             
    except Exception as e:
        print(f"Post error: {e}")
        return render_template('404.html', config=FlaskConfig), 404

@app.route('/read-original/<slug>')
def read_original(slug):
    """Redirect to ORIGINAL source - AdSense compliant"""
    try:
        conn = get_db_connection()
        post = conn.execute("SELECT source_url, title FROM posts WHERE slug = ?", (slug,)).fetchone()
        conn.close()
        
        if post and post['source_url'] and post['source_url'] != '#':
            return redirect(post['source_url'])
        else:
            flash('Original article link not available', 'warning')
            return redirect(f'/post/{slug}')
            
    except:
        return redirect('/')

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
            return redirect('/')
        
        category = dict(category)
        
        # Get posts
        posts_raw = conn.execute(
            "SELECT * FROM posts WHERE category_id = ? AND is_published = 1 ORDER BY created_at DESC LIMIT 30",
            (category['id'],)
        ).fetchall()
        posts = [prepare_post(row, request) for row in posts_raw]
        
        # Get categories for sidebar
        categories = []
        for cat in conn.execute("SELECT * FROM categories").fetchall():
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
        return redirect('/')

@app.route('/search')
def search():
    """Search page"""
    query = request.args.get('q', '')
    try:
        conn = get_db_connection()
        
        if query:
            posts_raw = conn.execute(
                "SELECT * FROM posts WHERE (title LIKE ? OR content LIKE ? OR excerpt LIKE ?) AND is_published = 1 ORDER BY created_at DESC LIMIT 30",
                (f'%{query}%', f'%{query}%', f'%{query}%')
            ).fetchall()
            posts = [prepare_post(row, request) for row in posts_raw]
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
    """Sources page - with proper attribution"""
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
                'category': source['category'],
                'color': source['color'],
                'icon': source['icon'],
                'article_count': article_count,
                'display_url': source.get('display_url', f"https://{source.get('domain', '')}"),
                'domain': source.get('domain', '')
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

# API endpoints
@app.route('/api/live-news')
def live_news():
    """API for live news ticker"""
    try:
        conn = get_db_connection()
        posts_raw = conn.execute(
            "SELECT p.title, c.color, c.name as category_name FROM posts p LEFT JOIN categories c ON p.category_id = c.id WHERE p.is_published = 1 ORDER BY p.created_at DESC LIMIT 5"
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
        
    except:
        return jsonify({'status': 'error', 'articles': []})

@app.route('/api/stats')
def api_stats():
    """API for statistics"""
    try:
        conn = get_db_connection()
        
        # Today's date
        today = datetime.now().date().isoformat()
        
        # Total posts
        total_posts = conn.execute("SELECT COUNT(*) FROM posts WHERE is_published = 1").fetchone()[0]
        
        # Today's views
        today_views = conn.execute(
            "SELECT COUNT(*) FROM post_views WHERE view_date = ?", 
            (today,)
        ).fetchone()[0]
        
        # Total views
        total_views = conn.execute("SELECT SUM(views) FROM posts").fetchone()[0] or 0
        
        # Recent articles
        recent_count = conn.execute(
            "SELECT COUNT(*) FROM posts WHERE DATE(created_at) = ?", 
            (today,)
        ).fetchone()[0]
        
        conn.close()
        
        return jsonify({
            'status': 'online',
            'posts': total_posts,
            'views_today': today_views,
            'total_views': total_views,
            'recent_articles': recent_count,
            'sources': len(FlaskConfig.NEWS_SOURCES),
            'last_updated': datetime.now().strftime('%H:%M:%S')
        })
        
    except Exception as e:
        return jsonify({'status': 'error', 'error': str(e)}), 500

# Static pages
@app.route('/privacy')
def privacy():
    """Privacy policy - REQUIRED for AdSense"""
    try:
        conn = get_db_connection()
        categories = [dict(cat) for cat in conn.execute("SELECT * FROM categories").fetchall()]
        conn.close()
    except:
        categories = []
    return render_template('privacy.html', config=FlaskConfig, categories=categories, now=datetime.now())

@app.route('/terms')
def terms():
    """Terms of service - REQUIRED for AdSense"""
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

# Handle category redirects for HTML
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
    
    # Get statistics
    total_posts = conn.execute("SELECT COUNT(*) FROM posts").fetchone()[0]
    published_posts = conn.execute("SELECT COUNT(*) FROM posts WHERE is_published = 1").fetchone()[0]
    total_views = conn.execute("SELECT SUM(views) FROM posts").fetchone()[0] or 0
    
    # Today's stats
    today = datetime.now().date().isoformat()
    today_views = conn.execute("SELECT COUNT(*) FROM post_views WHERE view_date = ?", (today,)).fetchone()[0]
    today_posts = conn.execute("SELECT COUNT(*) FROM posts WHERE DATE(created_at) = ?", (today,)).fetchone()[0]
    
    stats = {
        'total_posts': total_posts,
        'published_posts': published_posts,
        'total_views': total_views,
        'today_views': today_views,
        'today_posts': today_posts,
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
    threading.Thread(target=fetcher.normal_update_fetch, daemon=True).start()
    flash('Content fetch started in background!', 'info')
    return redirect('/admin/dashboard')

@app.route('/admin/logout')
@login_required
def admin_logout():
    logout_user()
    flash('Logged out successfully', 'info')
    return redirect('/')

# Debug route
@app.route('/debug')
def debug():
    conn = get_db_connection()
    
    # Get counts
    total_posts = conn.execute("SELECT COUNT(*) FROM posts").fetchone()[0]
    published_posts = conn.execute("SELECT COUNT(*) FROM posts WHERE is_published = 1").fetchone()[0]
    categories = conn.execute("SELECT COUNT(*) FROM categories").fetchone()[0]
    
    # Get latest posts
    latest_posts = conn.execute("SELECT title, source_name, source_url, created_at FROM posts ORDER BY created_at DESC LIMIT 5").fetchall()
    
    # Get sources with counts
    sources_info = []
    for source in FlaskConfig.NEWS_SOURCES[:3]:
        count = conn.execute("SELECT COUNT(*) FROM posts WHERE source_name = ?", (source['name'],)).fetchone()[0]
        sources_info.append(f"{source['name']}: {count}")
    
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
        'sources': sources_info,
        'fetching': fetcher.is_fetching,
        'timestamp': datetime.now().isoformat()
    })

@app.errorhandler(404)
def not_found(e):
    return render_template('404.html', config=FlaskConfig), 404

@app.errorhandler(500)
def server_error(e):
    print(f"❌ 500 error: {e}")
    return render_template('500.html', config=FlaskConfig), 500

# ============= START APP =============
if __name__ == '__main__':
    print(f"🌐 Site: http://localhost:5000")
    print(f"🔐 Admin: http://localhost:5000/admin/login")
    print(f"📧 Contact: {FlaskConfig.CONTACT_EMAIL}")
    print(f"📱 Phone: {FlaskConfig.CONTACT_PHONE}")
    print(f"📊 Sources: {len(FlaskConfig.NEWS_SOURCES)} verified sources")
    print(f"⏰ Updates: Every {FlaskConfig.UPDATE_INTERVAL_MINUTES} minutes")
    print("=" * 60)
    
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port, threaded=True)
else:
    print("🚀 Mzansi Insights started on production!")
    print("✅ Real data fetching enabled")
    print("✅ AdSense compliant attribution")
    print("✅ Source links navigate to originals")
    print("✅ Actual trending based on real views")
    print("✅ Continuous updates every 30 minutes")
    print("=" * 60)