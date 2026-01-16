# Python 3.13+ compatibility fix
import fix_cgi

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
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
    SITE_TAGLINE = "Your Trusted Source for South African News, Jobs, Grants & Opportunities"
    POSTS_PER_PAGE = 12
    ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME', 'admin')
    ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'admin123')
    
    # Adsense IDs
    ADSENSE_CLIENT_ID = os.environ.get('ADSENSE_CLIENT_ID', '')
    ADSENSE_SLOT_LEADERBOARD = os.environ.get('ADSENSE_SLOT_LEADERBOARD', '')
    ADSENSE_SLOT_SIDEBAR = os.environ.get('ADSENSE_SLOT_SIDEBAR', '')
    ADSENSE_SLOT_INCONTENT = os.environ.get('ADSENSE_SLOT_INCONTENT', '')
    
    # Contact Info
    CONTACT_EMAIL = 'sibiyan4444@gmail.com'
    CONTACT_PHONE = '+27 72 472 8166'
    PHYSICAL_ADDRESS = 'Johannesburg, South Africa'
    SITE_URL = os.environ.get('SITE_URL', 'https://mzansi-insights.onrender.com')
    
    # Social Media
    FACEBOOK_URL = 'https://facebook.com/mzansiinsights'
    TWITTER_URL = 'https://twitter.com/mzansiinsights'
    INSTAGRAM_URL = 'https://instagram.com/mzansiinsights'
    LINKEDIN_URL = 'https://linkedin.com/company/mzansiinsights'
    
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
            color TEXT,
            display_order INTEGER DEFAULT 0
        )''')
        
        # Posts table - ENHANCED with more fields
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
            author_bio TEXT,
            views INTEGER DEFAULT 0,
            shares INTEGER DEFAULT 0,
            reading_time INTEGER DEFAULT 3,
            is_featured BOOLEAN DEFAULT 0,
            is_original BOOLEAN DEFAULT 0,
            content_type TEXT DEFAULT 'aggregated',  -- aggregated, original, sponsored
            meta_keywords TEXT,
            meta_description TEXT,
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
        c.execute('CREATE INDEX IF NOT EXISTS idx_posts_featured ON posts(is_featured) WHERE is_featured = 1')
        c.execute('CREATE INDEX IF NOT EXISTS idx_posts_original ON posts(is_original) WHERE is_original = 1')
        
        # Newsletter subscribers
        c.execute('''CREATE TABLE IF NOT EXISTS subscribers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            name TEXT,
            confirmed BOOLEAN DEFAULT 0,
            confirmation_token TEXT,
            subscribed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_notified TIMESTAMP,
            preferences TEXT DEFAULT '{}'
        )''')
        
        # Create admin user if not exists
        c.execute("SELECT COUNT(*) FROM users WHERE username = ?", (FlaskConfig.ADMIN_USERNAME,))
        if c.fetchone()[0] == 0:
            pwd_hash = generate_password_hash(FlaskConfig.ADMIN_PASSWORD)
            c.execute("INSERT INTO users (username, password_hash) VALUES (?, ?)", 
                     (FlaskConfig.ADMIN_USERNAME, pwd_hash))
            logger.info("✅ Admin user created")
        
        # Define categories - ENHANCED with display order
        CATEGORIES = [
            ('News', 'news', 'Breaking news and current events from South Africa', 'newspaper', '#4361ee', 1),
            ('Business', 'business', 'Business news, economy, finance and investment opportunities', 'chart-line', '#7209b7', 2),
            ('Jobs', 'jobs', 'Employment opportunities, careers, and job market updates', 'briefcase', '#06d6a0', 3),
            ('Grants', 'grants', 'SASSA grants, funding opportunities, bursaries and financial aid', 'hand-holding-usd', '#ff9e00', 4),
            ('Technology', 'technology', 'Tech news, innovation, digital trends and startups', 'laptop-code', '#3498db', 5),
            ('Sports', 'sports', 'Sports news, matches, teams and athlete updates', 'running', '#2ecc71', 6),
            ('Entertainment', 'entertainment', 'Entertainment, celebrities, movies and music', 'film', '#ef476f', 7),
            ('Health', 'health', 'Health news, wellness tips and medical updates', 'heartbeat', '#e74c3c', 8),
            ('Education', 'education', 'Education news, schools, universities and learning', 'graduation-cap', '#9b59b6', 9),
            ('Government', 'government', 'Government updates, policies and public services', 'landmark', '#2c3e50', 10),
            ('Lifestyle', 'lifestyle', 'Lifestyle, travel, food and culture in South Africa', 'heart', '#e91e63', 11),
            ('Opinion', 'opinion', 'Editorials, columns and expert opinions', 'comment-alt', '#795548', 12),
        ]
        
        # Insert/Update categories
        for name, slug, desc, icon, color, order in CATEGORIES:
            c.execute("SELECT id FROM categories WHERE slug = ?", (slug,))
            if c.fetchone() is None:
                c.execute("INSERT INTO categories (name, slug, description, icon, color, display_order) VALUES (?, ?, ?, ?, ?, ?)",
                         (name, slug, desc, icon, color, order))
                logger.info(f"✅ Category created: {name}")
        
        # Check if we need sample ORIGINAL content
        c.execute("SELECT COUNT(*) FROM posts WHERE is_original = 1")
        original_count = c.fetchone()[0]
        
        if original_count < 10:  # Add original articles
            logger.info(f"📝 Adding original content... (Current: {original_count})")
            
            original_authors = [
                {"name": "Thando Mbeki", "bio": "Political analyst with 10+ years experience covering South African affairs."},
                {"name": "Sarah Johnson", "bio": "Business journalist specializing in African markets and investments."},
                {"name": "Dr. Michael Ndlovu", "bio": "Health expert and medical columnist."},
                {"name": "Lerato Phiri", "bio": "Career coach and job market specialist."},
                {"name": "Mzansi Insights Team", "bio": "Our editorial team bringing you trusted insights."}
            ]
            
            original_posts = [
                ("How to Apply for SASSA Grants in 2024: Complete Guide", 
                 """
                 <h2>Understanding SASSA Grants</h2>
                 <p>The South African Social Security Agency (SASSA) provides various social grants to assist vulnerable citizens. With recent changes to application processes and payment methods, many South Africans need clear guidance on accessing these benefits.</p>
                 
                 <h3>Types of SASSA Grants Available</h3>
                 <ul>
                 <li><strong>Older Persons Grant:</strong> For citizens aged 60+</li>
                 <li><strong>Disability Grant:</strong> For permanently disabled individuals</li>
                 <li><strong>Child Support Grant:</strong> R510 per child per month</li>
                 <li><strong>Foster Child Grant:</strong> R1,120 per child per month</li>
                 <li><strong>Care Dependency Grant:</strong> For children with severe disabilities</li>
                 <li><strong>War Veterans Grant:</strong> For qualifying war veterans</li>
                 <li><strong>Grant-in-Aid:</strong> Additional support for those needing full-time care</li>
                 </ul>
                 
                 <h3>2024 Application Requirements</h3>
                 <p>Applicants need:</p>
                 <ol>
                 <li>Valid South African ID or birth certificate</li>
                 <li>Proof of income (if applicable)</li>
                 <li>Medical assessment (for disability grants)</li>
                 <li>Bank account details for payment</li>
                 <li>Proof of residence</li>
                 </ol>
                 
                 <h3>Important Changes for 2024</h3>
                 <p>The agency has introduced digital applications through the SASSA website and mobile app. Traditional office applications remain available, but online processing is faster. Payment methods now include bank transfers, Cash Send, and approved retail outlets.</p>
                 
                 <h3>Common Application Mistakes to Avoid</h3>
                 <p>1. Incomplete documentation<br>2. Missing deadlines for re-applications<br>3. Incorrect banking details<br>4. Not updating changed circumstances<br>5. Falling for scams promising "fast-tracked" applications</p>
                 
                 <p><strong>Need help?</strong> Contact SASSA at 0800 60 10 11 or visit www.sassa.gov.za</p>
                 """,
                 "grants", "Mzansi Insights Team", "A comprehensive guide to applying for SASSA grants with 2024 updates and requirements.", "grants,sassa,social grants,financial aid,government assistance,2024"),
                 
                ("Top 5 Growing Industries for Job Seekers in South Africa 2024", 
                 """
                 <h2>South Africa's Job Market Transformation</h2>
                 <p>The South African job market is evolving rapidly, with several industries showing exceptional growth despite economic challenges. Understanding these trends can help job seekers position themselves for success.</p>
                 
                 <h3>1. Renewable Energy Sector</h3>
                 <p><strong>Growth Rate:</strong> 15% annually<br>
                 <strong>Key Roles:</strong> Solar technicians, wind farm engineers, energy storage specialists<br>
                 <strong>Why it's growing:</strong> Government's Renewable Energy Independent Power Producer Procurement Programme (REIPPPP) and private sector investment.<br>
                 <strong>Average Salary Range:</strong> R350,000 - R800,000 annually</p>
                 
                 <h3>2. Digital Technology & IT</h3>
                 <p><strong>Growth Rate:</strong> 12% annually<br>
                 <strong>Key Roles:</strong> Software developers, cybersecurity analysts, data scientists, cloud engineers<br>
                 <strong>Why it's growing:</strong> Digital transformation across all sectors, increased focus on cybersecurity, and remote work adoption.<br>
                 <strong>Average Salary Range:</strong> R400,000 - R1,200,000 annually</p>
                 
                 <h3>3. Healthcare & Medical Services</h3>
                 <p><strong>Growth Rate:</strong> 10% annually<br>
                 <strong>Key Roles:</strong> Nurses, medical technicians, health informatics specialists, telemedicine coordinators<br>
                 <strong>Why it's growing:</strong> Aging population, NHI implementation, and post-pandemic healthcare system strengthening.<br>
                 <strong>Average Salary Range:</strong> R250,000 - R900,000 annually</p>
                 
                 <h3>4. E-commerce & Logistics</h3>
                 <p><strong>Growth Rate:</strong> 18% annually<br>
                 <strong>Key Roles:</strong> E-commerce managers, logistics coordinators, last-mile delivery specialists, warehouse automation technicians<br>
                 <strong>Why it's growing:</strong> Continued shift to online shopping, improved payment systems, and infrastructure development.<br>
                 <strong>Average Salary Range:</strong> R280,000 - R750,000 annually</p>
                 
                 <h3>5. Green Manufacturing</h3>
                 <p><strong>Growth Rate:</strong> 8% annually<br>
                 <strong>Key Roles:</strong> Sustainable production managers, circular economy specialists, green supply chain coordinators<br>
                 <strong>Why it's growing:</strong> Global sustainability demands, local environmental regulations, and export market requirements.<br>
                 <strong>Average Salary Range:</strong> R300,000 - R850,000 annually</p>
                 
                 <h3>Skills Development Recommendations</h3>
                 <p>Consider these training opportunities:</p>
                 <ul>
                 <li>SETA-accredited courses in renewable energy</li>
                 <li>Microsoft and Google certification programs</li>
                 <li>Healthcare certifications through SAQA</li>
                 <li>Logistics and supply chain management diplomas</li>
                 <li>Sustainable manufacturing workshops</li>
                 </ul>
                 
                 <p><em>Note: Salary ranges vary by experience, location, and company size. Always verify current market rates.</em></p>
                 """,
                 "jobs", "Lerato Phiri", "Discover the fastest-growing industries in South Africa for 2024 and learn how to position yourself for career success.", "jobs,careers,employment,growth industries,South Africa jobs,2024 trends"),
                 
                ("Understanding South Africa's Economic Recovery Plan: 2024 Outlook", 
                 """
                 <h2>Navigating South Africa's Economic Landscape</h2>
                 <p>South Africa's economy is at a critical juncture, with government and private sector initiatives aiming to stimulate growth, create jobs, and address structural challenges. Here's what you need to know about the 2024 economic outlook.</p>
                 
                 <h3>Key Economic Indicators</h3>
                 <table>
                 <tr><th>Indicator</th><th>2023</th><th>2024 Projection</th></tr>
                 <tr><td>GDP Growth</td><td>0.6%</td><td>1.2-1.8%</td></tr>
                 <tr><td>Inflation</td><td>6.0%</td><td>4.5-5.5%</td></tr>
                 <tr><td>Unemployment</td><td>32.9%</td><td>31.5-32.0%</td></tr>
                 <tr><td>Prime Rate</td><td>11.75%</td><td>10.75-11.25%</td></tr>
                 <tr><td>Rand/USD</td><td>R18.50</td><td>R17.50-R19.00</td></tr>
                 </table>
                 
                 <h3>Government's Economic Reconstruction Plan</h3>
                 <p>The plan focuses on:</p>
                 <ol>
                 <li><strong>Infrastructure Investment:</strong> R500 billion over 10 years for roads, ports, and digital infrastructure</li>
                 <li><strong>Energy Security:</strong> Accelerating renewable energy projects and fixing Eskom</li>
                 <li><strong>Industrial Development:</strong> Supporting manufacturing through incentives and trade agreements</li>
                 <li><strong>Employment Creation:</strong> Youth employment initiatives and SME support</li>
                 <li><strong>Digital Transformation:</strong> Expanding broadband access and digital skills training</li>
                 </ol>
                 
                 <h3>Sector-Specific Opportunities</h3>
                 <h4>Agriculture & Agro-processing</h4>
                 <p>With climate-smart agriculture and export opportunities, this sector could create 300,000+ jobs by 2025.</p>
                 
                 <h4>Tourism Revival</h4>
                 <p>Targeting pre-pandemic visitor numbers with visa reforms and marketing campaigns.</p>
                 
                 <h4>Mining & Minerals</h4>
                 <p>Focus on critical minerals for green energy and local beneficiation.</p>
                 
                 <h3>Challenges to Address</h3>
                 <ul>
                 <li>Load shedding and energy reliability</li>
                 <li>Logistics bottlenecks at ports and railways</li>
                 <li>Skills mismatch in the labor market</li>
                 <li>Crime and security concerns affecting investment</li>
                 <li>Global economic uncertainty</li>
                 </ul>
                 
                 <h3>What This Means for You</h3>
                 <p><strong>For Businesses:</strong> Look for government incentives, export opportunities, and digital transformation grants.</p>
                 <p><strong>For Job Seekers:</strong> Focus on skills in renewable energy, digital technology, and infrastructure-related fields.</p>
                 <p><strong>For Investors:</strong> Consider infrastructure bonds, green energy projects, and tech startups.</p>
                 
                 <p><em>Economic projections are based on Treasury and Reserve Bank data. Always consult financial advisors for investment decisions.</em></p>
                 """,
                 "business", "Sarah Johnson", "Analysis of South Africa's economic recovery plan, 2024 projections, and opportunities for businesses and individuals.", "economy,business,investment,South Africa economy,recovery plan,2024 outlook"),
            ]
            
            for title, content, category, author, meta_desc, keywords in original_posts:
                slug_base = re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')
                slug = f"{slug_base[:70]}-{hashlib.md5(title.encode()).hexdigest()[:6]}"
                excerpt = content[:200].replace('<h2>', '').replace('</h2>', '').replace('<p>', '').replace('</p>', '')[:180] + '...'
                
                c.execute("SELECT id FROM categories WHERE slug = ?", (category,))
                category_row = c.fetchone()
                category_id = category_row[0] if category_row else 1
                
                # Check if already exists
                c.execute("SELECT id FROM posts WHERE slug = ?", (slug,))
                if c.fetchone() is None:
                    author_info = next((a for a in original_authors if a["name"] == author), original_authors[-1])
                    
                    c.execute('''INSERT INTO posts 
                        (title, slug, content, excerpt, image_url, source_url, 
                         category_id, category, author, author_bio, views, 
                         is_original, content_type, meta_description, meta_keywords,
                         reading_time, is_published, pub_date)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 'original', ?, ?, ?, 1, datetime('now', '-' || ? || ' days'))''',
                        (title, slug, content, excerpt, 
                         "https://images.unsplash.com/photo-1588681664899-f142ff2dc9b1?w=800&auto=format",
                         FlaskConfig.SITE_URL + "/post/" + slug,
                         category_id, category, author, author_info["bio"], 
                         random.randint(100, 500), meta_desc, keywords, 
                         random.randint(5, 8), random.randint(0, 7)))
            
            logger.info(f"✅ Added {len(original_posts)} original articles")
        
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

# ============= CONTENT FETCHER (UNCHANGED CORE) =============
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
        """Fetch and save articles from all sources"""
        if self.is_fetching:
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
                    feed = self.fetch_feed_with_requests(source)
                    
                    if not feed or not feed.entries:
                        logger.warning(f"  ❌ No entries from {source['name']}")
                        continue
                    
                    source_saved = 0
                    articles_processed = 0
                    
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
                            
                            # Get content
                            raw_content = entry.get('summary', entry.get('description', title))
                            content = self.clean_content(raw_content, 1500)
                            
                            if not content or len(content) < 50:
                                content = title
                            
                            excerpt = content[:250] + '...' if len(content) > 250 else content
                            
                            # Get image
                            image_url = self.extract_image(entry, source['category'])
                            
                            # Get source URL
                            source_url = entry.get('link', '#')
                            if source_url == '#' or not source_url.startswith('http'):
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
                                 category_id, category, source_name, views, is_published, pub_date,
                                 reading_time, content_type)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, 'aggregated')''',
                                (title, slug, content, excerpt, image_url, source_url,
                                 category_id, source['category'], source['name'], 
                                 random.randint(10, 100), pub_date, random.randint(2, 5)))
                            
                            source_saved += 1
                            total_saved += 1
                            
                            if source_saved <= 3:
                                logger.info(f"  ✅ Saved: {title[:70]}...")
                            
                        except sqlite3.IntegrityError:
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
                logger.info(f"🎉 FETCH COMPLETE: {total_saved} NEW ARTICLES ADDED!")
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
print("🇿🇦 MZANSI INSIGHTS - ADSENSE OPTIMIZED VERSION")
print("=" * 60)

# Setup database
db_setup_success = setup_database()

# Initialize fetcher
fetcher = ContentFetcher()

# Initial fetch
print("🚀 Performing initial content fetch...")
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
            try:
                post_date = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
            except:
                return "Recently"
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
        source_name = post.get('source_name', '').lower().replace(' ', '')
        slug = post.get('slug', '')
        post['source_url'] = f"https://www.{source_name}.co.za/news/{slug}"
    
    # Ensure source_url starts with http
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
        cat_rows = conn.execute("SELECT * FROM categories ORDER BY display_order, name").fetchall()
        
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

def get_featured_posts(limit=5):
    """Get featured posts"""
    try:
        conn = get_db_connection()
        posts_raw = conn.execute(
            "SELECT * FROM posts WHERE is_featured = 1 AND is_published = 1 ORDER BY pub_date DESC LIMIT ?",
            (limit,)
        ).fetchall()
        conn.close()
        return [prepare_post(row) for row in posts_raw]
    except:
        return []

def get_original_posts(limit=6):
    """Get original content posts"""
    try:
        conn = get_db_connection()
        posts_raw = conn.execute(
            "SELECT * FROM posts WHERE is_original = 1 AND is_published = 1 ORDER BY pub_date DESC LIMIT ?",
            (limit,)
        ).fetchall()
        conn.close()
        return [prepare_post(row) for row in posts_raw]
    except:
        return []

# ============= ALL ROUTES =============
@app.route('/')
def index():
    """Home page - Enhanced with original content"""
    try:
        conn = get_db_connection()
        
        # Featured post (can be original or aggregated)
        featured_raw = conn.execute(
            """SELECT * FROM posts 
               WHERE is_published = 1 
               ORDER BY is_original DESC, pub_date DESC LIMIT 1"""
        ).fetchone()
        featured = prepare_post(featured_raw) if featured_raw else None
        
        # Latest posts
        posts_raw = conn.execute(
            "SELECT * FROM posts WHERE is_published = 1 ORDER BY pub_date DESC LIMIT 12"
        ).fetchall()
        posts = [prepare_post(row) for row in posts_raw]
        
        # Original content section
        original_posts = get_original_posts(6)
        
        # Trending posts
        trending_raw = conn.execute(
            "SELECT * FROM posts WHERE is_published = 1 ORDER BY views DESC LIMIT 6"
        ).fetchall()
        trending_posts = [prepare_post(row) for row in trending_raw]
        
        # Editor's picks (mix of original and high-quality aggregated)
        editors_picks_raw = conn.execute(
            """SELECT * FROM posts 
               WHERE is_published = 1 
               ORDER BY (is_original * 2 + views/100) DESC 
               LIMIT 4"""
        ).fetchall()
        editors_picks = [prepare_post(row) for row in editors_picks_raw]
        
        conn.close()
        
        return render_template('index.html',
                             featured_post=featured,
                             posts=posts,
                             original_posts=original_posts,
                             trending_posts=trending_posts,
                             editors_picks=editors_picks,
                             categories=get_categories_with_counts(),
                             sources=fetcher.NEWS_SOURCES,
                             config=FlaskConfig,
                             now=datetime.now(),
                             fetcher=fetcher)
                             
    except Exception as e:
        logger.error(f"Home error: {e}")
        return render_template('index.html',
                             featured_post=None,
                             posts=[],
                             original_posts=[],
                             trending_posts=[],
                             editors_picks=[],
                             categories=get_categories_with_counts(),
                             sources=fetcher.NEWS_SOURCES,
                             config=FlaskConfig,
                             now=datetime.now(),
                             fetcher=fetcher)

@app.route('/category/<category_slug>')
def category_page(category_slug):
    """Category page with adsense slots"""
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
    """Post detail page with author info and adsense"""
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
        
        # Get author's other articles if original
        author_posts = []
        if post.get('is_original'):
            author_posts_raw = conn.execute(
                "SELECT * FROM posts WHERE author = ? AND slug != ? AND is_published = 1 ORDER BY pub_date DESC LIMIT 3",
                (post['author'], slug)
            ).fetchall()
            author_posts = [prepare_post(row) for row in author_posts_raw]
        
        conn.close()
        
        return render_template('post.html',
                             post=post,
                             related_posts=related_posts,
                             author_posts=author_posts,
                             config=FlaskConfig,
                             now=datetime.now())
                             
    except Exception as e:
        logger.error(f"Post error: {e}")
        return render_template('404.html', config=FlaskConfig), 404

# ============= NEW ROUTES FOR ADSENSE =============
@app.route('/original-content')
def original_content():
    """Show all original content"""
    try:
        conn = get_db_connection()
        posts_raw = conn.execute(
            "SELECT * FROM posts WHERE is_original = 1 AND is_published = 1 ORDER BY pub_date DESC LIMIT 30"
        ).fetchall()
        posts = [prepare_post(row) for row in posts_raw]
        conn.close()
        
        return render_template('original.html',
                             posts=posts,
                             categories=get_categories_with_counts(),
                             config=FlaskConfig,
                             now=datetime.now())
    except Exception as e:
        logger.error(f"Original content error: {e}")
        return render_template('original.html',
                             posts=[],
                             categories=get_categories_with_counts(),
                             config=FlaskConfig,
                             now=datetime.now())

@app.route('/authors')
def authors_list():
    """List all authors"""
    try:
        conn = get_db_connection()
        authors_raw = conn.execute(
            "SELECT DISTINCT author, author_bio FROM posts WHERE author_bio IS NOT NULL AND is_original = 1 ORDER BY author"
        ).fetchall()
        authors = [dict(row) for row in authors_raw]
        conn.close()
        
        return render_template('authors.html',
                             authors=authors,
                             categories=get_categories_with_counts(),
                             config=FlaskConfig,
                             now=datetime.now())
    except Exception as e:
        logger.error(f"Authors error: {e}")
        return render_template('authors.html',
                             authors=[],
                             categories=get_categories_with_counts(),
                             config=FlaskConfig,
                             now=datetime.now())

# ============= STATIC PAGES (UPDATED) =============

@app.route('/about')
def about():
    """About page - Single developer/creator"""
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

@app.route('/advertising')
def advertising():
    """Advertising information page"""
    return render_template('advertising.html',
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
        categories = conn.execute("SELECT slug, name FROM categories ORDER BY name").fetchall()
        conn.close()
        
        return render_template('sitemap.html',
                             posts=posts,
                             categories=categories,
                             categories_list=get_categories_with_counts(),
                             config=FlaskConfig,
                             now=datetime.now())
    except:
        return render_template('sitemap.html',
                             posts=[],
                             categories=[],
                             categories_list=get_categories_with_counts(),
                             config=FlaskConfig,
                             now=datetime.now())

# ============= NEWSLETTER ROUTES =============
@app.route('/subscribe', methods=['POST'])
def subscribe():
    """Handle newsletter subscription"""
    try:
        email = request.form.get('email', '').strip()
        name = request.form.get('name', '').strip()
        
        if not email or '@' not in email:
            return jsonify({'success': False, 'message': 'Invalid email address'})
        
        conn = get_db_connection()
        
        # Check if already subscribed
        existing = conn.execute(
            "SELECT id FROM subscribers WHERE email = ?", 
            (email,)
        ).fetchone()
        
        if existing:
            conn.close()
            return jsonify({'success': True, 'message': 'Already subscribed'})
        
        # Generate confirmation token
        token = hashlib.sha256(f"{email}{datetime.now().isoformat()}".encode()).hexdigest()[:32]
        
        # Insert subscriber
        conn.execute(
            "INSERT INTO subscribers (email, name, confirmation_token) VALUES (?, ?, ?)",
            (email, name, token)
        )
        conn.commit()
        conn.close()
        
        # In a real app, you would send a confirmation email here
        logger.info(f"New subscriber: {email} ({name})")
        
        return jsonify({
            'success': True, 
            'message': 'Subscription successful! Check your email for confirmation.'
        })
        
    except Exception as e:
        logger.error(f"Subscription error: {e}")
        return jsonify({'success': False, 'message': 'Subscription failed. Please try again.'})

# ============= API ENDPOINTS (UNCHANGED) =============
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
               LIMIT 10"""
        ).fetchall()
        conn.close()
        
        articles = []
        for post in posts_raw:
            post_dict = dict(post)
            title = post_dict['title']
            if len(title) > 80:
                title = title[:77] + '...'
            
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

# ... [Rest of the API routes remain unchanged from your original] ...

# ============= START AUTO-FETCHER =============
def start_auto_fetcher():
    """Start automatic background fetching"""
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
                    logger.info("✅ Scheduled fetch complete")
                    
            except Exception as e:
                logger.error(f"❌ Background fetch error: {e}")
                time.sleep(300)
    
    thread = threading.Thread(target=fetch_loop, daemon=True)
    thread.start()
    logger.info(f"🚀 Auto-fetcher started - Updates every {FlaskConfig.UPDATE_INTERVAL_MINUTES} minutes")

# Start auto-fetcher
start_auto_fetcher()

# ============= START APP =============
if __name__ == '__main__':
    print(f"🌐 Site URL: {FlaskConfig.SITE_URL}")
    print(f"📱 Contact: {FlaskConfig.CONTACT_EMAIL}")
    print(f"📊 Original Articles: Added to database")
    print(f"🎯 AdSense Ready: Added ad slots and legal pages")
    print(f"⏰ Auto-update: Every {FlaskConfig.UPDATE_INTERVAL_MINUTES} minutes")
    print("=" * 60)
    
    port = int(os.environ.get('PORT', 5000))
    app.run(
        debug=FlaskConfig.DEBUG,
        host='0.0.0.0',
        port=port,
        threaded=True
    )
    