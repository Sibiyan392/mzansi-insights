# automation/content_generator.py
"""
Content generation for auto-posting
"""
import random
from datetime import datetime

class ContentGenerator:
    def __init__(self):
        self.templates = self.load_templates()
    
    def load_templates(self):
        """Load content templates"""
        return {
            'grants': [
                {
                    'title': "New Government Funding Program Launched",
                    'template': """
                    <h2>Latest Funding Opportunity</h2>
                    <p>The South African government has introduced a new funding program aimed at supporting {target_audience}.</p>
                    
                    <h3>Program Details</h3>
                    <p>This initiative focuses on providing financial assistance for {purpose}. Eligible applicants can receive up to R{amount} in support.</p>
                    
                    <h3>Eligibility Criteria</h3>
                    <p>To qualify, applicants must meet the following requirements:</p>
                    <ul>
                        <li>South African citizen or permanent resident</li>
                        <li>{requirement1}</li>
                        <li>{requirement2}</li>
                    </ul>
                    
                    <h3>Application Process</h3>
                    <p>Applications can be submitted through the official government portal. The deadline for submissions is {deadline}.</p>
                    
                    <h3>Additional Support</h3>
                    <p>For more information and application assistance, visit the official government website or contact the support hotline.</p>
                    """
                }
            ],
            'jobs': [
                {
                    'title': "Career Opportunities in Growing Sector",
                    'template': """
                    <h2>Employment Update: {sector} Sector</h2>
                    <p>The {sector} industry in South Africa is experiencing significant growth, creating new job opportunities.</p>
                    
                    <h3>Available Positions</h3>
                    <p>Companies are currently hiring for various roles including:</p>
                    <ul>
                        <li>{position1}</li>
                        <li>{position2}</li>
                        <li>{position3}</li>
                    </ul>
                    
                    <h3>Salary Information</h3>
                    <p>Competitive salary packages ranging from R{salary_low} to R{salary_high} are being offered, depending on experience and qualifications.</p>
                    
                    <h3>Required Skills</h3>
                    <p>Successful candidates typically possess skills in {skill1}, {skill2}, and {skill3}.</p>
                    
                    <h3>How to Apply</h3>
                    <p>Interested candidates should submit their CVs through company websites or recruitment portals.</p>
                    """
                }
            ],
            'entertainment': [
                {
                    'title': "Local Entertainment Industry Update",
                    'template': """
                    <h2>Entertainment News: {event_type}</h2>
                    <p>The South African entertainment scene is buzzing with the latest {event_type} developments.</p>
                    
                    <h3>Recent Achievements</h3>
                    <p>Local artists and creators have been recognized for their work in {field}, showcasing the talent within South Africa's creative community.</p>
                    
                    <h3>Upcoming Events</h3>
                    <p>Several exciting events are scheduled, including {event1} and {event2}. These gatherings provide opportunities to experience diverse cultural expressions.</p>
                    
                    <h3>Industry Growth</h3>
                    <p>The entertainment sector continues to expand, with increased investment in {area1} and {area2}. This growth creates more opportunities for local talent.</p>
                    
                    <h3>Support Local</h3>
                    <p>By supporting South African entertainment, you contribute to the growth of the creative economy and help showcase local talent on a global stage.</p>
                    """
                }
            ]
        }
    
    def generate_content(self, category):
        """Generate content for a specific category"""
        if category not in self.templates:
            category = 'grants'
        
        template = random.choice(self.templates[category])
        title = template['title']
        
        # Fill template with random data
        if category == 'grants':
            content = template['template'].format(
                target_audience=random.choice(['students', 'small businesses', 'entrepreneurs', 'artists']),
                purpose=random.choice(['education expenses', 'business development', 'housing needs', 'skill training']),
                amount=random.choice(['15000', '25000', '50000', '100000']),
                requirement1=random.choice(['Minimum age of 18 years', 'Proof of income below threshold', 'Business registration documents', 'Academic transcripts']),
                requirement2=random.choice(['Residence in specific provinces', 'Membership in relevant associations', 'Completion of prerequisite courses', 'Business plan submission']),
                deadline=random.choice(['March 31, 2024', 'April 15, 2024', 'May 30, 2024', 'June 30, 2024'])
            )
            
        elif category == 'jobs':
            content = template['template'].format(
                sector=random.choice(['Technology', 'Healthcare', 'Renewable Energy', 'Finance', 'Education']),
                position1=random.choice(['Software Developer', 'Data Analyst', 'Project Manager', 'Marketing Specialist']),
                position2=random.choice(['IT Support', 'Sales Representative', 'Content Creator', 'Administrative Assistant']),
                position3=random.choice(['Graphic Designer', 'Account Manager', 'Quality Assurance', 'Customer Service']),
                salary_low=random.choice(['25000', '30000', '35000', '40000']),
                salary_high=random.choice(['60000', '80000', '100000', '120000']),
                skill1=random.choice(['Python programming', 'Digital marketing', 'Project management', 'Data analysis']),
                skill2=random.choice(['Communication skills', 'Team collaboration', 'Problem solving', 'Creative thinking']),
                skill3=random.choice(['Attention to detail', 'Time management', 'Customer service', 'Technical writing'])
            )
            
        else:  # entertainment
            content = template['template'].format(
                event_type=random.choice(['music release', 'film production', 'art exhibition', 'cultural festival']),
                field=random.choice(['music composition', 'film directing', 'visual arts', 'performance art']),
                event1=random.choice(['local music festival', 'film screening', 'art gallery opening', 'theater production']),
                event2=random.choice(['cultural celebration', 'talent showcase', 'creative workshop', 'industry networking']),
                area1=random.choice(['digital content creation', 'live performances', 'film production', 'music recording']),
                area2=random.choice(['streaming platforms', 'event management', 'artist development', 'creative technology'])
            )
        
        # Generate excerpt
        excerpt = self.generate_excerpt(content)
        
        return {
            'title': title,
            'content': content,
            'excerpt': excerpt,
            'category': category,
            'author': 'Auto Content Generator',
            'tags': [category, 'South Africa', 'News', 'Update', 'Auto-Generated'],
            'auto_generated': True
        }
    
    def generate_excerpt(self, content, max_length=150):
        """Generate excerpt from content"""
        # Remove HTML tags
        import re
        text = re.sub(r'<[^>]+>', '', content)
        
        # Get first meaningful sentences
        sentences = [s.strip() for s in text.split('.') if s.strip()]
        
        if not sentences:
            return "Latest update from South Africa..."
        
        excerpt = sentences[0]
        if len(excerpt) > max_length:
            excerpt = excerpt[:max_length-3] + '...'
        
        return excerpt

# Test function
def test_generation():
    """Test content generation"""
    generator = ContentGenerator()
    
    print("Testing content generation...")
    for category in ['grants', 'jobs', 'entertainment']:
        print(f"\n{category.upper()}:")
        content = generator.generate_content(category)
        print(f"Title: {content['title']}")
        print(f"Excerpt: {content['excerpt'][:80]}...")

if __name__ == "__main__":
    test_generation()