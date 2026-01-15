# automation/config.py
AUTO_POST_CONFIG = {
    'enabled': True,
    'schedule': 'daily',
    'time': '09:00',
    'posts_per_category': 1,
    'max_posts_per_day': 3,
    'min_interval_hours': 4,
    'sources': {
        'rss': True,
        'ai_generation': True
    },
    'categories': ['grants', 'jobs', 'entertainment'],
    'rss_feeds': {
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
}
