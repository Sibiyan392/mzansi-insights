# fix_cgi.py
"""
Fix for Python 3.13+ where cgi module was completely removed.
Monkey patches feedparser and other libraries that depend on cgi.
"""

import sys
import types

print("=" * 60)
print("PATCHING CGI MODULE FOR PYTHON 3.13+")
print("=" * 60)

# Check Python version
print(f"Python version: {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")

# Create a minimal cgi module replacement
class FakeCGIModule:
    """Minimal replacement for the removed cgi module."""
    
    @staticmethod
    def parse_header(value):
        """Parse Content-Type like headers (simplified version)."""
        if not value:
            return '', {}
        
        try:
            # Remove any leading/trailing whitespace
            value = value.strip()
            
            # Split main type from parameters
            if ';' in value:
                main_type, param_str = value.split(';', 1)
                main_type = main_type.strip().lower()
                
                # Parse parameters
                params = {}
                param_parts = param_str.split(';')
                for param in param_parts:
                    param = param.strip()
                    if '=' in param:
                        key, val = param.split('=', 1)
                        key = key.strip()
                        val = val.strip()
                        # Remove quotes if present
                        if (val.startswith('"') and val.endswith('"')) or \
                           (val.startswith("'") and val.endswith("'")):
                            val = val[1:-1]
                        params[key] = val
                
                return main_type, params
            else:
                return value.lower(), {}
                
        except Exception as e:
            print(f"parse_header error: {e}")
            return value.lower(), {}
    
    @staticmethod
    def parse_multipart(*args, **kwargs):
        """Stub for parse_multipart."""
        raise NotImplementedError("parse_multipart not implemented in cgi replacement")
    
    @staticmethod
    def parse_qs(*args, **kwargs):
        """Stub for parse_qs."""
        raise NotImplementedError("parse_qs not implemented in cgi replacement")
    
    @staticmethod
    def escape(s, quote=True):
        """Simple HTML escaping."""
        s = s.replace("&", "&amp;")
        s = s.replace("<", "&lt;")
        s = s.replace(">", "&gt;")
        if quote:
            s = s.replace('"', "&quot;")
            s = s.replace("'", "&#x27;")
        return s

# Create and install the fake cgi module BEFORE importing feedparser
print("Creating fake cgi module...")
cgi_module = types.ModuleType('cgi')
cgi_module.parse_header = FakeCGIModule.parse_header
cgi_module.parse_multipart = FakeCGIModule.parse_multipart
cgi_module.parse_qs = FakeCGIModule.parse_qs
cgi_module.escape = FakeCGIModule.escape
cgi_module.__version__ = "3.13+ compatibility layer"

# Install it in sys.modules
sys.modules['cgi'] = cgi_module
print("✅ Fake cgi module created and installed")

# Now patch feedparser's internal imports
def patch_feedparser_internals():
    """Patch feedparser's internal imports to use our fake cgi module."""
    try:
        # Import feedparser AFTER we've installed our fake cgi
        import feedparser
        
        # Patch feedparser's internal cgi reference
        if hasattr(feedparser, '_cgi'):
            feedparser._cgi = cgi_module
            print("✅ Patched feedparser._cgi")
        
        # Also patch the encodings module if needed
        if hasattr(feedparser, 'encodings'):
            try:
                feedparser.encodings.cgi = cgi_module
                print("✅ Patched feedparser.encodings.cgi")
            except:
                pass
        
        print("✅ Feedparser patched successfully")
        
    except Exception as e:
        print(f"⚠️  Warning: Could not patch feedparser: {e}")
        # Try to patch at the module level
        try:
            # Manually patch the feedparser.encodings module
            import feedparser.encodings as encodings_module
            encodings_module.cgi = cgi_module
            print("✅ Manually patched feedparser.encodings.cgi")
        except:
            pass

# Also create a direct patch for the parse_header function used by feedparser
def create_cgi_parse_header_patch():
    """Create a direct replacement for the parse_header function."""
    import email
    from email.message import EmailMessage
    
    def patched_parse_header(value):
        """Alternative implementation using email module."""
        if not value:
            return '', {}
        
        try:
            # Use email module for more robust parsing
            msg = EmailMessage()
            msg['Content-Type'] = value
            
            main_type = msg.get_content_type()
            params = dict(msg.get_params())
            
            # Remove None values and charset
            params = {k: v for k, v in params.items() 
                     if v is not None and k != 'charset'}
            
            return main_type, params
            
        except:
            # Fallback to simple parsing
            return FakeCGIModule.parse_header(value)
    
    return patched_parse_header

# Apply all patches
if __name__ == '__main__':
    patch_feedparser_internals()
    print("=" * 60)
    print("CGI PATCHING COMPLETE")
    print("=" * 60)