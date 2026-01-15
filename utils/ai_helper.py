# utils/ai_helper.py
"""
AI helper functions for content generation and optimization
"""

import re
from typing import List, Dict, Optional

class AIHelper:
    @staticmethod
    def summarize_content(content: str, max_length: int = 150) -> str:
        """Generate a summary of the content"""
        # Remove HTML tags
        text = re.sub(r'<[^>]+>', '', content)
        
        # Split into sentences
        sentences = re.split(r'[.!?]+', text)
        sentences = [s.strip() for s in sentences if s.strip()]
        
        if not sentences:
            return ""
        
        # Take first few sentences
        summary = []
        total_length = 0
        
        for sentence in sentences:
            if total_length + len(sentence) <= max_length:
                summary.append(sentence)
                total_length += len(sentence)
            else:
                break
        
        if summary:
            return '. '.join(summary) + '.'
        
        # If all sentences are too long, truncate first sentence
        return sentences[0][:max_length] + '...'
    
    @staticmethod
    def generate_tags(content: str, max_tags: int = 5) -> List[str]:
        """Generate relevant tags from content"""
        # Common stop words to ignore
        stop_words = {'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'shall', 'should', 'may', 'might', 'must', 'can', 'could', 'a', 'an', 'this', 'that', 'these', 'those', 'i', 'you', 'he', 'she', 'it', 'we', 'they', 'me', 'him', 'her', 'us', 'them', 'my', 'your', 'his', 'its', 'our', 'their', 'mine', 'yours', 'hers', 'ours', 'theirs'}
        
        # Remove HTML and punctuation
        text = re.sub(r'<[^>]+>', '', content.lower())
        words = re.findall(r'\b[a-z]{3,}\b', text)
        
        # Count word frequency
        word_counts = {}
        for word in words:
            if word not in stop_words:
                word_counts[word] = word_counts.get(word, 0) + 1
        
        # Get most common words
        sorted_words = sorted(word_counts.items(), key=lambda x: x[1], reverse=True)
        tags = [word for word, count in sorted_words[:max_tags]]
        
        return tags
    
    @staticmethod
    def generate_excerpt(content: str, length: int = 200) -> str:
        """Generate an excerpt from content"""
        # Remove HTML tags
        text = re.sub(r'<[^>]+>', '', content)
        
        # Truncate to specified length
        if len(text) <= length:
            return text
        
        # Try to cut at sentence boundary
        truncated = text[:length]
        last_period = truncated.rfind('.')
        last_question = truncated.rfind('?')
        last_exclamation = truncated.rfind('!')
        
        cut_point = max(last_period, last_question, last_exclamation)
        if cut_point > length * 0.5:  # Only cut if we found a reasonable boundary
            return truncated[:cut_point + 1]
        
        return truncated + '...'
    
    @staticmethod
    def optimize_title(title: str) -> str:
        """Optimize title for SEO"""
        # Capitalize important words
        small_words = {'a', 'an', 'and', 'as', 'at', 'but', 'by', 'for', 'if', 'in', 'of', 'on', 'or', 'the', 'to', 'with'}
        
        words = title.split()
        optimized_words = []
        
        for i, word in enumerate(words):
            if i == 0 or i == len(words) - 1 or word.lower() not in small_words:
                optimized_words.append(word.capitalize())
            else:
                optimized_words.append(word.lower())
        
        return ' '.join(optimized_words)