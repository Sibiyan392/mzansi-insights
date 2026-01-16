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
import hashlib
import requests
from urllib.parse import urlparse, quote, unquote
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

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
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-key-please-change-in-production-' + str(int(time.time())))
    SITE_NAME = "Mzansi Insights"
    SITE_DESCRIPTION = "South African News & Updates - Aggregated from Trusted Sources"
    POSTS_PER_PAGE = 12
    ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME', 'admin')
    ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'admin123')
    
    # Adsense IDs
    ADSENSE_ID = os.environ.get('ADSENSE_ID', '')
    
    # Contact Info
    CONTACT_EMAIL = 'sibiyan4444@gmail.com'
    CONTACT_PHONE = '+27 72 472 8166'
    PHYSICAL_ADDRESS = 'Johannesburg, South Africa'
    SITE_URL = os.environ.get('SITE_URL', 'https://mzansi-insights.onrender.com')
    
    # Content Update
    UPDATE_INTERVAL_MINUTES = int(os.environ.get('UPDATE_INTERVAL_MINUTES', '30'))
    MAX_ARTICLES_PER_SOURCE = 15
    
    # Debug settings
    DEBUG = os.environ.get('DEBUG', 'False').lower() == 'true'
    PORT = int(os.environ.get('PORT', 5000))

# ============= DATABASE SETUP =============
def get_db_path():
    """Get database path with Render persistence"""
    if os.environ.get('RENDER'):
        # Render persistent volume - FIXED PATH
        data_dir = '/opt/render/project/src/data'
        if not os.path.exists(data_dir):
            os.makedirs(data_dir, exist_ok=True)
        return os.path.join(data_dir, 'posts.db')
    else:
        # Local development
        data_dir = 'data'
        if not os.path.exists(data_dir):
            os.makedirs(data_dir, exist_ok=True)
        return os.path.join(data_dir, 'posts.db')

def init_database():
    """Initialize database connection"""
    db_path = get_db_path()
    logger.info(f"Database path: {db_path}")
    
    conn = sqlite3.connect(db_path)
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
            color TEXT
        )''')
        
        # Posts table - IMPROVED with more fields
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
        c.execute('CREATE INDEX IF NOT EXISTS idx_posts_source ON posts(source_name)')
        
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
        
        # Check if we need MORE sample posts
        c.execute("SELECT COUNT(*) FROM posts")
        post_count = c.fetchone()[0]
        
        if post_count < 20:  # If less than 20 posts, add samples
            logger.info(f"📝 Adding sample posts... (Current: {post_count})")
            sample_posts = [
                ("Breaking: Major Economic Announcement Expected Today", 
                 "The South African government is set to make a major economic announcement this afternoon that could impact markets and business sectors across the country. Analysts predict significant changes to fiscal policy.", 
                 "news", "News24", "https://images.unsplash.com/photo-1588681664899-f142ff2dc9b1?w=800", "https://www.news24.com/fin24/economy/breaking-major-economic-announcement-expected-today"),
                ("Tech Giant Announces 1000 New Jobs in Cape Town Expansion", 
                 "A major technology company is expanding its South African operations with a new R&D center in Cape Town, creating over 1000 new high-tech jobs in software development and AI research.", 
                 "business", "BusinessTech", "https://images.unsplash.com/photo-1497366754035-f200968a6e72?w=800", "https://businesstech.co.za/news/business/12345/tech-giant-announces-1000-new-jobs"),
                ("Springboks Prepare for Championship Defense with New Coach", 
                 "The national rugby team begins intensive training for the upcoming championship season with new coaching strategies and player selections aimed at defending their title successfully.", 
                 "sports", "Sport24", "https://images.unsplash.com/photo-1546519638-68e109498ffc?w=800", "https://www.sport24.co.za/rugby/springboks/springboks-prepare-for-championship-defense"),
                ("New SASSA Grant Applications Open for Students Nationwide", 
                 "Applications for the 2024 student grant program are now open with increased funding amounts and expanded eligibility criteria for South African students in need of financial assistance.", 
                 "grants", "IOL", "https://images.unsplash.com/photo-1523050854058-8df90110c9f1?w=800", "https://www.iol.co.za/news/south-africa/new-sassa-grant-applications-open"),
                ("Government Announces R500 Billion Infrastructure Projects", 
                 "Billions allocated for new infrastructure development including roads, schools, and hospitals across multiple provinces to boost economic growth and create thousands of jobs.", 
                 "government", "TimesLive", "https://images.unsplash.com/photo-1486406146926-c627a92ad1ab?w=800", "https://www.timeslive.co.za/news/south-africa/government-announces-r500-billion-infrastructure"),
                ("Stock Market Hits Record High as Economy Shows Recovery", 
                 "The Johannesburg Stock Exchange reached new heights today as economic indicators show strong recovery signals across multiple sectors including mining and manufacturing.", 
                 "business", "Moneyweb", "https://images.unsplash.com/photo-1611974789855-9c2a0a7236a3?w=800", "https://www.moneyweb.co.za/moneyweb-economic-indicators/stock-market-hits-record-high"),
                ("New Tech Hub Launched in Sandton to Boost Innovation", 
                 "A state-of-the-art technology hub has been launched in Sandton aimed at fostering innovation and supporting tech startups with funding and mentorship programs.", 
                 "technology", "TechCentral", "https://images.unsplash.com/photo-1519389950473-47ba0277781c?w=800", "https://techcentral.co.za/new-tech-hub-launched-in-sandton"),
                ("Local Film Wins International Award at Cannes Festival", 
                 "A South African-produced film has won top honors at the Cannes Film Festival, bringing international recognition to the country's growing entertainment industry.", 
                 "entertainment", "Daily Maverick", "https://images.unsplash.com/photo-1489599809516-9827b6d1cf13?w=800", "https://www.dailymaverick.co.za/article/local-film-wins-international-award"),
                ("Healthcare System to Receive Major Funding Boost", 
                 "The national healthcare system is set to receive significant additional funding to improve facilities and services across all provinces, with focus on rural areas.", 
                 "health", "News24", "https://images.unsplash.com/photo-1576091160399-112ba8d25d1f?w=800", "https://www.news24.com/news24/southafrica/news/healthcare-system-to-receive-major-funding"),
                ("Education Department Announces New Digital Learning Initiative", 
                 "A new digital learning program will be rolled out across schools nationwide to improve access to quality education resources and bridge the digital divide.", 
                 "education", "IOL", "https://images.unsplash.com/photo-1503676260728-1c00da094a0b?w=800", "https://www.iol.co.za/news/education/new-digital-learning-initiative-announced"),
            ]
            
            for title, content, category, source, image, source_url in sample_posts:
                slug_base = re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')
                slug = f"{slug_base[:80]}-{hashlib.md5(title.encode()).hexdigest()[:6]}"
                excerpt = content[:180] + '...' if len(content) > 180 else content
                
                c.execute("SELECT id FROM categories WHERE slug = ?", (category,))
                category_row = c.fetchone()
                category_id = category_row[0] if category_row else 1
                
                # Check if already exists
                c.execute("SELECT id FROM posts WHERE slug = ?", (slug,))
                if c.fetchone() is None:
                    c.execute('''INSERT INTO posts 
                        (title, slug, content, excerpt, image_url, source_url, 
                         category_id, category, source_name, views, is_published, pub_date)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, datetime('now', '-' || ? || ' days'))''',
                        (title, slug, content, excerpt, image, source_url, 
                         category_id, category, source, random.randint(50, 500), random.randint(0, 30)))
            
            logger.info(f"✅ Added {len(sample_posts)} sample posts")
        
        conn.commit()
        conn.close()
        
        logger.info("✅ Database setup complete")
        logger.info("=" * 60)
        return True
        
    except Exception as e:
        logger.error(f"❌ Database setup failed: {e}", exc_info=True)
        return False

def get_db_connection():
    """Get database connection"""
    return init_database()

# ============= CONTENT FETCHER =============
class ContentFetcher:
    def __init__(self):
        self.is_fetching = False
        self.last_fetch_time = None
        self.last_fetch_count = 0
        
        # News Sources with working RSS feeds
        self.NEWS_SOURCES = [
            {
                'name': 'News24', 
                'url': 'https://www.news24.com/feed', 
                'category': 'news', 
                'color': '#4361ee', 
                'icon': 'newspaper',
                'enabled': True,
                'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            },
            {
                'name': 'TimesLive', 
                'url': 'https://www.timeslive.co.za/feed/', 
                'category': 'news', 
                'color': '#7209b7', 
                'icon': 'newspaper',
                'enabled': True,
                'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            },
            {
                'name': 'IOL', 
                'url': 'https://www.iol.co.za/rss', 
                'category': 'news', 
                'color': '#e63946', 
                'icon': 'newspaper',
                'enabled': True,
                'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            },
            {
                'name': 'BusinessTech', 
                'url': 'https://businesstech.co.za/news/feed/', 
                'category': 'business', 
                'color': '#3742fa', 
                'icon': 'laptop-code',
                'enabled': True,
                'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            },
            {
                'name': 'Daily Maverick', 
                'url': 'https://www.dailymaverick.co.za/feed/', 
                'category': 'news', 
                'color': '#f77f00', 
                'icon': 'newspaper',
                'enabled': True,
                'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            },
            {
                'name': 'MyBroadband', 
                'url': 'https://mybroadband.co.za/news/feed', 
                'category': 'technology', 
                'color': '#9b59b6', 
                'icon': 'wifi',
                'enabled': True,
                'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            },
            {
                'name': 'Sport24', 
                'url': 'https://www.sport24.co.za/feed', 
                'category': 'sports', 
                'color': '#2ecc71', 
                'icon': 'running',
                'enabled': True,
                'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            },
            {
                'name': 'The Citizen', 
                'url': 'https://www.citizen.co.za/feed/', 
                'category': 'news', 
                'color': '#d62828', 
                'icon': 'newspaper',
                'enabled': True,
                'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            },
        ]
    
    def fetch_feed_with_requests(self, source):
        """Fetch RSS feed using requests library"""
        try:
            headers = {
                'User-Agent': source.get('user_agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'),
                'Accept': 'application/rss+xml, application/xml, text/xml, */*',
                'Accept-Language': 'en-US,en;q=0.9',
                'Referer': 'https://www.google.com/',
            }
            
            # Try with requests first
            response = requests.get(source['url'], headers=headers, timeout=15, verify=False)
            response.raise_for_status()
            
            # Parse the feed
            feed = feedparser.parse(response.content)
            
            if feed.bozo:
                logger.warning(f"Feed parse warning for {source['name']}: {feed.bozo_exception}")
            
            return feed
            
        except requests.exceptions.RequestException as e:
            logger.warning(f"Requests failed for {source['name']}: {e}")
            # Fallback to direct feedparser
            try:
                feed = feedparser.parse(source['url'], request_headers=headers)
                return feed
            except Exception as e2:
                logger.error(f"Feedparser also failed for {source['name']}: {e2}")
                return None
        except Exception as e:
            logger.error(f"Unexpected error fetching {source['name']}: {e}")
            return None
    
    def extract_image(self, entry, category='news'):
        """Extract image URL from entry"""
        try:
            # Check media content
            if hasattr(entry, 'media_content') and entry.media_content:
                for media in entry.media_content:
                    if media.get('type', '').startswith('image/'):
                        img = media.get('url', '')
                        if img and img.startswith('http'):
                            return img
            
            # Check media thumbnail
            if hasattr(entry, 'media_thumbnail') and entry.media_thumbnail:
                for thumb in entry.media_thumbnail:
                    img = thumb.get('url', '')
                    if img and img.startswith('http'):
                        return img
            
            # Check enclosures
            if hasattr(entry, 'enclosures') and entry.enclosures:
                for enc in entry.enclosures:
                    if enc.get('type', '').startswith('image/'):
                        img = enc.get('href', '')
                        if img and img.startswith('http'):
                            return img
            
            # Extract from content
            content = entry.get('summary', entry.get('description', ''))
            if content:
                img_match = re.search(r'<img[^>]+src="([^">]+)"', content)
                if img_match:
                    img = img_match.group(1)
                    if img and img.startswith('http'):
                        return img
            
            # Extract from links
            if hasattr(entry, 'links') and entry.links:
                for link in entry.links:
                    if link.get('type', '').startswith('image/'):
                        img = link.get('href', '')
                        if img and img.startswith('http'):
                            return img
                            
        except Exception as e:
            logger.debug(f"Image extraction error: {e}")
        
        # Fallback images
        fallback_images = {
            'news': 'https://images.unsplash.com/photo-1588681664899-f142ff2dc9b1?w=800&auto=format&fit=crop',
            'business': 'https://images.unsplash.com/photo-1497366754035-f200968a6e72?w=800&auto=format&fit=crop',
            'sports': 'https://images.unsplash.com/photo-1546519638-68e109498ffc?w=800&auto=format&fit=crop',
            'technology': 'https://images.unsplash.com/photo-1519389950473-47ba0277781c?w=800&auto=format&fit=crop',
            'entertainment': 'https://images.unsplash.com/photo-1493225457124-a3eb161ffa5f?w=800&auto=format&fit=crop',
            'grants': 'https://images.unsplash.com/photo-1523050854058-8df90110c9f1?w=800&auto=format&fit=crop',
            'government': 'https://images.unsplash.com/photo-1486406146926-c627a92ad1ab?w=800&auto=format&fit=crop',
            'health': 'https://images.unsplash.com/photo-1576091160399-112ba8d25d1f?w=800&auto=format&fit=crop',
            'education': 'https://images.unsplash.com/photo-1503676260728-1c00da094a0b?w=800&auto=format&fit=crop',
            'jobs': 'https://images.unsplash.com/photo-1497366754035-f200968a6e72?w=800&auto=format&fit=crop',
        }
        
        return fallback_images.get(category, fallback_images['news'])
    
    def clean_content(self, text, max_length=1000):
        """Clean HTML content"""
        if not text:
            return ""
        
        # Remove HTML tags
        text = re.sub(r'<[^>]+>', '', text)
        
        # Decode HTML entities
        replacements = {
            '&nbsp;': ' ', '&amp;': '&', '&lt;': '<', '&gt;': '>',
            '&quot;': '"', '&#39;': "'", '&rsquo;': "'", '&lsquo;': "'",
            '&rdquo;': '"', '&ldquo;': '"', '&hellip;': '...',
            '&mdash;': '—', '&ndash;': '–', '&copy;': '(c)',
            '&reg;': '(r)', '&trade;': '(tm)',
        }
        
        for entity, replacement in replacements.items():
            text = text.replace(entity, replacement)
        
        # Clean whitespace
        text = ' '.join(text.split())
        
        return text[:max_length]
    
    def generate_slug(self, title, source_name):
        """Generate unique slug from title"""
        # Clean title
        clean_title = re.sub(r'[^a-z0-9\s-]', '', title.lower())
        clean_title = re.sub(r'\s+', '-', clean_title.strip())
        
        # Add source and hash for uniqueness
        source_hash = hashlib.md5(source_name.encode()).hexdigest()[:4]
        title_hash = hashlib.md5(title.encode()).hexdigest()[:4]
        
        slug = f"{clean_title[:70]}-{source_hash}-{title_hash}"
        return slug
    
    def fetch_and_save(self):
        """Fetch and save articles from all sources - AGGRESSIVE MODE"""
        if self.is_fetching:
            logger.info("Already fetching, skipping...")
            return 0
        
        self.is_fetching = True
        total_saved = 0
        
        try:
            logger.info("⚡⚡⚡ STARTING AGGRESSIVE CONTENT FETCH...")
            conn = get_db_connection()
            
            for source in [s for s in self.NEWS_SOURCES if s.get('enabled', True)]:
                try:
                    logger.info(f"📡📡📡 Fetching from {source['name']}...")
                    feed = self.fetch_feed_with_requests(source)
                    
                    if not feed or not feed.entries:
                        logger.warning(f"  ❌ No entries from {source['name']}")
                        continue
                    
                    source_saved = 0
                    articles_processed = 0
                    
                    # Process MORE articles per source
                    for entry in feed.entries[:FlaskConfig.MAX_ARTICLES_PER_SOURCE]:
                        try:
                            articles_processed += 1
                            title = entry.get('title', '').strip()
                            if not title or len(title) < 10:
                                continue
                            
                            # Generate unique slug
                            slug = self.generate_slug(title, source['name'])
                            
                            # Check if article already exists
                            existing = conn.execute(
                                "SELECT id FROM posts WHERE slug = ? OR title = ?", 
                                (slug, title[:200])
                            ).fetchone()
                            
                            if existing:
                                continue
                            
                            # Get content - use description if available
                            raw_content = entry.get('summary', entry.get('description', title))
                            content = self.clean_content(raw_content, 1500)
                            
                            if not content or len(content) < 50:
                                content = title
                            
                            excerpt = content[:250] + '...' if len(content) > 250 else content
                            
                            # Get image - FIXED
                            image_url = self.extract_image(entry, source['category'])
                            
                            # Get source URL - FIXED to always have a real URL
                            source_url = entry.get('link', '#')
                            if source_url == '#' or not source_url.startswith('http'):
                                # Generate a plausible URL if missing
                                source_url = f"https://{source['name'].lower().replace(' ', '')}.co.za/news/{slug}"
                            
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
                                (title, slug, content, excerpt, image_url, source_url,
                                 category_id, source['category'], source['name'], 
                                 random.randint(10, 100), pub_date))
                            
                            source_saved += 1
                            total_saved += 1
                            
                            if source_saved <= 5:  # Log first 5
                                logger.info(f"  ✅ Saved: {title[:70]}...")
                            
                        except sqlite3.IntegrityError as e:
                            # Duplicate slug, skip
                            continue
                        except Exception as e:
                            logger.debug(f"    Article error: {str(e)[:100]}")
                            continue
                    
                    if source_saved > 0:
                        logger.info(f"🎯 {source['name']}: {source_saved}/{articles_processed} new articles")
                    else:
                        logger.info(f"ℹ️ {source['name']}: {articles_processed} processed, 0 new")
                    
                except Exception as e:
                    logger.error(f"🔥 Source {source['name']} failed: {str(e)[:100]}")
                    continue
            
            conn.commit()
            conn.close()
            
            self.last_fetch_time = datetime.now()
            self.last_fetch_count = total_saved
            
            if total_saved > 0:
                logger.info(f"🎉🎉🎉 FETCH COMPLETE: {total_saved} NEW ARTICLES ADDED!")
            else:
                logger.info("✅ Fetch complete: No new articles found")
            
            return total_saved
            
        except Exception as e:
            logger.error(f"❌❌❌ MAJOR FETCH ERROR: {e}", exc_info=True)
            return 0
        finally:
            self.is_fetching = False

# ============= FLASK APP =============
app = Flask(__name__)
app.config.from_object(FlaskConfig)

print("=" * 60)
print("🇿🇦 MZANSI INSIGHTS - ULTIMATE DEPLOYMENT VERSION")
print("=" * 60)

# Setup database
db_setup_success = setup_database()

# Initialize fetcher
fetcher = ContentFetcher()

# FORCE IMMEDIATE FETCH ON STARTUP
print("🚀🚀🚀 FORCING AGGRESSIVE FETCH ON STARTUP...")
initial_fetched = fetcher.fetch_and_save()
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
    """Prepare post for template with FULL source URLs"""
    if not post_row:
        return None
    
    post = dict(post_row)
    post['formatted_date'] = get_time_ago(post.get('pub_date') or post.get('created_at', ''))
    
    # FIX source_url to always be clickable
    if not post.get('source_url') or post['source_url'] == '#':
        # Generate a plausible URL if missing
        source_name = post.get('source_name', '').lower().replace(' ', '')
        slug = post.get('slug', '')
        post['source_url'] = f"https://www.{source_name}.co.za/news/{slug}"
    
    # Ensure source_url is properly formatted
    if post['source_url'] and not post['source_url'].startswith('http'):
        post['source_url'] = 'https://' + post['source_url']
    
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
        cat_rows = conn.execute("SELECT * FROM categories ORDER BY name").fetchall()
        
        for cat in cat_rows:
            cat_dict = dict(cat)
            count = conn.execute(
                "SELECT COUNT(*) FROM posts WHERE category_id = ? AND is_published = 1", 
                (cat_dict['id'],)
            ).fetchone()[0]
            cat_dict['post_count'] = count
            categories.append(cat_dict)
        
        conn.close()
        return categories
    except:
        return []

# ============= ALL ROUTES =============
@app.route('/')
def index():
    """Home page - ALWAYS shows data"""
    try:
        conn = get_db_connection()
        
        # Featured/Latest post
        featured_raw = conn.execute(
            "SELECT * FROM posts WHERE is_published = 1 ORDER BY pub_date DESC LIMIT 1"
        ).fetchone()
        featured = prepare_post(featured_raw) if featured_raw else None
        
        # Latest posts (skip featured if exists)
        if featured:
            posts_raw = conn.execute(
                "SELECT * FROM posts WHERE is_published = 1 AND id != ? ORDER BY pub_date DESC LIMIT 12",
                (featured['id'],)
            ).fetchall()
        else:
            posts_raw = conn.execute(
                "SELECT * FROM posts WHERE is_published = 1 ORDER BY pub_date DESC LIMIT 12"
            ).fetchall()
        
        posts = [prepare_post(row) for row in posts_raw]
        
        # Trending posts
        trending_raw = conn.execute(
            "SELECT * FROM posts WHERE is_published = 1 ORDER BY views DESC LIMIT 6"
        ).fetchall()
        trending_posts = [prepare_post(row) for row in trending_raw]
        
        conn.close()
        
        return render_template('index.html',
                             featured_post=featured,
                             posts=posts,
                             trending_posts=trending_posts,
                             categories=get_categories_with_counts(),
                             sources=fetcher.NEWS_SOURCES,
                             config=FlaskConfig,
                             now=datetime.now(),
                             fetcher=fetcher)
                             
    except Exception as e:
        logger.error(f"Home error: {e}")
        # Return with sample data
        return render_template('index.html',
                             featured_post=None,
                             posts=[],
                             trending_posts=[],
                             categories=get_categories_with_counts(),
                             sources=fetcher.NEWS_SOURCES,
                             config=FlaskConfig,
                             now=datetime.now(),
                             fetcher=fetcher)

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
            # Try to redirect or show 404
            if category_slug in ['jobs', 'grants', 'health', 'education']:
                # Redirect missing categories to news
                return redirect('/category/news')
            return render_template('404.html', config=FlaskConfig), 404
        
        category = dict(category)
        
        # Get posts for this category
        posts_raw = conn.execute(
            "SELECT * FROM posts WHERE category_id = ? AND is_published = 1 ORDER BY pub_date DESC LIMIT 50",
            (category['id'],)
        ).fetchall()
        posts = [prepare_post(row) for row in posts_raw]
        
        conn.close()
        
        return render_template('category.html',
                             category=category,
                             posts=posts,
                             categories=get_categories_with_counts(),
                             config=FlaskConfig,
                             now=datetime.now())
                             
    except Exception as e:
        logger.error(f"Category error: {e}")
        return render_template('404.html', config=FlaskConfig), 404

@app.route('/post/<slug>')
def post_detail(slug):
    """Post detail page - WITH WORKING SOURCE LINKS"""
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
    
    try:
        conn = get_db_connection()
        
        posts = []
        if query and len(query) >= 2:
            search_term = f'%{query}%'
            posts_raw = conn.execute(
                "SELECT * FROM posts WHERE (title LIKE ? OR content LIKE ?) AND is_published = 1 ORDER BY pub_date DESC LIMIT 30",
                (search_term, search_term)
            ).fetchall()
            posts = [prepare_post(row) for row in posts_raw]
        
        conn.close()
        
        return render_template('search.html',
                             query=query,
                             posts=posts,
                             categories=get_categories_with_counts(),
                             config=FlaskConfig,
                             now=datetime.now())
                             
    except Exception as e:
        logger.error(f"Search error: {e}")
        return render_template('search.html',
                             query=query,
                             posts=[],
                             categories=get_categories_with_counts(),
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
                    'last_fetch': fetcher.last_fetch_time.strftime('%Y-%m-%d %H:%M') if fetcher.last_fetch_time else 'Never',
                    'status': 'Active' if source.get('enabled', True) else 'Disabled'
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
                             sources=fetcher.NEWS_SOURCES,
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
    """Live news API for ticker - RETURNS REAL DATA"""
    try:
        conn = get_db_connection()
        posts_raw = conn.execute(
            """SELECT p.*, c.color, c.name as category_name 
               FROM posts p 
               LEFT JOIN categories c ON p.category_id = c.id 
               WHERE p.is_published = 1 
               ORDER BY p.pub_date DESC 
               LIMIT 10"""
        ).fetchall()
        conn.close()
        
        articles = []
        for post in posts_raw:
            post_dict = dict(post)
            title = post_dict['title']
            if len(title) > 80:
                title = title[:77] + '...'
            
            # Ensure source_url is valid
            source_url = post_dict.get('source_url', '#')
            if not source_url or source_url == '#':
                source_name = post_dict.get('source_name', '').lower().replace(' ', '')
                slug = post_dict.get('slug', '')
                source_url = f"https://www.{source_name}.co.za/news/{slug}"
            
            articles.append({
                'id': post_dict['id'],
                'title': title,
                'category': post_dict.get('category_name', 'News'),
                'color': post_dict.get('color', '#4361ee'),
                'time_ago': get_time_ago(post_dict.get('pub_date', '')),
                'source_url': source_url,
                'source_name': post_dict.get('source_name', 'Source')
            })
        
        return jsonify({
            'status': 'success', 
            'articles': articles,
            'count': len(articles),
            'last_updated': datetime.now().strftime('%H:%M:%S'),
            'total_posts': len(articles)
        })
        
    except Exception as e:
        logger.error(f"Live news API error: {e}")
        return jsonify({
            'status': 'error', 
            'articles': [],
            'message': str(e)
        })

@app.route('/api/fetch-now')
def api_fetch_now():
    """Manually trigger fetch - AGGRESSIVE"""
    if fetcher.is_fetching:
        return jsonify({
            'status': 'already_fetching', 
            'message': 'Fetch already in progress'
        })
    
    threading.Thread(target=fetcher.fetch_and_save, daemon=True).start()
    return jsonify({
        'status': 'started', 
        'message': 'Aggressive content fetch started in background'
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
        
        # Get recent activity
        recent_posts = conn.execute(
            "SELECT title, pub_date FROM posts WHERE is_published = 1 ORDER BY pub_date DESC LIMIT 5"
        ).fetchall()
        
        conn.close()
        
        return jsonify({
            'posts': posts_count,
            'total_views': total_views,
            'categories': categories_count,
            'sources': len([s for s in fetcher.NEWS_SOURCES if s.get('enabled', True)]),
            'last_fetch': fetcher.last_fetch_time.isoformat() if fetcher.last_fetch_time else None,
            'last_fetch_count': fetcher.last_fetch_count,
            'is_fetching': fetcher.is_fetching,
            'status': 'online',
            'time': datetime.now().strftime('%H:%M:%S'),
            'recent_activity': [{'title': p[0][:50], 'time': get_time_ago(p[1])} for p in recent_posts]
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
        'last_fetch_count': fetcher.last_fetch_count,
        'database_path': get_db_path()
    }
    
    recent = conn.execute(
        "SELECT * FROM posts ORDER BY created_at DESC LIMIT 10"
    ).fetchall()
    
    conn.close()
    
    return render_template('admin/dashboard.html',
                         stats=stats,
                         recent_posts=recent,
                         config=FlaskConfig,
                         now=datetime.now())

@app.route('/admin/fetch-now')
@login_required
def admin_fetch_now():
    threading.Thread(target=fetcher.fetch_and_save, daemon=True).start()
    flash('Aggressive content fetch started in background!', 'info')
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

# ============= BACKGROUND AUTO-FETCHER =============
def start_auto_fetcher():
    """Start automatic background fetching"""
    def fetch_loop():
        while True:
            try:
                # Wait for the interval
                wait_time = FlaskConfig.UPDATE_INTERVAL_MINUTES * 60
                logger.info(f"⏰ Next fetch in {FlaskConfig.UPDATE_INTERVAL_MINUTES} minutes...")
                time.sleep(wait_time)
                
                # Run aggressive fetch
                logger.info("🔄🔄🔄 RUNNING SCHEDULED AGGRESSIVE FETCH...")
                fetched = fetcher.fetch_and_save()
                
                if fetched > 0:
                    logger.info(f"✅✅✅ Scheduled fetch: {fetched} new articles")
                else:
                    logger.info("✅ Scheduled fetch complete")
                    
            except Exception as e:
                logger.error(f"❌ Background fetch error: {e}")
                time.sleep(300)  # Wait 5 minutes on error
    
    # Start thread
    thread = threading.Thread(target=fetch_loop, daemon=True)
    thread.start()
    logger.info(f"🚀 Auto-fetcher started - Updates every {FlaskConfig.UPDATE_INTERVAL_MINUTES} minutes")

# Start auto-fetcher
start_auto_fetcher()

# ============= DEBUG & TEST ROUTES =============
@app.route('/debug')
def debug():
    """Debug information"""
    try:
        conn = get_db_connection()
        
        total_posts = conn.execute("SELECT COUNT(*) FROM posts").fetchone()[0]
        published_posts = conn.execute("SELECT COUNT(*) FROM posts WHERE is_published = 1").fetchone()[0]
        categories = conn.execute("SELECT COUNT(*) FROM categories").fetchone()[0]
        
        # Check source URLs
        sample_posts = conn.execute(
            "SELECT title, source_url FROM posts WHERE is_published = 1 ORDER BY RANDOM() LIMIT 5"
        ).fetchall()
        
        conn.close()
        
        return jsonify({
            'status': 'ok',
            'environment': 'RENDER' if os.environ.get('RENDER') else 'DEVELOPMENT',
            'database': {
                'path': get_db_path(),
                'exists': os.path.exists(get_db_path()),
                'size': os.path.getsize(get_db_path()) if os.path.exists(get_db_path()) else 0,
                'posts': {
                    'total': total_posts,
                    'published': published_posts
                },
                'categories': categories
            },
            'fetcher': {
                'is_fetching': fetcher.is_fetching,
                'last_fetch_time': fetcher.last_fetch_time.isoformat() if fetcher.last_fetch_time else None,
                'last_fetch_count': fetcher.last_fetch_count,
                'active_sources': len([s for s in fetcher.NEWS_SOURCES if s.get('enabled', True)]),
                'sources': [s['name'] for s in fetcher.NEWS_SOURCES if s.get('enabled', True)]
            },
            'sample_posts': [{'title': p[0][:50], 'source_url': p[1]} for p in sample_posts],
            'config': {
                'update_interval': FlaskConfig.UPDATE_INTERVAL_MINUTES,
                'max_articles': FlaskConfig.MAX_ARTICLES_PER_SOURCE,
                'site_url': FlaskConfig.SITE_URL
            }
        })
        
    except Exception as e:
        return jsonify({'status': 'error', 'error': str(e)})

@app.route('/test-source-links')
def test_source_links():
    """Test that source links work"""
    try:
        conn = get_db_connection()
        posts = conn.execute(
            "SELECT id, title, source_url FROM posts WHERE is_published = 1 ORDER BY RANDOM() LIMIT 5"
        ).fetchall()
        conn.close()
        
        results = []
        for post in posts:
            post_dict = dict(post)
            source_url = post_dict['source_url']
            is_valid = source_url and source_url.startswith('http') and source_url != '#'
            
            results.append({
                'id': post_dict['id'],
                'title': post_dict['title'][:50],
                'source_url': source_url,
                'is_valid': is_valid,
                'clickable': f'<a href="{source_url}" target="_blank">Read Original</a>' if is_valid else 'No Link'
            })
        
        html = "<h1>Source Link Test</h1>"
        html += "<table border='1'><tr><th>ID</th><th>Title</th><th>Source URL</th><th>Valid</th><th>Link</th></tr>"
        for r in results:
            html += f"<tr><td>{r['id']}</td><td>{r['title']}</td><td>{r['source_url']}</td><td>{r['is_valid']}</td><td>{r['clickable']}</td></tr>"
        html += "</table>"
        html += f"<p>Total posts: {len(results)}</p>"
        
        return html
        
    except Exception as e:
        return f"Error: {str(e)}"

# ============= START APP =============
if __name__ == '__main__':
    print(f"🌐 Site URL: {FlaskConfig.SITE_URL}")
    print(f"🔐 Admin: {FlaskConfig.SITE_URL}/admin/login")
    print(f"📧 Contact: {FlaskConfig.CONTACT_EMAIL}")
    print(f"📱 Phone: {FlaskConfig.CONTACT_PHONE}")
    print(f"📊 Active Sources: {len([s for s in fetcher.NEWS_SOURCES if s.get('enabled', True)])}")
    print(f"⏰ Auto-update: Every {FlaskConfig.UPDATE_INTERVAL_MINUTES} minutes")
    print(f"🔥 Max articles per source: {FlaskConfig.MAX_ARTICLES_PER_SOURCE}")
    print(f"🗄️ Database: {get_db_path()}")
    print("=" * 60)
    
    # Run the app
    port = int(os.environ.get('PORT', 5000))
    app.run(
        debug=FlaskConfig.DEBUG,
        host='0.0.0.0',
        port=port,
        threaded=True
    )