"""
Fix for cgi module removal in Python 3.13
"""

import sys

# Check Python version
python_version = sys.version_info

if python_version.major == 3 and python_version.minor >= 13:
    # Python 3.13+ - cgi module was removed
    # Create a minimal mock or use alternatives
    try:
        # Try to import from cgi module (if available)
        import cgi
    except ImportError:
        # Create minimal mock for cgi module
        class FieldStorage:
            def __init__(self, fp=None, headers=None, outerboundary=b'',
                        environ=os.environ, keep_blank_values=0, strict_parsing=0):
                self.list = []
                
        class MiniMock:
            FieldStorage = FieldStorage
            
        # Inject into sys.modules
        import types
        cgi = types.ModuleType('cgi')
        cgi.FieldStorage = FieldStorage
        sys.modules['cgi'] = cgi
else:
    # Python < 3.13 - import normally
    import cgi