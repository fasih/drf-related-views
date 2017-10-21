# Python 2 and 3:
try:
    # Python 3 only:
    from urllib.parse import urlencode, urlsplit, parse_qs, unquote
except ImportError:
    # Python 2 only:
    from urlparse import parse_qs, urlsplit
    from urllib import urlencode, unquote
