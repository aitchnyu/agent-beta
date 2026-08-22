"""ASGI config for djangoproject project."""

import os

from django.core.asgi import get_asgi_application
from granian.utils.proxies import wrap_asgi_with_proxy_headers

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "djangoproject.settings")

application = get_asgi_application()

# Served by granian behind caddy (test VM): apply the proxy's forwarded
# headers (X-Forwarded-Proto/For) so Django sees the real scheme/host —
# URL-building (absolute redirects, makeloginlink printouts) depends on it.
# The proxy is caddy on 127.0.0.1 (trusted_hosts); without the wrap Django
# sees plain http and generates http://… URLs behind the https site. No-op
# semantics in dev (runserver uses WSGI and never imports this wrapper).
application = wrap_asgi_with_proxy_headers(application, trusted_hosts="127.0.0.1")
