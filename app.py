# Python 3.13+ compatibility fix
import cgi_fix  # We'll create this file

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
from urllib.parse import urlparse, quote, unquote, urljoin
import urllib3
from bs4 import BeautifulSoup
import html
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
    
    # Google AdSense Auto Ads
    ADSENSE_ENABLED = True
    ADSENSE_PUBLISHER_ID = 'ca-pub-9621668436424790'
    
    # Google Analytics
    GOOGLE_ANALYTICS_ID = 'G-9LWJJPQ5LK'
    
    # Contact Info
    CONTACT_EMAIL = 'sibiyan4444@gmail.com'
    CONTACT_PHONE = '+27 72 472 8166'
    PHYSICAL_ADDRESS = 'Johannesburg, South Africa'
    SITE_URL = os.environ.get('SITE_URL', 'https://mzansi-insights.onrender.com')
    
    # Content Update
    UPDATE_INTERVAL_MINUTES = 60
    MAX_ARTICLES_PER_SOURCE = 20
    
    # NewsAPI (Free tier - get key from https://newsapi.org)
    NEWSAPI_KEY = os.environ.get('NEWSAPI_KEY', '')
    
    # Debug settings
    DEBUG = os.environ.get('DEBUG', 'False').lower() == 'true'
    PORT = int(os.environ.get('PORT', 5000))

# ============= DATABASE SETUP =============
def get_db_path():
    """Get database path with Render persistence"""
    if os.environ.get('RENDER'):
        data_dir = '/opt/render/project/src/data'
        if not os.path.exists(data_dir):
            os.makedirs(data_dir, exist_ok=True)
        return os.path.join(data_dir, 'posts.db')
    else:
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
        
        # Posts table
        c.execute('''CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            slug TEXT UNIQUE NOT NULL,
            content TEXT NOT NULL,
            excerpt TEXT,
            image_url TEXT,
            source_url TEXT NOT NULL,
            category_id INTEGER,
            category TEXT DEFAULT 'news',
            author TEXT DEFAULT 'Mzansi Insights',
            views INTEGER DEFAULT 0,
            source_name TEXT NOT NULL,
            is_published BOOLEAN DEFAULT 1,
            pub_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (category_id) REFERENCES categories(id)
        )''')
        
        # Create indexes
        c.execute('CREATE INDEX IF NOT EXISTS idx_posts_slug ON posts(slug)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_posts_category ON posts(category_id)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_posts_created_at ON posts(created_at DESC)')
        
        # Create admin user
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
        
        # WORKING SOURCES - These should work on Render
        self.NEWS_SOURCES = [
            # NewsAPI sources (if key is provided)
            {
                'name': 'NewsAPI - South Africa',
                'type': 'newsapi',
                'country': 'za',
                'category': 'news',
                'color': '#4361ee',
                'icon': 'newspaper',
                'enabled': True
            },
            {
                'name': 'NewsAPI - Business',
                'type': 'newsapi',
                'category': 'business',
                'category_filter': 'business',
                'color': '#7209b7',
                'icon': 'chart-line',
                'enabled': True
            },
            {
                'name': 'NewsAPI - Technology',
                'type': 'newsapi',
                'category': 'technology',
                'category_filter': 'technology',
                'color': '#3498db',
                'icon': 'laptop-code',
                'enabled': True
            },
            {
                'name': 'NewsAPI - Sports',
                'type': 'newsapi',
                'category': 'sports',
                'category_filter': 'sports',
                'color': '#2ecc71',
                'icon': 'running',
                'enabled': True
            },
            {
                'name': 'NewsAPI - Entertainment',
                'type': 'newsapi',
                'category': 'entertainment',
                'category_filter': 'entertainment',
                'color': '#ef476f',
                'icon': 'film',
                'enabled': True
            },
            {
                'name': 'NewsAPI - Health',
                'type': 'newsapi',
                'category': 'health',
                'category_filter': 'health',
                'color': '#e74c3c',
                'icon': 'heartbeat',
                'enabled': True
            },
            
            # RSS feeds that MIGHT work (with better headers)
            {
                'name': 'Reuters - Africa',
                'type': 'rss',
                'url': 'http://feeds.reuters.com/reuters/AFRICATopNews',
                'category': 'news',
                'color': '#d62828',
                'icon': 'globe-africa',
                'enabled': True,
                'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            },
            {
                'name': 'BBC News - World',
                'type': 'rss',
                'url': 'http://feeds.bbci.co.uk/news/world/rss.xml',
                'category': 'news',
                'color': '#FFD700',
                'icon': 'globe',
                'enabled': True,
                'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            },
            {
                'name': 'Al Jazeera English',
                'type': 'rss',
                'url': 'https://www.aljazeera.com/xml/rss/all.xml',
                'category': 'news',
                'color': '#0066cc',
                'icon': 'tv',
                'enabled': True,
                'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
        ]
        
        # Sample articles for when no external sources work
        self.SAMPLE_ARTICLES = [
            {
                'title': 'South African Economy Shows Signs of Recovery',
                'content': 'The South African economy is showing positive signs of recovery with GDP growth exceeding expectations. Key sectors including mining, manufacturing, and tourism are driving this growth.',
                'category': 'business',
                'source': 'Mzansi Insights Analysis'
            },
            {
                'title': 'New Job Opportunities in Tech Sector',
                'content': 'The technology sector in South Africa is booming, creating thousands of new job opportunities. Companies are seeking skilled professionals in software development, data science, and cybersecurity.',
                'category': 'jobs',
                'source': 'Mzansi Insights Report'
            },
            {
                'title': 'Government Announces New Grant Programs',
                'content': 'The South African government has announced new grant programs to support small businesses and vulnerable households. Applications open next month.',
                'category': 'grants',
                'source': 'Mzansi Insights Update'
            },
            {
                'title': 'Local Sports Team Wins Championship',
                'content': 'A local sports team has brought home the championship trophy after an exciting season. The victory has brought the community together in celebration.',
                'category': 'sports',
                'source': 'Mzansi Insights Sports'
            },
            {
                'title': 'Tech Innovation Hub Opens in Johannesburg',
                'content': 'A new technology innovation hub has opened in Johannesburg, providing resources and support for tech startups and entrepreneurs.',
                'category': 'technology',
                'source': 'Mzansi Insights Tech'
            },
            {
                'title': 'Entertainment Industry Thrives Post-Pandemic',
                'content': 'The South African entertainment industry is experiencing a strong comeback with new film productions, music festivals, and cultural events.',
                'category': 'entertainment',
                'source': 'Mzansi Insights Entertainment'
            },
            {
                'title': 'Healthcare Initiatives Improve Access',
                'content': 'New healthcare initiatives are improving access to medical services in rural areas across South Africa.',
                'category': 'health',
                'source': 'Mzansi Insights Health'
            },
            {
                'title': 'Education Reforms Announced',
                'content': 'The Department of Education has announced new reforms aimed at improving the quality of education across all levels.',
                'category': 'education',
                'source': 'Mzansi Insights Education'
            }
        ]
    
    def fetch_from_newsapi(self, source):
        """Fetch articles from NewsAPI"""
        if not FlaskConfig.NEWSAPI_KEY:
            logger.warning("NewsAPI key not configured")
            return None
        
        try:
            base_url = "https://newsapi.org/v2/top-headlines"
            params = {
                'apiKey': FlaskConfig.NEWSAPI_KEY,
                'pageSize': FlaskConfig.MAX_ARTICLES_PER_SOURCE
            }
            
            # Add country or category filters
            if 'country' in source:
                params['country'] = source['country']
            if 'category_filter' in source:
                params['category'] = source['category_filter']
            else:
                params['q'] = 'South Africa'  # Default search
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            response = requests.get(base_url, params=params, headers=headers, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            if data.get('status') == 'ok' and data.get('articles'):
                logger.info(f"✅ NewsAPI: Found {len(data['articles'])} articles")
                return data['articles']
            else:
                logger.warning(f"NewsAPI: No articles found")
                return None
                
        except Exception as e:
            logger.error(f"NewsAPI error: {e}")
            return None
    
    def fetch_rss_feed(self, source):
        """Fetch RSS feed with improved error handling"""
        try:
            headers = {
                'User-Agent': source.get('user_agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'),
                'Accept': 'application/xml, text/xml, */*; q=0.01',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'keep-alive',
                'Cache-Control': 'max-age=0'
            }
            
            # Try with requests
            response = requests.get(
                source['url'],
                headers=headers,
                timeout=15,
                verify=True,
                allow_redirects=True
            )
            response.raise_for_status()
            
            # Parse feed
            feed = feedparser.parse(response.content)
            
            if feed.bozo:
                logger.warning(f"RSS parse warning: {feed.bozo_exception}")
                # Try with text
                try:
                    feed = feedparser.parse(response.text)
                except:
                    pass
            
            if feed.entries:
                logger.info(f"✅ RSS: Found {len(feed.entries)} entries from {source['name']}")
                return feed
            else:
                logger.warning(f"RSS: No entries from {source['name']}")
                return None
                
        except Exception as e:
            logger.error(f"RSS fetch error for {source['name']}: {e}")
            return None
    
    def create_sample_articles(self):
        """Create sample articles when no external sources work"""
        logger.info("📝 Creating sample articles...")
        
        articles = []
        for i, sample in enumerate(self.SAMPLE_ARTICLES):
            article = {
                'title': sample['title'],
                'content': sample['content'] + " This is sample content to demonstrate the Mzansi Insights platform. In a production environment, this would be replaced with real news articles from trusted South African sources.",
                'link': f"https://mzansi-insights.onrender.com/article/sample-{i+1}",
                'source': sample['source'],
                'pub_date': (datetime.now() - timedelta(hours=random.randint(1, 24))).strftime('%Y-%m-%d %H:%M:%S')
            }
            articles.append(article)
        
        return articles
    
    def extract_image(self, article, source_type):
        """Extract image URL from article"""
        try:
            if source_type == 'newsapi':
                return article.get('urlToImage', '')
            elif source_type == 'rss':
                if 'media_content' in article and article.media_content:
                    for media in article.media_content:
                        if media.get('type', '').startswith('image/'):
                            return media.get('url', '')
                elif 'media_thumbnail' in article and article.media_thumbnail:
                    return article.media_thumbnail[0].get('url', '')
                elif 'content' in article:
                    # Try to extract from content
                    content = article.content[0].value if isinstance(article.content, list) else str(article.content)
                    img_match = re.search(r'<img[^>]+src="([^">]+)"', content, re.IGNORECASE)
                    if img_match:
                        return img_match.group(1)
        except:
            pass
        
        # Fallback images based on category
        fallback_images = {
            'news': 'https://images.unsplash.com/photo-1588681664899-f142ff2dc9b1?w=800&auto=format&fit=crop',
            'business': 'https://images.unsplash.com/photo-1497366754035-f200968a6e72?w=800&auto=format&fit=crop',
            'technology': 'https://images.unsplash.com/photo-1519389950473-47ba0277781c?w=800&auto=format&fit=crop',
            'sports': 'https://images.unsplash.com/photo-1546519638-68e109498ffc?w=800&auto=format&fit=crop',
            'entertainment': 'https://images.unsplash.com/photo-1493225457124-a3eb161ffa5f?w=800&auto=format&fit=crop',
            'jobs': 'https://images.unsplash.com/photo-1521791136064-7986c2920216?w=800&auto=format&fit=crop',
            'grants': 'https://images.unsplash.com/photo-1554224155-6726b3ff858f?w=800&auto=format&fit=crop',
            'health': 'https://images.unsplash.com/photo-1576091160399-112ba8d25d1f?w=800&auto=format&fit=crop',
            'education': 'https://images.unsplash.com/photo-1523050854058-8df90110c9f1?w=800&auto=format&fit=crop',
            'government': 'https://images.unsplash.com/photo-1551135049-8a33b2fb2f5a?w=800&auto=format&fit=crop'
        }
        
        category = self.get_article_category(article, source_type)
        return fallback_images.get(category, fallback_images['news'])
    
    def get_article_category(self, article, source_type):
        """Get article category"""
        if source_type == 'newsapi':
            return article.get('category', 'news')
        elif source_type == 'rss':
            # Try to extract category from RSS
            if hasattr(article, 'category'):
                if isinstance(article.category, str):
                    return article.category.lower()
                elif isinstance(article.category, list) and len(article.category) > 0:
                    return str(article.category[0]).lower()
        return 'news'
    
    def clean_content(self, content, max_length=1500):
        """Clean HTML content to plain text"""
        if not content:
            return ""
        
        try:
            soup = BeautifulSoup(content, 'html.parser')
            for script in soup(["script", "style", "iframe"]):
                script.decompose()
            
            text = soup.get_text()
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = ' '.join(chunk for chunk in chunks if chunk)
            
            text = html.unescape(text)
            
            if len(text) > max_length:
                text = text[:max_length] + '...'
            
            return text
            
        except:
            # Simple cleanup
            text = re.sub(r'<[^>]+>', '', content)
            text = html.unescape(text)
            text = ' '.join(text.split())
            return text[:max_length]
    
    def generate_slug(self, title, source_name):
        """Generate unique slug from title"""
        clean_title = re.sub(r'[^a-z0-9\s-]', '', title.lower())
        clean_title = re.sub(r'\s+', '-', clean_title.strip())
        
        source_hash = hashlib.md5(source_name.encode()).hexdigest()[:6]
        title_hash = hashlib.md5(title.encode()).hexdigest()[:6]
        
        slug = f"{clean_title[:60]}-{source_hash}-{title_hash}"
        return slug
    
    def create_excerpt(self, content, max_length=200):
        """Create excerpt from content"""
        if not content:
            return ""
        
        cleaned = self.clean_content(content, max_length * 2)
        
        if len(cleaned) > max_length:
            truncated = cleaned[:max_length]
            last_period = truncated.rfind('. ')
            if last_period > max_length * 0.5:
                return truncated[:last_period + 1] + '..'
            return truncated + '...'
        
        return cleaned
    
    def fetch_and_save(self):
        """Fetch and save articles from sources"""
        if self.is_fetching:
            logger.info("Already fetching, skipping...")
            return 0
        
        self.is_fetching = True
        total_saved = 0
        start_time = time.time()
        
        try:
            logger.info("=" * 60)
            logger.info("STARTING CONTENT FETCH...")
            logger.info("=" * 60)
            
            conn = get_db_connection()
            
            # First try NewsAPI if key is available
            newsapi_sources = [s for s in self.NEWS_SOURCES if s.get('type') == 'newsapi' and s.get('enabled', True)]
            rss_sources = [s for s in self.NEWS_SOURCES if s.get('type') == 'rss' and s.get('enabled', True)]
            
            articles = []
            
            # Try NewsAPI sources
            if FlaskConfig.NEWSAPI_KEY and newsapi_sources:
                logger.info("📡 Trying NewsAPI sources...")
                for source in newsapi_sources[:2]:  # Limit to 2 NewsAPI calls to stay within limits
                    try:
                        newsapi_articles = self.fetch_from_newsapi(source)
                        if newsapi_articles:
                            for article in newsapi_articles:
                                article['_source'] = source
                                article['_type'] = 'newsapi'
                            articles.extend(newsapi_articles)
                    except Exception as e:
                        logger.error(f"NewsAPI source {source['name']} failed: {e}")
            
            # Try RSS sources
            logger.info("📡 Trying RSS sources...")
            for source in rss_sources[:3]:  # Limit to 3 RSS feeds
                try:
                    feed = self.fetch_rss_feed(source)
                    if feed and feed.entries:
                        for entry in feed.entries[:10]:  # Limit entries
                            entry._source = source
                            entry._type = 'rss'
                            articles.append(entry)
                except Exception as e:
                    logger.error(f"RSS source {source['name']} failed: {e}")
            
            # If no articles from external sources, create samples
            if not articles:
                logger.info("📝 No external articles found, creating sample articles...")
                sample_data = self.create_sample_articles()
                for sample in sample_data:
                    sample['_source'] = {
                        'name': sample['source'],
                        'category': sample.get('category', 'news')
                    }
                    sample['_type'] = 'sample'
                articles = sample_data
            
            # Process and save articles
            logger.info(f"📊 Processing {len(articles)} articles...")
            
            for article in articles[:FlaskConfig.MAX_ARTICLES_PER_SOURCE * 2]:  # Limit total
                try:
                    if article['_type'] == 'newsapi':
                        title = article.get('title', '').strip()
                        source_name = article['_source']['name']
                        content = article.get('content', article.get('description', ''))
                        source_url = article.get('url', '')
                        author = article.get('author', 'Unknown')
                        pub_date_str = article.get('publishedAt', '')
                    elif article['_type'] == 'rss':
                        title = getattr(article, 'title', '').strip()
                        source_name = article._source['name']
                        content = self.get_entry_content(article)
                        source_url = getattr(article, 'link', '')
                        author = getattr(article, 'author', 'Unknown')
                        pub_date = getattr(article, 'published_parsed', None)
                        if pub_date:
                            pub_date_str = datetime(*pub_date[:6]).strftime('%Y-%m-%d %H:%M:%S')
                        else:
                            pub_date_str = ''
                    else:  # sample
                        title = article['title']
                        source_name = article['_source']['name']
                        content = article['content']
                        source_url = article['link']
                        author = 'Mzansi Insights'
                        pub_date_str = article['pub_date']
                    
                    if not title or len(title) < 10:
                        continue
                    
                    # Generate slug
                    slug = self.generate_slug(title, source_name)
                    
                    # Check if article already exists
                    existing = conn.execute(
                        "SELECT id FROM posts WHERE slug = ?", 
                        (slug,)
                    ).fetchone()
                    
                    if existing:
                        continue
                    
                    # Clean content
                    cleaned_content = self.clean_content(content, 2000)
                    if not cleaned_content or len(cleaned_content) < 100:
                        cleaned_content = title + ". Read more on the source website."
                    
                    # Create excerpt
                    excerpt = self.create_excerpt(cleaned_content, 250)
                    
                    # Get image
                    image_url = self.extract_image(article, article['_type'])
                    
                    # Get category
                    category = article['_source'].get('category', 'news')
                    
                    # Get category ID
                    cat_row = conn.execute(
                        "SELECT id FROM categories WHERE slug = ?", 
                        (category,)
                    ).fetchone()
                    category_id = cat_row[0] if cat_row else 1
                    
                    # Parse publication date
                    try:
                        if pub_date_str:
                            if 'T' in pub_date_str:
                                pub_date = datetime.strptime(pub_date_str.split('T')[0], '%Y-%m-%d')
                            else:
                                pub_date = datetime.strptime(pub_date_str.split()[0], '%Y-%m-%d')
                        else:
                            pub_date = datetime.now() - timedelta(hours=random.randint(1, 24))
                    except:
                        pub_date = datetime.now() - timedelta(hours=random.randint(1, 24))
                    
                    # Insert article
                    conn.execute('''INSERT INTO posts 
                        (title, slug, content, excerpt, image_url, source_url, 
                         category_id, category, author, source_name, views, is_published, 
                         pub_date)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)''',
                        (title, slug, cleaned_content, excerpt, image_url, source_url,
                         category_id, category, author, source_name, 
                         random.randint(10, 100), pub_date))
                    
                    total_saved += 1
                    
                    if total_saved <= 5:
                        logger.info(f"    ✅ Saved: {title[:70]}...")
                    
                except Exception as e:
                    logger.debug(f"Article error: {str(e)[:100]}")
                    continue
            
            conn.commit()
            conn.close()
            
            self.last_fetch_time = datetime.now()
            self.last_fetch_count = total_saved
            
            elapsed = time.time() - start_time
            
            logger.info("=" * 60)
            if total_saved > 0:
                logger.info(f"🎉 FETCH COMPLETE!")
                logger.info(f"✅ Total new articles: {total_saved}")
                logger.info(f"⏱️  Time taken: {elapsed:.2f} seconds")
            else:
                logger.info("✅ Fetch complete: No new articles found")
            logger.info("=" * 60)
            
            return total_saved
            
        except Exception as e:
            logger.error(f"❌ FETCH ERROR: {e}", exc_info=True)
            return 0
        finally:
            self.is_fetching = False
    
    def get_entry_content(self, entry):
        """Get content from RSS entry"""
        content_fields = [
            ('content', lambda x: x[0].value if isinstance(x, list) and len(x) > 0 else str(x)),
            ('summary_detail', lambda x: x.value if hasattr(x, 'value') else str(x)),
            ('summary', str),
            ('description', str),
            ('title', str)
        ]
        
        for field, converter in content_fields:
            if hasattr(entry, field):
                try:
                    value = getattr(entry, field)
                    if value:
                        content = converter(value)
                        if content and len(str(content).strip()) > 50:
                            return str(content)
                except:
                    continue
        
        return getattr(entry, 'title', 'No content available')

# ============= FLASK APP =============
app = Flask(__name__)
app.config.from_object(FlaskConfig)

print("=" * 60)
print("🇿🇦 MZANSI INSIGHTS - NEWS AGGREGATOR")
print("=" * 60)

# Setup database
db_setup_success = setup_database()

# Initialize fetcher
fetcher = ContentFetcher()

# Test fetch on startup
print("🚀 Testing fetch on startup...")
initial_fetched = fetcher.fetch_and_save()
print(f"✅ Initial fetch: {initial_fetched} articles")
print(f"⏰ Next fetch in: {FlaskConfig.UPDATE_INTERVAL_MINUTES} minutes")

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

# Helper functions (same as before, but include them)
def get_time_ago(date_str):
    """Convert date to relative time"""
    try:
        if not date_str:
            return "Recently"
        
        if isinstance(date_str, str):
            try:
                post_date = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
            except:
                post_date = datetime.strptime(date_str, '%Y-%m-%d')
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
    post['formatted_date'] = get_time_ago(post.get('pub_date') or post.get('created_at', ''))
    
    if not post.get('source_url') or post['source_url'] == '#':
        source_name = post.get('source_name', '').lower().replace(' ', '-')
        slug = post.get('slug', '')
        post['source_url'] = f"https://mzansi-insights.onrender.com/post/{slug}"
    
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

# Routes (same as before - index, category, post, search, sources, etc.)
# ... [Include all the route functions from your previous app.py]

# Background auto-fetcher
def start_auto_fetcher():
    def fetch_loop():
        while True:
            try:
                wait_time = FlaskConfig.UPDATE_INTERVAL_MINUTES * 60
                logger.info(f"⏰ Next fetch in {FlaskConfig.UPDATE_INTERVAL_MINUTES} minutes...")
                time.sleep(wait_time)
                
                logger.info("🔄 RUNNING SCHEDULED FETCH...")
                fetched = fetcher.fetch_and_save()
                
                if fetched > 0:
                    logger.info(f"✅ Scheduled fetch: {fetched} new articles")
                else:
                    logger.info("✅ Scheduled fetch complete - no new articles")
                    
            except Exception as e:
                logger.error(f"❌ Background fetch error: {e}")
                time.sleep(300)
    
    thread = threading.Thread(target=fetch_loop, daemon=True)
    thread.start()
    logger.info(f"🚀 Auto-fetcher started - Updates every {FlaskConfig.UPDATE_INTERVAL_MINUTES} minutes")

# Start auto-fetcher
start_auto_fetcher()

if __name__ == '__main__':
    print(f"🌐 Site URL: {FlaskConfig.SITE_URL}")
    print(f"🔐 Admin: {FlaskConfig.SITE_URL}/admin/login")
    print(f"📧 Contact: {FlaskConfig.CONTACT_EMAIL}")
    print(f"📱 Phone: {FlaskConfig.CONTACT_PHONE}")
    print(f"💰 AdSense: {'ENABLED' if FlaskConfig.ADSENSE_ENABLED else 'DISABLED'}")
    print(f"📊 Active Sources: {len([s for s in fetcher.NEWS_SOURCES if s.get('enabled', True)])}")
    print(f"⏰ Auto-update: Every {FlaskConfig.UPDATE_INTERVAL_MINUTES} minutes")
    print("=" * 60)
    print("🚀 Ready to fetch news from South African sources!")
    print("=" * 60)
    
    port = int(os.environ.get('PORT', 5000))
    app.run(
        debug=FlaskConfig.DEBUG,
        host='0.0.0.0',
        port=port,
        threaded=True
    )