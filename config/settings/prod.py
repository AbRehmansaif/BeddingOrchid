from .base import *

DEBUG = False

# Production Allowed Hosts
ALLOWED_HOSTS = env.list(
    'ALLOWED_HOSTS',
    default=[
        'beddingorchid.com',
        'www.beddingorchid.com',
        '127.0.0.1',
        'localhost',
    ]
)

# PostgreSQL Database Configuration for Production
# Out-of-the-box pre-configured with dedicated user & database on VPS
DATABASES = {
    'default': env.db(
        'DATABASE_URL',
        default='postgres://beddingorchid_user:YourStrongSecretPassword123!@localhost:5432/beddingorchid_db'
    )
}
DATABASES['default']['CONN_MAX_AGE'] = env.int('DB_CONN_MAX_AGE', default=600)

# CSRF Trusted Origins (Mandatory for Django 4.0+ HTTPS behind Nginx reverse proxy)
CSRF_TRUSTED_ORIGINS = env.list(
    'CSRF_TRUSTED_ORIGINS',
    default=[
        'https://beddingorchid.com',
        'https://www.beddingorchid.com',
    ]
)

# SSL & Reverse Proxy headers
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_SSL_REDIRECT = env.bool('SECURE_SSL_REDIRECT', default=True)
SESSION_COOKIE_SECURE = env.bool('SESSION_COOKIE_SECURE', default=True)
CSRF_COOKIE_SECURE = env.bool('CSRF_COOKIE_SECURE', default=True)
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# Redis Cache for Production (Isolated with unique key prefix for multi-site VPS)
if env('REDIS_URL', default=None):
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.redis.RedisCache',
            'LOCATION': env('REDIS_URL'),
            'KEY_PREFIX': 'beddingorchid',
            'TIMEOUT': 86400,
        }
    }

# Production Logging (Outputs to console for systemd journalctl capture)
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '[{asctime}] {levelname} [{name}:{lineno}] {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'django.security': {
            'handlers': ['console'],
            'level': 'WARNING',
            'propagate': False,
        },
    },
}
