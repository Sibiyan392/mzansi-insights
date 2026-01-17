# fix_cgi.py - Compatibility for Python 3.13+
import sys
import types

# Patch cgi module (removed in Python 3.13)
try:
    import cgi
    print("cgi module already exists")
except ImportError:
    print("Patching cgi module for Python 3.13+...")
    
    class DummyCGI:
        @staticmethod
        def escape(s, quote=True):
            if not s:
                return s
            s = s.replace("&", "&amp;")
            s = s.replace("<", "&lt;")
            s = s.replace(">", "&gt;")
            if quote:
                s = s.replace('"', "&quot;")
            return s
    
    cgi_module = types.ModuleType('cgi')
    cgi_module.escape = DummyCGI.escape
    sys.modules['cgi'] = cgi_module
    
    # Also ensure html module has escape
    import html
    if not hasattr(html, 'escape'):
        html.escape = DummyCGI.escape