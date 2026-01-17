# backup_feeds.py
import sqlite3
import random
from datetime import datetime, timedelta

def add_backup_posts():
    """Add some backup posts for testing"""
    conn = sqlite3.connect('data/posts.db')
    c = conn.cursor()
    
    backup_posts = [
        {
            'title': 'South African Economy Shows Growth in Q4 2025',
            'content': 'The South African economy has shown positive growth in the last quarter of 2025...',
            'category': 'business',
            'source_name': 'Mzansi Insights'
        },
        {
            'title': 'New Technology Hub Opens in Johannesburg',
            'content': 'A new technology innovation hub has opened in Johannesburg...',
            'category': 'technology',
            'source_name': 'Mzansi Insights'
        },
        # Add more backup posts...
    ]
    
    for post in backup_posts[:10]:
        slug = f"{post['title'].lower().replace(' ', '-')[:50]}-{random.randint(1000,9999)}"
        c.execute('''INSERT OR IGNORE INTO posts 
                    (title, slug, content, excerpt, category, source_name, views, is_published)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 1)''',
                 (post['title'], slug, post['content'], 
                  post['content'][:200] + '...' if len(post['content']) > 200 else post['content'],
                  post['category'], post['source_name'], random.randint(10, 100)))
    
    conn.commit()
    conn.close()
    print("✅ Backup posts added")

if __name__ == '__main__':
    add_backup_posts()