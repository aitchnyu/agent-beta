"""Django settings for djangoproject project.

For more information on this file, see
https://docs.djangoproject.com/en/6.0/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/6.0/ref/settings/
"""

import os
from pathlib import Path

from django.utils.csp import CSP

from djangoapp.logging import configure_logging, json_formatter

# Environment comes from the caller, not python-dotenv: dev processes are
# launched via ./run (which shell-sources .env: `set -a; . ./.env; set +a`),
# and on the VM every systemd unit carries
# EnvironmentFile=/etc/credentials/app/.env.vm (single fixed app).

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/6.0/howto/deployment/checklist/

SECRET_KEY = os.environ["SECRET_KEY"]

DEBUG = os.environ["DEBUG"] == "True"

if not DEBUG and SECRET_KEY == "fake":  # noqa: S105
    msg = "Do not use `fake` secret key in production"
    raise ValueError(msg)

# Structured (JSON/NDJSON) logging: one object per line, jq-filterable.
# Configured once at import so it's ready before the first log call.
configure_logging()

# Convert comma-separated string to list
ALLOWED_HOSTS = [host.strip() for host in os.environ["ALLOWED_HOSTS"].split(",") if host.strip()]


# Application definition

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.postgres",
    # Required by allauth
    "django.contrib.sites",
    # Allauth apps
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    # Google only; adding a provider changes this line + form-action below
    # (docs/social-providers.md).
    "allauth.socialaccount.providers.google",
    "djangoapp",
    "ourapp",
    "inertia",
    "huey.contrib.djhuey",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csp.ContentSecurityPolicyMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "inertia.middleware.InertiaMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    # Bind request_id + viewer identity into the log context (runs after
    # AuthenticationMiddleware so request.user is resolved) before any view log.
    "djangoapp.middleware.LoggingContextMiddleware",
    # Shares the viewer profile + superuser flag on every Inertia page;
    # reads request.user, so it must run after AuthenticationMiddleware.
    "djangoapp.middleware.SharedPropsMiddleware",
    "djangoapp.middleware.SessionIdleTouchMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    # Allauth middleware
    "allauth.account.middleware.AccountMiddleware",
]

ROOT_URLCONF = "djangoproject.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        # Searched before app dirs, so these overrides beat allauth's own copies.
        "DIRS": [BASE_DIR / "djangoapp" / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.template.context_processors.csp",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "djangoproject.wsgi.application"


# Database
# https://docs.djangoproject.com/en/6.0/ref/settings/#databases

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ["DB_NAME"],
        "USER": os.environ["DB_USER"],
        "PASSWORD": os.environ["DB_PASSWORD"],
        "HOST": os.environ["DB_HOST"],
        "PORT": os.environ["DB_PORT"],
    }
}


# Password validation
# https://docs.djangoproject.com/en/6.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


# Internationalization
# https://docs.djangoproject.com/en/6.0/topics/i18n/

LANGUAGE_CODE = "en-us"

TIME_ZONE = os.environ["TIME_ZONE"]

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/6.0/howto/static-files/

STATIC_URL = "static/"

# Where `collectstatic` gathers files for the serving layer (caddy serves
# /static/* from it on the test VM — Django serves nothing under /static
# when DEBUG=False). Unused in dev (runserver serves app static dirs
# directly).
STATIC_ROOT = Path(os.environ["STATIC_ROOT"])

# Origins trusted for secure POSTs, DERIVED from ALLOWED_HOSTS (no env knob):
# the app is always reached over HTTPS at its allowed hosts — behind caddy on
# the VM (https://localhost:8000 behind caddy), plain runserver in dev (where the
# https://localhost origins are simply unused). ALLOWED_HOSTS validates the
# Host header; this gates the CSRF Origin/Referer match, which needs scheme.
# Behind the proxy this is belt-and-braces: Django also accepts an Origin that
# matches the request's own scheme+host (incl. non-standard ports).
CSRF_TRUSTED_ORIGINS = [f"https://{host}" for host in ALLOWED_HOSTS]

# Two layers make Django see https behind caddy: djangoproject/asgi.py wraps
# the app with granian's proxy-header handler (peer-checked, the primary
# mechanism on the VM), and this setting makes Django itself trust
# X-Forwarded-Proto (META-style key) — covering WSGI/test contexts and any
# non-granian deployment. Safe ONLY because granian binds 127.0.0.1
# (deploy/granian.service.in) and dev runserver never sends the header.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# Default primary key field type
# https://docs.djangoproject.com/en/6.0/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Custom user model
AUTH_USER_MODEL = "djangoapp.User"

# Allauth configuration
AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]

SITE_ID = 1

# Only social login - no local email/password account creation or login.
SOCIALACCOUNT_ONLY = True
ACCOUNT_EMAIL_VERIFICATION = "none"
SOCIALACCOUNT_EMAIL_VERIFICATION = "none"
SOCIALACCOUNT_EMAIL_REQUIRED = True

# A Google-verified email IS the identity: logging in with an email logs INTO that
# account instead of asking you to connect it
SOCIALACCOUNT_PROVIDERS = {
    "google": {"EMAIL_AUTHENTICATION": True},
}

LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/"

# Inertia settings
INERTIA_LAYOUT = "inertia/base.html"

# Content Security Policy
# https://docs.djangoproject.com/en/6.0/ref/csp/

# Sessions expire SESSION_IDLE_DAYS days after the user's LAST request
# (sliding — SessionIdleTouchMiddleware re-arms at half-life), not after
# login. Mandatory: no silent default lifetime.
SESSION_COOKIE_AGE = int(os.environ["SESSION_IDLE_DAYS"]) * 86400

_CSP_COMMON = {
    # Fallback for any directive not explicitly set
    "default-src": [CSP.SELF],
    # Block all plugins (Flash, Java applets, etc.)
    "object-src": [],
    # Images (data: covers base64-encoded images in rich text editors)
    "img-src": [CSP.SELF, "data:"],
    # Web fonts
    "font-src": [CSP.SELF],
    # Form submissions — Google's authorize domain (the login POST's redirect
    # chain is form-action-checked); change per provider (docs/social-providers.md).
    "form-action": [
        CSP.SELF,
        "https://accounts.google.com",
    ],
    # Who can embed this page in an iframe (clickjacking protection)
    "frame-ancestors": [CSP.SELF],
    # Restricts URLs that can be used in the <base> tag
    "base-uri": [CSP.SELF],
}

_CSP_STRICT = _CSP_COMMON | {
    # JavaScript sources — unsafe-eval: zod's sync-parse fast path (and its
    # feature probe) JIT-compiles via new Function; avoid csp violation
    "script-src": [CSP.SELF, CSP.UNSAFE_EVAL],
    # CSS sources — unsafe-inline: sweetalert2 (the toast layer,
    # utils/sweetalert.ts) injects its stylesheet as an inline <style> at
    # first toast
    "style-src": [CSP.SELF, CSP.UNSAFE_INLINE],
    # AJAX, WebSocket, EventSource connections
    "connect-src": [CSP.SELF],
}

if DEBUG:
    SECURE_CSP = _CSP_COMMON | {
        # unsafe-eval required by Vite HMR
        "script-src": [CSP.SELF, CSP.UNSAFE_EVAL],
        # unsafe-inline required by Vite injected styles
        "style-src": [CSP.SELF, CSP.UNSAFE_INLINE],
        # WebSocket connection for Vite HMR hot reload
        "connect-src": [CSP.SELF, "ws://localhost:5173"],
    }
    # Report-only uses the strict policy so dev console shows what prod will block
    SECURE_CSP_REPORT_ONLY = _CSP_STRICT
else:
    # Enforce the strict policy
    SECURE_CSP = _CSP_STRICT
    # Report-only mirrors enforced policy to catch regressions
    SECURE_CSP_REPORT_ONLY = _CSP_STRICT


# Logging
# https://docs.djangoproject.com/en/6.0/topics/logging/

# One JSON object per line. Every logger (django.*, allauth, ninja, ours)
# propagates to the root handler, which renders via the formatter from
# djangoapp.logging — so the whole process emits one uniform, jq-filterable
# NDJSON stream. See djangoapp/logging.py for the contract.
_LOG_LEVEL = "DEBUG" if DEBUG else "INFO"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {"()": json_formatter},
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": _LOG_LEVEL,
    },
    "loggers": {
        # django.server already logs every request; keep it (now JSON) at INFO.
        "django.server": {"level": _LOG_LEVEL},
        # Own the huey logger so `run_huey` never attaches ITS plain-text
        # handler:  NDJSON exactly once; propagate stays
        # False so the root handler doesn't double-print them.
        "huey": {"level": _LOG_LEVEL, "handlers": ["console"], "propagate": False},
    },
}

# Huey — Redis-backed background tasks + cron. Reuses REDIS_URL (shared with the
# client-error rate limiter, djangoapp/views/client_errors.py). `immediate` is
# False: enqueued tasks run via the consumer (`./run hueydev` / `./run dev`), and
# tests call the model classmethod or `task.call_local()` directly (no consumer).
# `utc: False` so crontab times are local TIME_ZONE.
HUEY = {
    "huey_class": "huey.RedisHuey",
    "name": "instant",
    "results": False,
    "store_none": False,
    "immediate": False,
    "utc": False,
    "connection": {"url": os.environ["REDIS_URL"]},
}
