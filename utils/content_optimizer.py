# utils/content_optimizer.py
"""
Content optimization for SEO and readability
"""

import re
from typing import Dict, List

class ContentOptimizer:
    @staticmethod
    def add_header_tags(content: str) -> str:
        """Add header tags to content for better structure"""
        # Split content by paragraphs
        paragraphs = content.split('\n')
        optimized = []
        
        for i, para in enumerate(paragraphs):
            para = para.strip()
            if not para:
                continue
            
            # Check if paragraph looks like a heading
            if len(para) < 100 and not para.startswith('<'):
                # Check if it ends with punctuation (probably not a heading)
                if not para.endswith(('.', '?', '!')):
                    # Make it an H2 if it's early in content
                    if i < 3:
                        para = f'<h2>{para}</h2>'
                    else:
                        para = f'<h3>{para}</h3>'
            
            optimized.append(para)
        
        return '\n'.join(optimized)
    
    @staticmethod
    def format_for_web(content: str) -> str:
        """Format content for web display"""
        # Replace line breaks with paragraphs
        paragraphs = content.split('\n')
        formatted = []
        
        for para in paragraphs:
            para = para.strip()
            if para and not para.startswith('<'):
                formatted.append(f'<p>{para}</p>')
            elif para:
                formatted.append(para)
        
        return '\n'.join(formatted)
    
    @staticmethod
    def generate_meta_description(content: str, max_length: int = 160) -> str:
        """Generate meta description from content"""
        # Remove HTML tags
        text = re.sub(r'<[^>]+>', '', content)
        
        # Truncate to max length
        if len(text) <= max_length:
            return text
        
        # Try to cut at sentence boundary
        truncated = text[:max_length]
        last_space = truncated.rfind(' ')
        
        if last_space > max_length * 0.7:
            return truncated[:last_space] + '...'
        
        return text[:max_length] + '...'
    
    @staticmethod
    def extract_keywords(content: str, num_keywords: int = 10) -> List[str]:
        """Extract keywords from content"""
        # Remove HTML and common words
        text = re.sub(r'<[^>]+>', '', content.lower())
        
        # Find words
        words = re.findall(r'\b[a-z]{4,}\b', text)
        
        # Common words to exclude
        common_words = {
            'that', 'with', 'this', 'from', 'have', 'more', 'will',
            'about', 'their', 'what', 'which', 'there', 'were', 'when',
            'your', 'they', 'some', 'these', 'would', 'other', 'been',
            'should', 'could', 'very', 'because', 'through'
        }
        
        # Count word frequency
        word_counts = {}
        for word in words:
            if word not in common_words:
                word_counts[word] = word_counts.get(word, 0) + 1
        
        # Get most frequent words
        sorted_words = sorted(word_counts.items(), key=lambda x: x[1], reverse=True)
        return [word for word, count in sorted_words[:num_keywords]]