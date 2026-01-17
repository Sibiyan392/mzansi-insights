# fix_cgi.py
"""
Fix for Python 3.13+ where cgi module was deprecated and removed.
Provides compatibility shims for feedparser and other libraries.
"""

import sys
import email
from email.message import EmailMessage

print("Patching cgi module for Python 3.13+...")

# Monkey patch cgi module if it's missing parse_header
try:
    import cgi
    # Test if parse_header exists
    cgi.parse_header
except AttributeError:
    # Create minimal cgi module replacement
    class FakeCGIModule:
        @staticmethod
        def parse_header(value):
            """Parse Content-Type like headers."""
            if not value:
                return '', {}
            
            # Simple parsing
            parts = value.split(';', 1)
            main_type = parts[0].strip().lower()
            
            params = {}
            if len(parts) > 1:
                # Parse parameters like charset=utf-8
                param_parts = parts[1].split(';')
                for param in param_parts:
                    if '=' in param:
                        key, val = param.split('=', 1)
                        params[key.strip()] = val.strip().strip('"\'')
            
            return main_type, params
    
    # Replace cgi module with our fake one
    import types
    sys.modules['cgi'] = types.ModuleType('cgi')
    sys.modules['cgi'].parse_header = FakeCGIModule.parse_header
    
    # Also patch it directly for feedparser
    import feedparser
    feedparser._cgi = sys.modules['cgi']
    
    print("✅ cgi module patched successfully")

# Alternative: Direct patch for feedparser
def patch_feedparser():
    """Patch feedparser to use email module instead of cgi."""
    import feedparser
    from email.message import EmailMessage
    
    original_parse = feedparser._parse_content_type
    
    def patched_parse_content_type(headers):
        """Use email module instead of cgi."""
        content_type = headers.get('content-type', '')
        if not content_type:
            return '', {}
        
        try:
            msg = EmailMessage()
            msg['Content-Type'] = content_type
            main_type = msg.get_content_type()
            
            # Extract params
            params = {}
            for key, value in msg.get_params():
                if key and value and key != 'charset':
                    params[key] = value
            
            return main_type, params
        except:
            # Fallback to simple parsing
            return original_parse(headers)
    
    feedparser._parse_content_type = patched_parse_content_type
    print("✅ Feedparser patched successfully")

# Run the patches
if __name__ == '__main__':
    patch_feedparser()