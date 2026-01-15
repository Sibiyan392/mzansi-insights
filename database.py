from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from flask_login import UserMixin
import markdown
import os

db = SQLAlchemy()

class User(UserMixin, db.Model):
    """Admin user model"""
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<User {self.username}>'

class Category(db.Model):
    """Post categories"""
    __tablename__ = 'categories'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    slug = db.Column(db.String(50), unique=True, nullable=False)
    description = db.Column(db.String(200))
    posts = db.relationship('Post', backref='category_ref', lazy=True)
    
    def __repr__(self):
        return f'<Category {self.name}>'

class Post(db.Model):
    """News post model"""
    __tablename__ = 'posts'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    slug = db.Column(db.String(200), unique=True, nullable=False)
    content = db.Column(db.Text, nullable=False)
    excerpt = db.Column(db.String(300))
    image_url = db.Column(db.String(500))
    source_url = db.Column(db.String(500))
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'))
    author = db.Column(db.String(100), default='SA Updates')
    is_auto_generated = db.Column(db.Boolean, default=False)
    is_published = db.Column(db.Boolean, default=True)
    views = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    @property
    def formatted_date(self):
        return self.created_at.strftime('%B %d, %Y')
    
    @property
    def html_content(self):
        return markdown.markdown(self.content)
    
    def increment_views(self):
        self.views += 1
        db.session.commit()
    
    def __repr__(self):
        return f'<Post {self.title}>'

class RSSFeed(db.Model):
    """RSS feed sources"""
    __tablename__ = 'rss_feeds'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    url = db.Column(db.String(500), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'))
    is_active = db.Column(db.Boolean, default=True)
    last_fetch = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<RSSFeed {self.name}>'

def init_db(app):
    """Initialize database with default categories"""
    try:
        # Create data directory if it doesn't exist
        os.makedirs('data', exist_ok=True)
        
        with app.app_context():
            db.create_all()
            
            # Create default categories if they don't exist
            categories = [
                ('news', 'SA News', 'Latest South African news and updates'),
                ('jobs', 'Jobs', 'Employment opportunities and career advice'),
                ('grants', 'Grants', 'Government grants and funding opportunities'),
                ('entertainment', 'Entertainment', 'Movies, music, and entertainment news')
            ]
            
            for slug, name, desc in categories:
                if not Category.query.filter_by(slug=slug).first():
                    category = Category(name=name, slug=slug, description=desc)
                    db.session.add(category)
            
            # Create admin user if not exists
            if not User.query.filter_by(username='admin').first():
                from werkzeug.security import generate_password_hash
                admin = User(
                    username='admin',
                    password_hash=generate_password_hash('admin123')
                )
                db.session.add(admin)
            
            db.session.commit()
            print("✅ Database initialized successfully!")
            
    except Exception as e:
        print(f"❌ Database initialization error: {e}")
        print("⚠️  Please run 'python fix_db.py' to create the database manually.")