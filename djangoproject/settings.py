"""Django settings for djangoproject project.

For more information on this file, see
https://docs.djangoproject.com/en/6.0/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/6.0/ref/settings/
"""

import os
from pathlib import Path

from django.utils.csp import CSP
from dotenv import load_dotenv

load_dotenv(override=True)

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/6.0/howto/deployment/checklist/

SECRET_KEY = os.environ["SECRET_KEY"]

DEBUG = os.environ["DEBUG"] == "True"

if not DEBUG and SECRET_KEY == "fake":  # noqa: S105
    msg = "Do not use `fake` secret key in production"
    raise ValueError(msg)

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
    "allauth.socialaccount.providers.google",
    "djangoapp",
    "ourapp",
    "inertia",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csp.ContentSecurityPolicyMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    # Shares the viewer profile + superuser flag on every Inertia page;
    # reads request.user, so it must run after AuthenticationMiddleware.
    "djangoapp.middleware.SharedPropsMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    # Allauth middleware
    "allauth.account.middleware.AccountMiddleware",
]

ROOT_URLCONF = "djangoproject.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
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
    },
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

LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/"

# Redirect URLs
# Google OAuth credentials live in the database, configured via:
#   ./run python manage.py addgoogleoauth <client_id> <secret>
# (no SOCIALACCOUNT_PROVIDERS block needed).

# Inertia settings
INERTIA_LAYOUT = "inertia/base.html"

# Content Security Policy
# https://docs.djangoproject.com/en/6.0/ref/csp/

_CSP_COMMON = {
    # Fallback for any directive not explicitly set
    "default-src": [CSP.SELF],
    # Block all plugins (Flash, Java applets, etc.)
    "object-src": [],
    # Images (data: covers base64-encoded images in rich text editors)
    "img-src": [CSP.SELF, "data:"],
    # Web fonts
    "font-src": [CSP.SELF],
    # Form submissions
    "form-action": [
        CSP.SELF,
        "https://accounts.google.com",  # For Google login
    ],
    # Who can embed this page in an iframe (clickjacking protection)
    "frame-ancestors": [CSP.SELF],
    # Restricts URLs that can be used in the <base> tag
    "base-uri": [CSP.SELF],
}

_CSP_STRICT = _CSP_COMMON | {
    # JavaScript sources
    "script-src": [CSP.SELF],
    # CSS sources
    "style-src": [CSP.SELF],
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
