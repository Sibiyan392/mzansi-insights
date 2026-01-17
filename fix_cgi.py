# cgi_fix.py - Fix for Python 3.13+ cgi module deprecation
import sys
import email
import email.policy

# Monkey patch for feedparser compatibility
if sys.version_info >= (3, 13):
    import cgi
    
    # Create a replacement for parse_header
    def parse_header(value):
        """Parse a Content-Type like header."""
        if not value:
            return '', {}
        
        # Parse with email module
        msg = email.message_from_string(f'Content-Type: {value}', 
                                       policy=email.policy.default)
        main_type = msg.get_content_type()
        params = dict(msg.get_params())
        
        return main_type, params
    
    # Monkey patch cgi module
    cgi.parse_header = parse_header
    
    # Also patch if feedparser imports it directly
    sys.modules['cgi'].parse_header = parse_header
    
    print("✅ Applied cgi module fix for Python 3.13+")
else:
    print("ℹ️ Python version < 3.13, no cgi fix needed")