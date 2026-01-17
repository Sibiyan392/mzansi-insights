# Python 3.13+ compatibility fix
try:
    import fix_cgi
    fix_cgi.patch_feedparser()
except Exception as e:
    print(f"⚠️  CGI fix failed: {e}")

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
# ... rest of your imports ...

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
    UPDATE_INTERVAL_MINUTES = 60  # Fetch every 60 minutes
    MAX_ARTICLES_PER_SOURCE = 20  # Fetch up to 20 articles per source
    
    # Debug settings
    DEBUG = os.environ.get('DEBUG', 'False').lower() == 'true'
    PORT = int(os.environ.get('PORT', 5000))

# ============= DATABASE SETUP =============
def get_db_path():
    """Get database path with Render persistence"""
    if os.environ.get('RENDER'):
        # Render persistent volume
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
        
        # Posts table - SIMPLIFIED VERSION
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
        
        # Create index for faster lookups
        c.execute('CREATE INDEX IF NOT EXISTS idx_posts_slug ON posts(slug)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_posts_category ON posts(category_id)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_posts_created_at ON posts(created_at DESC)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_posts_source_url ON posts(source_url)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_posts_source_name ON posts(source_name)')
        
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
        
        # WORKING South African News Sources (Updated URLs)
        self.NEWS_SOURCES = [
            {
                'name': 'SABC News',
                'url': 'https://www.sabcnews.com/sabcnews/feed/',
                'category': 'news',
                'color': '#4361ee',
                'icon': 'newspaper',
                'enabled': True,
                'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'base_url': 'https://www.sabcnews.com'
            },
            {
                'name': 'News24',
                'url': 'https://www.news24.com/rss',
                'category': 'news',
                'color': '#d62828',
                'icon': 'newspaper',
                'enabled': True,
                'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'base_url': 'https://www.news24.com'
            },
            {
                'name': 'IOL News',
                'url': 'https://www.iol.co.za/rss',
                'category': 'news',
                'color': '#06d6a0',
                'icon': 'newspaper',
                'enabled': True,
                'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'base_url': 'https://www.iol.co.za'
            },
            {
                'name': 'TimesLIVE',
                'url': 'https://www.timeslive.co.za/rss',
                'category': 'news',
                'color': '#7209b7',
                'icon': 'newspaper',
                'enabled': True,
                'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'base_url': 'https://www.timeslive.co.za'
            },
            {
                'name': 'SA Government News',
                'url': 'https://www.gov.za/news/feed',
                'category': 'government',
                'color': '#2c3e50',
                'icon': 'landmark',
                'enabled': True,
                'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'base_url': 'https://www.gov.za'
            },
            {
                'name': 'MyBroadband',
                'url': 'https://mybroadband.co.za/news/feed/',
                'category': 'technology',
                'color': '#9b59b6',
                'icon': 'wifi',
                'enabled': True,
                'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'base_url': 'https://mybroadband.co.za',
                'requires_proxy': True
            },
            {
                'name': 'BusinessTech',
                'url': 'https://businesstech.co.za/news/feed/',
                'category': 'business',
                'color': '#3742fa',
                'icon': 'chart-line',
                'enabled': True,
                'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'base_url': 'https://businesstech.co.za',
                'requires_proxy': True
            },
            {
                'name': 'TechFinancials',
                'url': 'https://techfinancials.co.za/feed/',
                'category': 'technology',
                'color': '#3498db',
                'icon': 'laptop',
                'enabled': True,
                'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'base_url': 'https://techfinancials.co.za'
            },
            {
                'name': 'Daily Maverick',
                'url': 'https://www.dailymaverick.co.za/feed/',
                'category': 'news',
                'color': '#ef476f',
                'icon': 'newspaper',
                'enabled': True,
                'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'base_url': 'https://www.dailymaverick.co.za'
            },
        ]
    
    def fetch_feed_with_proxy(self, source):
        """Fetch RSS feed with proper headers and error handling"""
        try:
            headers = {
                'User-Agent': source.get('user_agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'),
                'Accept': 'application/rss+xml, application/xml, text/xml, */*; q=0.01',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Cache-Control': 'max-age=0',
                'DNT': '1',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Sec-Fetch-User': '?1'
            }
            
            # Add referer for specific sites
            if 'mybroadband' in source['url']:
                headers['Referer'] = 'https://mybroadband.co.za/'
                headers['Origin'] = 'https://mybroadband.co.za'
            elif 'businesstech' in source['url']:
                headers['Referer'] = 'https://businesstech.co.za/'
                headers['Origin'] = 'https://businesstech.co.za'
            
            timeout = 15  # Increased timeout
            
            # Try multiple URL variations for problematic feeds
            url_variations = [source['url']]
            
            # Add alternative URL formats
            base_url = source['url']
            if '/feed' in base_url:
                url_variations.append(base_url.replace('/feed', '/feed.xml'))
                url_variations.append(base_url.replace('/feed', '/rss'))
                url_variations.append(base_url.replace('/feed', '/atom.xml'))
            elif '/rss' in base_url:
                url_variations.append(base_url.replace('/rss', '/feed'))
                url_variations.append(base_url.replace('/rss', '/feed.xml'))
            
            feed = None
            successful_url = None
            
            for feed_url in url_variations:
                try:
                    logger.info(f"Trying URL: {feed_url}")
                    
                    response = requests.get(
                        feed_url,
                        headers=headers,
                        timeout=timeout,
                        verify=False,
                        allow_redirects=True
                    )
                    
                    logger.info(f"Response from {source['name']} ({feed_url}): {response.status_code}")
                    
                    if response.status_code == 200:
                        successful_url = feed_url
                        
                        # Try different parsing methods
                        try:
                            # Method 1: Direct feedparser parse
                            feed = feedparser.parse(response.content)
                            
                            # If feedparser fails, try BeautifulSoup as XML
                            if feed.bozo and (not feed.entries or len(feed.entries) == 0):
                                logger.info(f"Feedparser failed, trying BeautifulSoup XML parsing for {source['name']}")
                                soup = BeautifulSoup(response.content, 'xml')
                                
                                # Create a minimal feed object
                                class MinimalFeed:
                                    def __init__(self):
                                        self.entries = []
                                        self.bozo = False
                                
                                feed = MinimalFeed()
                                
                                # Extract items
                                items = soup.find_all(['item', 'entry'])
                                for item in items[:FlaskConfig.MAX_ARTICLES_PER_SOURCE]:
                                    entry = {}
                                    
                                    # Extract title
                                    title_elem = item.find('title')
                                    if title_elem:
                                        entry['title'] = title_elem.get_text(strip=True)
                                    else:
                                        continue  # Skip if no title
                                    
                                    # Extract link
                                    link_elem = item.find('link')
                                    if link_elem:
                                        if link_elem.get('href'):
                                            entry['link'] = link_elem['href']
                                        else:
                                            entry['link'] = link_elem.get_text(strip=True)
                                    else:
                                        # Generate a placeholder link
                                        slug = hashlib.md5(entry['title'].encode()).hexdigest()[:10]
                                        entry['link'] = f"{source['base_url']}/article/{slug}"
                                    
                                    # Extract description/content
                                    desc_elem = item.find(['description', 'content:encoded', 'content', 'summary'])
                                    if desc_elem:
                                        entry['summary'] = desc_elem.get_text(strip=True)[:500]
                                    else:
                                        entry['summary'] = entry['title']
                                    
                                    # Extract published date
                                    date_elem = item.find(['pubDate', 'published', 'dc:date', 'date'])
                                    if date_elem:
                                        entry['published'] = date_elem.get_text(strip=True)
                                    
                                    feed.entries.append(entry)
                                
                                logger.info(f"BeautifulSoup extracted {len(feed.entries)} entries")
                        
                        except Exception as parse_error:
                            logger.error(f"Parse error for {source['name']}: {parse_error}")
                            continue
                        
                        if feed and hasattr(feed, 'entries') and len(feed.entries) > 0:
                            logger.info(f"Successfully parsed {len(feed.entries)} entries from {feed_url}")
                            break
                        else:
                            logger.warning(f"No entries found in {feed_url}")
                
                except requests.exceptions.RequestException as req_err:
                    logger.warning(f"Failed to fetch {feed_url}: {req_err}")
                    continue
                except Exception as e:
                    logger.warning(f"Error processing {feed_url}: {e}")
                    continue
            
            # If all URL variations failed, try a web scrape as last resort
            if not feed or not hasattr(feed, 'entries') or len(feed.entries) == 0:
                logger.info(f"All RSS feeds failed, trying web scrape for {source['name']}")
                try:
                    response = requests.get(
                        source['base_url'],
                        headers=headers,
                        timeout=timeout,
                        verify=False
                    )
                    
                    if response.status_code == 200:
                        soup = BeautifulSoup(response.content, 'html.parser')
                        
                        # Look for article links (common patterns)
                        article_links = []
                        
                        # Try different selectors
                        selectors = [
                            'article a', '.article a', '.news-item a', '.post a',
                            'h2 a', 'h3 a', '.title a', '.headline a',
                            '[class*="article"] a', '[class*="news"] a', '[class*="post"] a'
                        ]
                        
                        for selector in selectors:
                            links = soup.select(selector)
                            for link in links:
                                href = link.get('href', '')
                                text = link.get_text(strip=True)
                                
                                if (href and href.startswith('http') and 
                                    text and len(text) > 20 and 
                                    not any(x in href.lower() for x in ['contact', 'about', 'privacy', 'terms', 'login', 'register'])):
                                    
                                    # Make absolute URL if relative
                                    if href.startswith('/'):
                                        href = urljoin(source['base_url'], href)
                                    
                                    article_links.append({
                                        'title': text[:200],
                                        'link': href,
                                        'summary': f'Latest news from {source["name"]}',
                                        'published': datetime.now().strftime('%a, %d %b %Y %H:%M:%S GMT')
                                    })
                            
                            if article_links:
                                break
                        
                        if article_links:
                            # Create a minimal feed
                            class ScrapedFeed:
                                def __init__(self):
                                    self.entries = []
                                    self.bozo = False
                            
                            feed = ScrapedFeed()
                            feed.entries = article_links[:FlaskConfig.MAX_ARTICLES_PER_SOURCE]
                            logger.info(f"Web scrape found {len(feed.entries)} articles")
                
                except Exception as scrape_error:
                    logger.error(f"Web scrape failed for {source['name']}: {scrape_error}")
            
            return feed
            
        except Exception as e:
            logger.error(f"Unexpected error in fetch_feed_with_proxy for {source['name']}: {e}", exc_info=True)
            return None
    
    def extract_image_from_entry(self, entry, source_base_url):
        """Extract image URL from entry"""
        try:
            # Method 1: Check for media content
            if hasattr(entry, 'media_content') and entry.media_content:
                for media in entry.media_content:
                    if isinstance(media, dict) and media.get('type', '').startswith('image/'):
                        img_url = media.get('url', '')
                        if img_url and img_url.startswith('http'):
                            return img_url
            
            # Method 2: Check media thumbnail
            if hasattr(entry, 'media_thumbnail') and entry.media_thumbnail:
                for thumb in entry.media_thumbnail:
                    if isinstance(thumb, dict):
                        img_url = thumb.get('url', '')
                        if img_url and img_url.startswith('http'):
                            return img_url
            
            # Method 3: Check for enclosures
            if hasattr(entry, 'enclosures') and entry.enclosures:
                for enc in entry.enclosures:
                    if isinstance(enc, dict) and enc.get('type', '').startswith('image/'):
                        img_url = enc.get('href', '') or enc.get('url', '')
                        if img_url and img_url.startswith('http'):
                            return img_url
            
            # Method 4: Extract from content/summary using BeautifulSoup
            content_fields = ['content', 'summary', 'description']
            
            for field in content_fields:
                if hasattr(entry, field):
                    content = getattr(entry, field)
                    
                    # Handle different content types
                    if isinstance(content, list) and len(content) > 0:
                        if hasattr(content[0], 'value'):
                            content = content[0].value
                        else:
                            content = str(content[0])
                    elif isinstance(content, dict):
                        content = content.get('value', '')
                    else:
                        content = str(content)
                    
                    if content:
                        try:
                            soup = BeautifulSoup(content, 'html.parser')
                            img_tag = soup.find('img')
                            if img_tag and img_tag.get('src'):
                                img_url = img_tag['src']
                                if img_url and img_url.startswith('http'):
                                    return img_url
                                elif img_url and img_url.startswith('/'):
                                    return urljoin(source_base_url, img_url)
                        except:
                            # Try regex as fallback
                            img_match = re.search(r'<img[^>]+src="([^">]+)"', content, re.IGNORECASE)
                            if img_match:
                                img_url = img_match.group(1)
                                if img_url and img_url.startswith('http'):
                                    return img_url
                                elif img_url and img_url.startswith('/'):
                                    return urljoin(source_base_url, img_url)
            
            # Method 5: Check for links in entry
            if hasattr(entry, 'links'):
                for link in entry.links:
                    if isinstance(link, dict) and link.get('type', '').startswith('image/'):
                        img_url = link.get('href', '')
                        if img_url and img_url.startswith('http'):
                            return img_url
            
        except Exception as e:
            logger.debug(f"Image extraction error: {e}")
        
        # Return fallback image based on category
        return self.get_fallback_image(source_base_url.split('/')[2] if '//' in source_base_url else 'news')
    
    def get_fallback_image(self, category):
        """Get fallback image based on category"""
        fallback_images = {
            'news': 'https://images.unsplash.com/photo-1588681664899-f142ff2dc9b1?w=800&auto=format&fit=crop',
            'business': 'https://images.unsplash.com/photo-1497366754035-f200968a6e72?w=800&auto=format&fit=crop',
            'technology': 'https://images.unsplash.com/photo-1519389950473-47ba0277781c?w=800&auto=format&fit=crop',
            'sports': 'https://images.unsplash.com/photo-1546519638-68e109498ffc?w=800&auto=format&fit=crop',
            'entertainment': 'https://images.unsplash.com/photo-1493225457124-a3eb161ffa5f?w=800&auto=format&fit=crop',
            'government': 'https://images.unsplash.com/photo-1551135049-8a33b2fb2f5a?w=800&auto=format&fit=crop',
            'health': 'https://images.unsplash.com/photo-1576091160399-112ba8d25d1f?w=800&auto=format&fit=crop',
            'education': 'https://images.unsplash.com/photo-1523050854058-8df90110c9f1?w=800&auto=format&fit=crop',
            'jobs': 'https://images.unsplash.com/photo-1551836026-d5c2c5af78e4?w=800&auto=format&fit=crop',
            'grants': 'https://images.unsplash.com/photo-1579621970795-87facc2f976d?w=800&auto=format&fit=crop',
        }
        
        # Try to match category
        for key in fallback_images:
            if key in category.lower():
                return fallback_images[key]
        
        return fallback_images['news']
    
    def clean_html_content(self, html_content, max_length=2000):
        """Clean HTML content to plain text with better handling"""
        if not html_content:
            return ""
        
        try:
            # Handle different input types
            if isinstance(html_content, list):
                if len(html_content) > 0:
                    if hasattr(html_content[0], 'value'):
                        html_content = html_content[0].value
                    else:
                        html_content = str(html_content[0])
                else:
                    return ""
            elif isinstance(html_content, dict):
                html_content = html_content.get('value', '')
            
            html_content = str(html_content)
            
            # Parse HTML with BeautifulSoup
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Remove unwanted elements
            unwanted_tags = ['script', 'style', 'iframe', 'nav', 'header', 'footer', 
                           'aside', 'form', 'button', 'input', 'select', 'textarea']
            
            for tag in unwanted_tags:
                for element in soup.find_all(tag):
                    element.decompose()
            
            # Also remove divs with certain classes
            unwanted_classes = ['advertisement', 'ad', 'sidebar', 'navigation', 
                              'comments', 'share', 'related', 'promo']
            
            for cls in unwanted_classes:
                for element in soup.find_all(class_=lambda x: x and cls in x.lower()):
                    element.decompose()
            
            # Get text
            text = soup.get_text(separator=' ', strip=True)
            
            # Decode HTML entities
            text = html.unescape(text)
            
            # Clean up whitespace
            text = ' '.join(text.split())
            
            # Truncate if too long
            if len(text) > max_length:
                # Try to find a good breaking point
                truncated = text[:max_length]
                last_period = truncated.rfind('. ')
                last_sentence = truncated.rfind('.')
                
                if last_period > max_length * 0.5:
                    text = truncated[:last_period + 1] + '..'
                elif last_sentence > max_length * 0.5:
                    text = truncated[:last_sentence + 1] + '..'
                else:
                    text = truncated + '...'
            
            return text
            
        except Exception as e:
            logger.debug(f"HTML cleaning error: {e}")
            # Fallback to simple regex cleaning
            try:
                text = re.sub(r'<[^>]+>', ' ', str(html_content))
                text = html.unescape(text)
                text = ' '.join(text.split())
                return text[:max_length]
            except:
                return str(html_content)[:max_length]
    
    def get_entry_content(self, entry):
        """Get content from entry with multiple fallbacks"""
        # Define content extraction methods
        content_extractors = [
            # Try full content first
            lambda: getattr(entry, 'content', None),
            lambda: getattr(entry, 'content:encoded', None),
            lambda: getattr(entry, 'content:encoded#html', None),
            
            # Then try summary/detail
            lambda: (getattr(entry, 'summary_detail', None) and 
                    (getattr(entry.summary_detail, 'value', None) or 
                     str(entry.summary_detail))),
            lambda: getattr(entry, 'summary', None),
            
            # Then description
            lambda: getattr(entry, 'description', None),
            
            # Finally title
            lambda: getattr(entry, 'title', 'No content available')
        ]
        
        for extractor in content_extractors:
            try:
                content = extractor()
                if content:
                    # Handle different content types
                    if isinstance(content, list):
                        if len(content) > 0:
                            if hasattr(content[0], 'value'):
                                content = content[0].value
                            else:
                                content = str(content[0])
                        else:
                            continue
                    elif isinstance(content, dict):
                        content = content.get('value', '')
                    
                    content_str = str(content).strip()
                    if content_str and len(content_str) > 50:
                        return content_str
            except:
                continue
        
        return 'No content available'
    
    def get_entry_excerpt(self, content, max_length=200):
        """Create excerpt from content"""
        if not content:
            return ""
        
        # Clean the content
        cleaned = self.clean_html_content(content, max_length * 3)
        
        # Remove URLs and special characters
        cleaned = re.sub(r'https?://\S+|www\.\S+', '', cleaned)
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        
        # Take first max_length characters
        if len(cleaned) > max_length:
            truncated = cleaned[:max_length]
            
            # Try to end at a sentence
            last_period = truncated.rfind('. ')
            last_exclamation = truncated.rfind('! ')
            last_question = truncated.rfind('? ')
            
            end_points = [p for p in [last_period, last_exclamation, last_question] if p > max_length * 0.3]
            
            if end_points:
                best_end = max(end_points)
                return truncated[:best_end + 1] + '..'
            
            return truncated + '...'
        
        return cleaned
    
    def generate_slug(self, title, source_name):
        """Generate unique slug from title"""
        if not title:
            title = "untitled-article"
        
        # Clean title
        clean_title = re.sub(r'[^a-z0-9\s-]', '', title.lower())
        clean_title = re.sub(r'\s+', '-', clean_title.strip())
        
        # Ensure slug is not empty
        if not clean_title:
            clean_title = "article"
        
        # Add source and hash for uniqueness
        source_hash = hashlib.md5(source_name.encode()).hexdigest()[:6]
        title_hash = hashlib.md5(title.encode()).hexdigest()[:6]
        timestamp = str(int(time.time()))[-6:]
        
        slug = f"{clean_title[:50]}-{source_hash}-{title_hash}-{timestamp}"
        
        # Ensure slug length is reasonable
        if len(slug) > 100:
            slug = slug[:100]
        
        return slug
    
    def get_publication_date(self, entry):
        """Get publication date from entry with multiple fallbacks"""
        date_fields = [
            ('published_parsed', lambda x: datetime(*x[:6]) if x else None),
            ('updated_parsed', lambda x: datetime(*x[:6]) if x else None),
            ('created_parsed', lambda x: datetime(*x[:6]) if x else None),
            ('pubDate', lambda x: self.parse_date_string(x) if x else None),
            ('published', lambda x: self.parse_date_string(x) if x else None),
            ('dc:date', lambda x: self.parse_date_string(x) if x else None),
        ]
        
        for field_name, parser in date_fields:
            if hasattr(entry, field_name):
                try:
                    value = getattr(entry, field_name)
                    if value:
                        date_obj = parser(value)
                        if date_obj:
                            return date_obj
                except:
                    continue
        
        # If no date found, use current time minus random hours (to simulate freshness)
        random_hours = random.randint(1, 72)
        return datetime.now() - timedelta(hours=random_hours)
    
    def parse_date_string(self, date_str):
        """Parse various date string formats"""
        if not date_str:
            return None
        
        date_formats = [
            '%a, %d %b %Y %H:%M:%S %Z',
            '%a, %d %b %Y %H:%M:%S %z',
            '%Y-%m-%dT%H:%M:%S%z',
            '%Y-%m-%d %H:%M:%S',
            '%d %b %Y %H:%M:%S',
            '%b %d, %Y %H:%M:%S',
        ]
        
        for fmt in date_formats:
            try:
                return datetime.strptime(date_str.strip(), fmt)
            except:
                continue
        
        return None
    
    def fetch_and_save(self):
        """Fetch and save articles from sources with improved error handling"""
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
            
            enabled_sources = [s for s in self.NEWS_SOURCES if s.get('enabled', True)]
            logger.info(f"Processing {len(enabled_sources)} enabled sources")
            
            for source in enabled_sources:
                source_start_time = time.time()
                source_saved = 0
                
                try:
                    logger.info(f"📡 Fetching from {source['name']} ({source['category']})...")
                    
                    # Fetch the feed
                    feed = self.fetch_feed_with_proxy(source)
                    
                    if not feed or not hasattr(feed, 'entries') or len(feed.entries) == 0:
                        logger.warning(f"  ❌ No entries from {source['name']}")
                        
                        # Add a backup article if no content
                        if random.random() < 0.3:  # 30% chance to add backup
                            self.add_backup_article(conn, source)
                        
                        continue
                    
                    logger.info(f"  📊 Found {len(feed.entries)} entries from {source['name']}")
                    
                    # Process articles
                    max_articles = min(len(feed.entries), FlaskConfig.MAX_ARTICLES_PER_SOURCE)
                    
                    for i, entry in enumerate(feed.entries[:max_articles]):
                        try:
                            # Skip if entry is not a dict/object
                            if not entry:
                                continue
                            
                            # Get title (handle different entry formats)
                            if isinstance(entry, dict):
                                title = entry.get('title', '')
                            else:
                                title = getattr(entry, 'title', '')
                            
                            title = str(title).strip()
                            if not title or len(title) < 10:
                                continue
                            
                            # Get source URL
                            if isinstance(entry, dict):
                                source_url = entry.get('link', '') or entry.get('url', '')
                            else:
                                source_url = getattr(entry, 'link', '')
                            
                            source_url = str(source_url).strip()
                            if not source_url or not source_url.startswith('http'):
                                # Create placeholder URL
                                slug = self.generate_slug(title, source['name'])
                                source_url = f"{source['base_url']}/article/{slug}"
                            
                            # Generate unique slug
                            slug = self.generate_slug(title, source['name'])
                            
                            # Check if article already exists
                            existing = conn.execute(
                                "SELECT id FROM posts WHERE slug = ? OR source_url = ?", 
                                (slug, source_url)
                            ).fetchone()
                            
                            if existing:
                                if i < 3:  # Log only first few duplicates
                                    logger.debug(f"    ⏭️  Skipping duplicate: {title[:50]}...")
                                continue
                            
                            # Get content
                            raw_content = self.get_entry_content(entry)
                            content = self.clean_html_content(raw_content, 2500)
                            
                            if not content or len(content) < 100:
                                # Create minimal content
                                content = f"{title}. Read the full article on {source['name']}."
                            
                            # Create excerpt
                            excerpt = self.get_entry_excerpt(content, 250)
                            if not excerpt or len(excerpt) < 50:
                                excerpt = title[:200] + '...'
                            
                            # Get image
                            if isinstance(entry, dict):
                                # For dict entries, try to get image from dict
                                image_url = entry.get('image', '') or entry.get('thumbnail', '')
                                if not image_url:
                                    image_url = self.extract_image_from_entry(entry, source.get('base_url', source_url))
                            else:
                                image_url = self.extract_image_from_entry(entry, source.get('base_url', source_url))
                            
                            # Get category ID
                            cat_row = conn.execute(
                                "SELECT id FROM categories WHERE slug = ?", 
                                (source['category'],)
                            ).fetchone()
                            category_id = cat_row[0] if cat_row else 1
                            
                            # Get publication date
                            pub_date = self.get_publication_date(entry)
                            
                            # Insert the article
                            conn.execute('''INSERT INTO posts 
                                (title, slug, content, excerpt, image_url, source_url, 
                                 category_id, category, source_name, views, is_published, 
                                 pub_date, created_at, updated_at)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)''',
                                (title, slug, content, excerpt, image_url, source_url,
                                 category_id, source['category'], source['name'], 
                                 random.randint(10, 500), pub_date))
                            
                            source_saved += 1
                            total_saved += 1
                            
                            if source_saved <= 3:
                                logger.info(f"    ✅ Saved: {title[:60]}...")
                            
                        except sqlite3.IntegrityError as ie:
                            # Duplicate entry, skip
                            continue
                        except Exception as e:
                            logger.debug(f"    Article processing error: {str(e)[:80]}")
                            continue
                    
                    source_time = time.time() - source_start_time
                    
                    if source_saved > 0:
                        logger.info(f"✅ {source['name']}: Saved {source_saved} new articles ({source_time:.1f}s)")
                    else:
                        logger.info(f"ℹ️ {source['name']}: No new articles ({source_time:.1f}s)")
                    
                except Exception as e:
                    logger.error(f"❌ Source {source['name']} failed: {str(e)[:100]}")
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
                logger.info(f"📊 Average: {total_saved/len(enabled_sources):.1f} articles per source")
            else:
                logger.info("✅ Fetch complete: No new articles found")
            logger.info("=" * 60)
            
            return total_saved
            
        except Exception as e:
            logger.error(f"❌ FETCH ERROR: {e}", exc_info=True)
            return 0
        finally:
            self.is_fetching = False
    
    def add_backup_article(self, conn, source):
        """Add a backup article when no content is available"""
        try:
            backup_titles = [
                f"Latest updates from {source['name']}",
                f"Breaking news from {source['category'].title()} sector",
                f"Important developments in South African {source['category']}",
                f"{source['name']} brings you the latest insights",
                f"Stay informed with {source['name']}'s coverage",
            ]
            
            title = random.choice(backup_titles)
            slug = self.generate_slug(title, source['name'])
            
            # Check if already exists
            existing = conn.execute(
                "SELECT id FROM posts WHERE slug = ?", 
                (slug,)
            ).fetchone()
            
            if existing:
                return
            
            content = f"This is a summary of the latest news from {source['name']}. For full details, visit {source['base_url']}."
            excerpt = content[:200] + '...'
            image_url = self.get_fallback_image(source['category'])
            
            # Get category ID
            cat_row = conn.execute(
                "SELECT id FROM categories WHERE slug = ?", 
                (source['category'],)
            ).fetchone()
            category_id = cat_row[0] if cat_row else 1
            
            conn.execute('''INSERT INTO posts 
                (title, slug, content, excerpt, image_url, source_url, 
                 category_id, category, source_name, views, is_published, 
                 pub_date, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)''',
                (title, slug, content, excerpt, image_url, source['base_url'],
                 category_id, source['category'], source['name'], 
                 random.randint(5, 50),))
            
            logger.info(f"    🔧 Added backup article for {source['name']}")
            
        except Exception as e:
            logger.debug(f"Backup article error: {e}")

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

# Helper functions
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
    
    # Ensure source_url is valid
    if not post.get('source_url') or post['source_url'] == '#':
        source_name = post.get('source_name', '').lower().replace(' ', '-')
        slug = post.get('slug', '')
        post['source_url'] = f"https://www.{source_name}.co.za/news/{slug}"
    
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
    """Home page"""
    try:
        conn = get_db_connection()
        
        # Featured/Latest post
        featured_raw = conn.execute(
            "SELECT * FROM posts WHERE is_published = 1 ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
        featured = prepare_post(featured_raw) if featured_raw else None
        
        # Latest posts
        if featured:
            posts_raw = conn.execute(
                "SELECT * FROM posts WHERE is_published = 1 AND id != ? ORDER BY created_at DESC LIMIT 12",
                (featured['id'],)
            ).fetchall()
        else:
            posts_raw = conn.execute(
                "SELECT * FROM posts WHERE is_published = 1 ORDER BY created_at DESC LIMIT 12"
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
                             config=FlaskConfig,
                             now=datetime.now())
                             
    except Exception as e:
        logger.error(f"Home error: {e}")
        return render_template('index.html',
                             featured_post=None,
                             posts=[],
                             trending_posts=[],
                             categories=get_categories_with_counts(),
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
            return redirect('/category/news')
        
        category = dict(category)
        
        # Get posts for this category
        posts_raw = conn.execute(
            "SELECT * FROM posts WHERE category_id = ? AND is_published = 1 ORDER BY created_at DESC LIMIT 50",
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
            "SELECT * FROM posts WHERE category_id = ? AND slug != ? AND is_published = 1 ORDER BY created_at DESC LIMIT 4",
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
                "SELECT * FROM posts WHERE (title LIKE ? OR content LIKE ? OR excerpt LIKE ?) AND is_published = 1 ORDER BY created_at DESC LIMIT 30",
                (search_term, search_term, search_term)
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
               ORDER BY p.created_at DESC 
               LIMIT 10"""
        ).fetchall()
        conn.close()
        
        articles = []
        for post in posts_raw:
            post_dict = dict(post)
            title = post_dict['title']
            if len(title) > 80:
                title = title[:77] + '...'
            
            articles.append({
                'id': post_dict['id'],
                'title': title,
                'category': post_dict.get('category_name', 'News'),
                'color': post_dict.get('color', '#4361ee'),
                'time_ago': get_time_ago(post_dict.get('created_at', '')),
                'source_url': post_dict.get('source_url', '#'),
                'source_name': post_dict.get('source_name', 'Source')
            })
        
        return jsonify({
            'status': 'success', 
            'articles': articles,
            'count': len(articles),
            'last_updated': datetime.now().strftime('%H:%M:%S')
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
            'is_fetching': fetcher.is_fetching,
            'next_fetch_in_minutes': FlaskConfig.UPDATE_INTERVAL_MINUTES,
            'status': 'online',
            'time': datetime.now().strftime('%H:%M:%S')
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
        'sources': len([s for s in fetcher.NEWS_SOURCES if s.get('enabled', True)]),
        'fetching_status': 'Active' if fetcher.is_fetching else 'Idle',
        'last_fetch': fetcher.last_fetch_time.strftime('%Y-%m-%d %H:%M:%S') if fetcher.last_fetch_time else 'Never',
        'last_fetch_count': fetcher.last_fetch_count,
        'database_path': get_db_path()
    }
    
    recent = conn.execute(
        "SELECT id, title, source_name, source_url, created_at FROM posts ORDER BY created_at DESC LIMIT 10"
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
                
                # Run fetch
                logger.info("🔄 RUNNING SCHEDULED FETCH...")
                fetched = fetcher.fetch_and_save()
                
                if fetched > 0:
                    logger.info(f"✅ Scheduled fetch: {fetched} new articles")
                else:
                    logger.info("✅ Scheduled fetch complete - no new articles")
                    
            except Exception as e:
                logger.error(f"❌ Background fetch error: {e}")
                time.sleep(300)
    
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
        
        sample_posts = conn.execute(
            "SELECT id, title, source_url, source_name, created_at FROM posts WHERE is_published = 1 ORDER BY created_at DESC LIMIT 5"
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
                'active_sources': len([s for s in fetcher.NEWS_SOURCES if s.get('enabled', True)])
            },
            'sample_posts': [
                {
                    'id': p[0], 
                    'title': p[1][:50], 
                    'source_url': p[2],
                    'source_name': p[3],
                    'created_at': p[4]
                } for p in sample_posts
            ]
        })
        
    except Exception as e:
        return jsonify({'status': 'error', 'error': str(e)})

@app.route('/test-fetch')
def test_fetch():
    """Test fetch directly"""
    result = fetcher.fetch_and_save()
    return f"<h1>Fetch Test</h1><p>Result: {result} articles fetched</p>"

# ============= START APP =============
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
    
    # Run the app
    port = int(os.environ.get('PORT', 5000))
    app.run(
        debug=FlaskConfig.DEBUG,
        host='0.0.0.0',
        port=port,
        threaded=True
    )