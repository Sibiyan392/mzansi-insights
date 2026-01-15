# automation/rss_importer.py
"""
RSS feed importer for auto-posting
"""
import feedparser
import requests
from bs4 import BeautifulSoup
import random
from datetime import datetime
from urllib.parse import urlparse
import time

class RSSImporter:
    def __init__(self):
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        ]
        
        self.rss_feeds = {
            'grants': [
                'https://www.gov.za/rss',
                'https://www.sassa.gov.za/feed',
            ],
            'jobs': [
                'https://www.careers24.com/rss/',
                'https://www.pnet.co.za/rss/',
            ],
            'entertainment': [
                'https://www.news24.com/entertainment/rss',
                'https://www.channel24.co.za/RSS/',
            ]
        }
    
    def fetch_feed(self, feed_url, category):
        """Fetch and parse RSS feed"""
        try:
            headers = {'User-Agent': random.choice(self.user_agents)}
            feed = feedparser.parse(feed_url)
            
            articles = []
            for entry in feed.entries[:5]:  # Get latest 5
                article = {
                    'title': self.clean_text(entry.title),
                    'summary': self.clean_text(entry.get('summary', '')),
                    'link': entry.link,
                    'published': entry.get('published', datetime.now().isoformat()),
                    'source': urlparse(feed_url).netloc,
                    'category': category
                }
                
                # Get full content if needed
                if len(article['summary']) < 100:
                    article['content'] = self.fetch_article_content(entry.link)
                else:
                    article['content'] = article['summary']
                
                articles.append(article)
            
            return articles
            
        except Exception as e:
            print(f"Error fetching feed {feed_url}: {e}")
            return []
    
    def fetch_article_content(self, url):
        """Fetch full article content"""
        try:
            headers = {'User-Agent': random.choice(self.user_agents)}
            response = requests.get(url, headers=headers, timeout=10)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Remove unwanted elements
            for element in soup(['script', 'style', 'nav', 'footer', 'header']):
                element.decompose()
            
            # Try to find main content
            content_selectors = ['article', 'main', '.content', '.article', '.post-content']
            content = None
            
            for selector in content_selectors:
                content = soup.select_one(selector)
                if content:
                    break
            
            if content:
                text = content.get_text(separator=' ', strip=True)
            else:
                text = soup.get_text(separator=' ', strip=True)
            
            return self.clean_text(text[:1500])  # Limit length
            
        except Exception as e:
            print(f"Error fetching article content: {e}")
            return ""
    
    def clean_text(self, text):
        """Clean text"""
        if not text:
            return ""
        
        # Basic cleaning
        text = ' '.join(text.split())  # Remove extra whitespace
        return text.strip()
    
    def get_latest_articles(self, category, limit=2):
        """Get latest articles for a category"""
        articles = []
        
        if category not in self.rss_feeds:
            return articles
        
        for feed_url in self.rss_feeds[category]:
            feed_articles = self.fetch_feed(feed_url, category)
            articles.extend(feed_articles)
            
            # Small delay between requests
            time.sleep(1)
        
        # Sort by date and limit
        articles.sort(key=lambda x: x.get('published', ''), reverse=True)
        return articles[:limit]

# Test function
def test_rss_import():
    """Test RSS import"""
    importer = RSSImporter()
    
    print("Testing RSS import...")
    for category in ['grants', 'jobs', 'entertainment']:
        print(f"\n{category.upper()}:")
        articles = importer.get_latest_articles(category, limit=1)
        if articles:
            print(f"  Found: {articles[0]['title'][:60]}...")
        else:
            print("  No articles found")

if __name__ == "__main__":
    test_rss_import()