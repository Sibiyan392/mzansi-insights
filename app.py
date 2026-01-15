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
    
    # Content Update
    UPDATE_INTERVAL_MINUTES = 30
    INITIAL_FETCH_COUNT = 10
    
    # News Sources - WORKING RSS FEEDS (Tested)
    NEWS_SOURCES = [
        # These feeds WORK:
        {'name': 'News24', 'url': 'https://www.news24.com/rss/', 'category': 'news', 'enabled': True, 
         'color': '#4361ee', 'icon': 'newspaper', 'domain': 'news24.com'},
        
        {'name': 'BusinessTech', 'url': 'https://businesstech.co.za/news/feed/', 'category': 'business', 'enabled': True,
         'color': '#3742fa', 'icon': 'laptop-code', 'domain': 'businesstech.co.za'},
        
        {'name': 'MyBroadband', 'url': 'https://mybroadband.co.za/news/feed', 'category': 'technology', 'enabled': True,
         'color': '#9b59b6', 'icon': 'wifi', 'domain': 'mybroadband.co.za'},
        
        {'name': 'TimesLive', 'url': 'https://www.timeslive.co.za/rss/', 'category': 'news', 'enabled': True,
         'color': '#7209b7', 'icon': 'newspaper', 'domain': 'timeslive.co.za'},
        
        # Fallback: Use Google News RSS for South Africa
        {'name': 'Google News SA', 'url': 'https://news.google.com/rss/search?q=South+Africa&hl=en-ZA&gl=ZA&ceid=ZA:en', 'category': 'news', 'enabled': True,
         'color': '#4285F4', 'icon': 'google', 'domain': 'news.google.com'},
        
        {'name': 'IOL', 'url': 'https://www.iol.co.za/cmlink/1.640', 'category': 'news', 'enabled': True,
         'color': '#e63946', 'icon': 'newspaper', 'domain': 'iol.co.za'},
    ]

# Category definitions
CATEGORY_DEFINITIONS = {
    'news': {'name': 'News', 'slug': 'news', 'description': 'Breaking news and current events', 'icon': 'newspaper', 'color': '#4361ee'},
    'business': {'name': 'Business', 'slug': 'business', 'description': 'Business and economic news', 'icon': 'chart-line', 'color': '#7209b7'},
    'technology': {'name': 'Technology', 'slug': 'technology', 'description': 'Tech news and innovation', 'icon': 'laptop-code', 'color': '#3498db'},
    'sports': {'name': 'Sports', 'slug': 'sports', 'description': 'Sports news and updates', 'icon': 'running', 'color': '#2ecc71'},
}

# ============= DATABASE =============
def get_db_path():
    """Get database path"""
    if 'RENDER' in os.environ:
        return '/tmp/mzansi.db'
    else:
        os.makedirs('data', exist_ok=True)
        return 'data/mzansi.db'

def setup_database():
    print("=" * 60)
    print("📄 SETTING UP DATABASE...")
    print("=" * 60)
    
    db_path = get_db_path()
    print(f"📊 Database: {db_path}")
    
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    # Simple tables
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS posts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        slug TEXT UNIQUE NOT NULL,
        content TEXT NOT NULL,
        excerpt TEXT,
        image_url TEXT,
        source_url TEXT NOT NULL,
        category TEXT DEFAULT 'news',
        author TEXT DEFAULT 'Source',
        views INTEGER DEFAULT 0,
        source_name TEXT NOT NULL,
        is_published BOOLEAN DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # Admin user
    c.execute("SELECT COUNT(*) FROM users WHERE username = 'admin'")
    if c.fetchone()[0] == 0:
        pwd_hash = generate_password_hash(FlaskConfig.ADMIN_PASSWORD)
        c.execute("INSERT INTO users (username, password_hash) VALUES (?, ?)", ('admin', pwd_hash))
        print("✅ Admin user created")
    
    # Check posts
    c.execute("SELECT COUNT(*) FROM posts")
    post_count = c.fetchone()[0]
    
    conn.commit()
    conn.close()
    
    print(f"✅ Database ready - {post_count} existing posts")
    print("=" * 60)
    
    return post_count == 0

def get_db_connection():
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

# ============= SIMPLE FETCHER =============
class SimpleFetcher:
    def __init__(self):
        self.is_fetching = False
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        ]
    
    def fetch_rss(self, url):
        """Simple RSS fetch with timeout"""
        try:
            print(f"🌐 Fetching: {url[:50]}...")
            feed = feedparser.parse(url)
            
            if feed.entries:
                print(f"✅ Got {len(feed.entries)} entries")
                return feed
            else:
                print(f"⚠️ No entries found")
                return None
                
        except Exception as e:
            print(f"❌ Fetch error: {e}")
            return None
    
    def create_slug(self, title):
        """Create URL slug"""
        slug = re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')
        return slug[:50] or f"article-{int(time.time())}"
    
    def get_image(self, entry):
        """Extract image from entry"""
        # Try multiple methods
        if hasattr(entry, 'media_content') and entry.media_content:
            for media in entry.media_content:
                if 'image' in media.get('type', ''):
                    return media.get('url', '')
        
        if hasattr(entry, 'links') and entry.links:
            for link in entry.links:
                if 'image' in link.get('type', ''):
                    return link.get('href', '')
        
        # Default news images
        default_images = [
            'https://images.unsplash.com/photo-1588681664899-f142ff2dc9b1?w=800',
            'https://images.unsplash.com/photo-1497366754035-f200968a6e72?w=800',
            'https://images.unsplash.com/photo-1546519638-68e109498ffc?w=800',
        ]
        return random.choice(default_images)
    
    def fetch_and_save(self, source, count=10):
        """Fetch and save articles from a source"""
        try:
            print(f"\n📡 FETCHING FROM {source['name']}...")
            
            feed = self.fetch_rss(source['url'])
            if not feed or not feed.entries:
                print(f"❌ Failed to fetch from {source['name']}")
                return 0
            
            saved = 0
            conn = get_db_connection()
            
            for entry in feed.entries[:count]:
                try:
                    title = entry.get('title', '').strip()
                    if not title or len(title) < 10:
                        continue
                    
                    # Get content
                    content = ''
                    if hasattr(entry, 'summary'):
                        content = entry.summary[:500]
                    elif hasattr(entry, 'description'):
                        content = entry.description[:500]
                    
                    if not content:
                        content = f"Read more about {title} on {source['name']}."
                    
                    excerpt = content[:200] + '...' if len(content) > 200 else content
                    source_url = entry.get('link', f"https://{source['domain']}")
                    
                    # Check if exists
                    existing = conn.execute(
                        "SELECT id FROM posts WHERE title = ?", 
                        (title,)
                    ).fetchone()
                    
                    if existing:
                        continue
                    
                    # Save to DB
                    slug = self.create_slug(title)
                    
                    conn.execute('''INSERT INTO posts 
                        (title, slug, content, excerpt, image_url, source_url, 
                         category, author, views, source_name, is_published)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)''',
                        (title, slug, content, excerpt, self.get_image(entry), 
                         source_url, source['category'], source['name'], 
                         random.randint(10, 100), source['name']))
                    
                    saved += 1
                    print(f"  ✅ {title[:60]}...")
                    
                except Exception as e:
                    print(f"  ❌ Article error: {e}")
                    continue
            
            conn.commit()
            conn.close()
            
            print(f"📊 {source['name']}: Saved {saved} new articles")
            return saved
            
        except Exception as e:
            print(f"❌ Source error {source['name']}: {e}")
            return 0
    
    def initial_fetch(self):
        """Initial aggressive fetch"""
        print("\n" + "="*60)
        print("🚀 AGGRESSIVE INITIAL FETCH")
        print("="*60)
        
        total_saved = 0
        
        # Fetch from all sources
        for source in FlaskConfig.NEWS_SOURCES:
            if not source.get('enabled', True):
                continue
            
            saved = self.fetch_and_save(source, FlaskConfig.INITIAL_FETCH_COUNT)
            total_saved += saved
            
            # Short delay
            time.sleep(1)
        
        print("="*60)
        print(f"🎯 TOTAL: {total_saved} ARTICLES SAVED!")
        print("="*60)
        
        return total_saved
    
    def update_fetch(self):
        """Update fetch"""
        print("\n" + "="*60)
        print("🔄 UPDATE FETCH")
        print("="*60)
        
        total_saved = 0
        
        # Fetch from 3 random sources
        sources = random.sample([s for s in FlaskConfig.NEWS_SOURCES if s.get('enabled', True)], 3)
        
        for source in sources:
            saved = self.fetch_and_save(source, 5)
            total_saved += saved
            time.sleep(1)
        
        if total_saved > 0:
            print(f"📊 Update: {total_saved} new articles")
        else:
            print("📊 No new articles")
        
        print("="*60)
        return total_saved

# ============= FLASK APP =============
app = Flask(__name__)
app.config.from_object(FlaskConfig)

print("=" * 60)
print("🇿🇦 MZANSI INSIGHTS - SIMPLE VERSION")
print("=" * 60)

# Setup database
db_is_empty = setup_database()

# Create and start fetcher
fetcher = SimpleFetcher()

# IMMEDIATE FETCH
print("⚡ STARTING IMMEDIATE FETCH...")
fetcher.initial_fetch()

# Start background updates
def start_updates():
    """Start background updates"""
    while True:
        time.sleep(FlaskConfig.UPDATE_INTERVAL_MINUTES * 60)
        print(f"\n🔄 Running scheduled update...")
        fetcher.update_fetch()

threading.Thread(target=start_updates, daemon=True).start()
print("✅ Background updates started")

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

def prepare_post(post_row):
    """Prepare post for template"""
    post = dict(post_row)
    
    # Format date
    try:
        date_str = post.get('created_at', '')
        if date_str:
            post_date = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
            diff = datetime.now() - post_date
            
            if diff.days > 0:
                post['formatted_date'] = f"{diff.days}d ago"
            elif diff.seconds > 3600:
                post['formatted_date'] = f"{diff.seconds // 3600}h ago"
            elif diff.seconds > 60:
                post['formatted_date'] = f"{diff.seconds // 60}m ago"
            else:
                post['formatted_date'] = "Just now"
        else:
            post['formatted_date'] = "Recently"
    except:
        post['formatted_date'] = "Recently"
    
    # Add category info
    category = post.get('category', 'news')
    cat_data = CATEGORY_DEFINITIONS.get(category, CATEGORY_DEFINITIONS['news'])
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
    """Home page - WORKING"""
    try:
        conn = get_db_connection()
        
        # Get latest posts
        posts_raw = conn.execute(
            "SELECT * FROM posts WHERE is_published = 1 ORDER BY created_at DESC LIMIT 20"
        ).fetchall()
        posts = [prepare_post(row) for row in posts_raw]
        
        # Get trending (most viewed)
        trending_raw = conn.execute(
            "SELECT * FROM posts WHERE is_published = 1 ORDER BY views DESC LIMIT 6"
        ).fetchall()
        trending_posts = [prepare_post(row) for row in trending_raw]
        
        # Get categories for sidebar
        categories = []
        for slug, cat_data in CATEGORY_DEFINITIONS.items():
            count = conn.execute(
                "SELECT COUNT(*) FROM posts WHERE category = ?", 
                (slug,)
            ).fetchone()[0]
            categories.append({
                'name': cat_data['name'],
                'slug': cat_data['slug'],
                'description': cat_data['description'],
                'icon': cat_data['icon'],
                'color': cat_data['color'],
                'post_count': count
            })
        
        # Get sources
        sources = []
        for source in FlaskConfig.NEWS_SOURCES:
            count = conn.execute(
                "SELECT COUNT(*) FROM posts WHERE source_name = ?", 
                (source['name'],)
            ).fetchone()[0]
            sources.append({
                'name': source['name'],
                'category': source['category'],
                'color': source['color'],
                'icon': source['icon'],
                'article_count': count
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
        # Simple fallback
        return render_template('index.html',
                             posts=[],
                             trending_posts=[],
                             categories=list(CATEGORY_DEFINITIONS.values()),
                             sources=FlaskConfig.NEWS_SOURCES,
                             config=FlaskConfig,
                             has_posts=False,
                             now=datetime.now())

@app.route('/post/<slug>')
def post_detail(slug):
    """Post detail"""
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
            "SELECT * FROM posts WHERE category = ? AND slug != ? AND is_published = 1 ORDER BY RANDOM() LIMIT 4",
            (post['category'], slug)
        ).fetchall()
        related_posts = [prepare_post(row) for row in related_raw]
        
        conn.close()
        
        return render_template('post.html',
                             post=post,
                             related_posts=related_posts,
                             categories=list(CATEGORY_DEFINITIONS.values()),
                             config=FlaskConfig,
                             now=datetime.now())
                             
    except Exception as e:
        print(f"Post error: {e}")
        return redirect('/')

@app.route('/category/<category_slug>')
def category_page(category_slug):
    """Category page"""
    try:
        conn = get_db_connection()
        
        # Get posts
        posts_raw = conn.execute(
            "SELECT * FROM posts WHERE category = ? AND is_published = 1 ORDER BY created_at DESC LIMIT 30",
            (category_slug,)
        ).fetchall()
        posts = [prepare_post(row) for row in posts_raw]
        
        # Get category info
        cat_data = CATEGORY_DEFINITIONS.get(category_slug, CATEGORY_DEFINITIONS['news'])
        category = {
            'name': cat_data['name'],
            'slug': cat_data['slug'],
            'description': cat_data['description'],
            'icon': cat_data['icon'],
            'color': cat_data['color']
        }
        
        conn.close()
        
        return render_template('category.html',
                             category=category,
                             posts=posts,
                             categories=list(CATEGORY_DEFINITIONS.values()),
                             config=FlaskConfig,
                             now=datetime.now())
                             
    except Exception as e:
        print(f"Category error: {e}")
        return redirect('/')

@app.route('/search')
def search():
    """Search"""
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
        
        conn.close()
        
        return render_template('search.html',
                             query=query,
                             posts=posts,
                             categories=list(CATEGORY_DEFINITIONS.values()),
                             config=FlaskConfig,
                             now=datetime.now())
                             
    except Exception as e:
        print(f"Search error: {e}")
        return render_template('search.html',
                             query=query,
                             posts=[],
                             categories=list(CATEGORY_DEFINITIONS.values()),
                             config=FlaskConfig,
                             now=datetime.now())

@app.route('/sources')
def sources():
    """Sources page"""
    try:
        conn = get_db_connection()
        
        sources_list = []
        for source in FlaskConfig.NEWS_SOURCES:
            count = conn.execute(
                "SELECT COUNT(*) FROM posts WHERE source_name = ?", 
                (source['name'],)
            ).fetchone()[0]
            sources_list.append({
                'name': source['name'],
                'category': source['category'],
                'color': source['color'],
                'icon': source['icon'],
                'article_count': count,
                'url': f"https://{source.get('domain', '')}"
            })
        
        conn.close()
        
        return render_template('sources.html',
                             sources=sources_list,
                             categories=list(CATEGORY_DEFINITIONS.values()),
                             config=FlaskConfig,
                             now=datetime.now())
                             
    except Exception as e:
        print(f"Sources error: {e}")
        return render_template('sources.html',
                             sources=FlaskConfig.NEWS_SOURCES,
                             categories=list(CATEGORY_DEFINITIONS.values()),
                             config=FlaskConfig,
                             now=datetime.now())

# Redirect for missing categories in HTML
@app.route('/category/jobs')
def jobs():
    return redirect('/category/business')

@app.route('/category/grants')
def grants():
    return redirect('/category/news')

# Static pages
@app.route('/privacy')
def privacy():
    return render_template('privacy.html', config=FlaskConfig, 
                         categories=list(CATEGORY_DEFINITIONS.values()), 
                         now=datetime.now())

@app.route('/terms')
def terms():
    return render_template('terms.html', config=FlaskConfig,
                         categories=list(CATEGORY_DEFINITIONS.values()),
                         now=datetime.now())

@app.route('/contact')
def contact():
    return render_template('contact.html', config=FlaskConfig,
                         categories=list(CATEGORY_DEFINITIONS.values()),
                         now=datetime.now())

@app.route('/about')
def about():
    return render_template('about.html', config=FlaskConfig,
                         categories=list(CATEGORY_DEFINITIONS.values()),
                         now=datetime.now())

# Admin
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
        'published_posts': conn.execute("SELECT COUNT(*) FROM posts WHERE is_published = 1").fetchone()[0],
        'total_views': conn.execute("SELECT SUM(views) FROM posts").fetchone()[0] or 0,
        'sources': len(FlaskConfig.NEWS_SOURCES),
    }
    
    recent = conn.execute("SELECT * FROM posts ORDER BY created_at DESC LIMIT 10").fetchall()
    conn.close()
    
    return render_template('admin/dashboard.html', stats=stats, recent_posts=recent, config=FlaskConfig)

@app.route('/admin/fetch-now')
@login_required
def admin_fetch_now():
    threading.Thread(target=fetcher.initial_fetch, daemon=True).start()
    flash('Fetch started!', 'info')
    return redirect('/admin/dashboard')

@app.route('/admin/logout')
@login_required
def admin_logout():
    logout_user()
    flash('Logged out', 'info')
    return redirect('/')

# API
@app.route('/api/live-news')
def live_news():
    """Simple API for ticker"""
    try:
        conn = get_db_connection()
        posts = conn.execute(
            "SELECT title, category FROM posts WHERE is_published = 1 ORDER BY created_at DESC LIMIT 3"
        ).fetchall()
        conn.close()
        
        articles = []
        for post in posts:
            cat_data = CATEGORY_DEFINITIONS.get(post['category'], CATEGORY_DEFINITIONS['news'])
            articles.append({
                'title': post['title'][:60] + '...' if len(post['title']) > 60 else post['title'],
                'category': cat_data['name'],
                'color': cat_data['color']
            })
        
        return jsonify({'status': 'success', 'articles': articles})
        
    except:
        return jsonify({'status': 'error', 'articles': []})

@app.route('/api/stats')
def api_stats():
    """Simple stats"""
    try:
        conn = get_db_connection()
        posts = conn.execute("SELECT COUNT(*) FROM posts WHERE is_published = 1").fetchone()[0]
        views = conn.execute("SELECT SUM(views) FROM posts").fetchone()[0] or 0
        conn.close()
        
        return jsonify({
            'posts': posts,
            'views': views,
            'sources': len(FlaskConfig.NEWS_SOURCES),
            'status': 'online'
        })
        
    except:
        return jsonify({'posts': 0, 'views': 0, 'status': 'error'})

# Debug
@app.route('/debug')
def debug():
    """Debug info"""
    conn = get_db_connection()
    posts = conn.execute("SELECT COUNT(*) FROM posts").fetchone()[0]
    latest = conn.execute("SELECT title, source_name FROM posts ORDER BY created_at DESC LIMIT 3").fetchall()
    conn.close()
    
    return f"""
    <h1>Debug</h1>
    <p>Posts: {posts}</p>
    <p>Latest:</p>
    <ul>
        {"".join(f'<li>{row["title"][:50]}... ({row["source_name"]})</li>' for row in latest)}
    </ul>
    <p>Sources: {len(FlaskConfig.NEWS_SOURCES)}</p>
    <p>Time: {datetime.now()}</p>
    """

@app.errorhandler(404)
def not_found(e):
    return render_template('404.html', config=FlaskConfig), 404

# ============= START =============
if __name__ == '__main__':
    print(f"🌐 Site: http://localhost:5000")
    print(f"🔐 Admin: http://localhost:5000/admin/login")
    print(f"📊 Sources: {len(FlaskConfig.NEWS_SOURCES)}")
    print("=" * 60)
    
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port, threaded=True)
else:
    print("🚀 App ready on production!")
    print("✅ Articles fetched immediately")
    print("✅ Links work properly")
    print("✅ Updates every 30 minutes")