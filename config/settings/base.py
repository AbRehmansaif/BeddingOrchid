from pathlib import Path
import environ
import os

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env(
    DEBUG=(bool, False),
    SECRET_KEY=(str, 'django-insecure-bedding-store-default-key-production-replace'),
    ALLOWED_HOSTS=(list, ['*']),
    DATABASE_URL=(str, f'sqlite:///{BASE_DIR / "db.sqlite3"}'),
    REDIS_URL=(str, 'redis://127.0.0.1:6379/1'),
    CELERY_BROKER_URL=(str, 'redis://127.0.0.1:6379/0'),
    BRAND_NAME=(str, 'BeddingOrchid'),
    STORE_DOMAIN=(str, 'localhost:8000'),
    STORE_CURRENCY=(str, 'PKR'),
    DEFAULT_SHIPPING_FEE=(float, 250.00),
    FREE_SHIPPING_THRESHOLD=(float, 4000.00),
    DEFAULT_COD_FEE=(float, 0.00),
    META_PIXEL_ID=(str, ''),
    META_CAPI_ACCESS_TOKEN=(str, ''),
    META_TEST_EVENT_CODE=(str, ''),
    META_ADS_ACCESS_TOKEN=(str, ''),
    META_ADS_ACCOUNT_ID=(str, ''),
)

# Read .env file if present
env_file = BASE_DIR / '.env'
if env_file.exists():
    environ.Env.read_env(env_file)

SECRET_KEY = env('SECRET_KEY')
DEBUG = env('DEBUG')
ALLOWED_HOSTS = env('ALLOWED_HOSTS')

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sitemaps',

    # Third party
    'mptt',
    'import_export',
    'simple_history',

    # Store Apps
    'apps.core.apps.CoreConfig',
    'apps.accounts.apps.AccountsConfig',
    'apps.catalog.apps.CatalogConfig',
    'apps.inventory.apps.InventoryConfig',
    'apps.cart.apps.CartConfig',
    'apps.orders.apps.OrdersConfig',
    'apps.promotions.apps.PromotionsConfig',
    'apps.reviews.apps.ReviewsConfig',
    'apps.pages.apps.PagesConfig',
    'apps.seo.apps.SeoConfig',
    'apps.marketing.apps.MarketingConfig',
    'apps.notifications.apps.NotificationsConfig',

    # Finance & Profit Dashboard
    'apps.finance.apps.FinanceConfig',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    # Custom Middlewares
    'apps.core.middleware.TrackingMiddleware',
    'apps.seo.middleware.RedirectMiddleware',
    'simple_history.middleware.HistoryRequestMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'apps.core.context_processors.site_context',
                'apps.cart.context_processors.cart_context',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'
ASGI_APPLICATION = 'config.asgi.application'

DATABASES = {
    'default': env.db('DATABASE_URL', default=f'sqlite:///{BASE_DIR / "db.sqlite3"}')
}

AUTH_USER_MODEL = 'accounts.User'

AUTHENTICATION_BACKENDS = [
    'apps.accounts.backends.EmailOrPhoneModelBackend',
    'django.contrib.auth.backends.ModelBackend',
]

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', 'OPTIONS': {'min_length': 6}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Karachi'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Session Configuration
SESSION_ENGINE = 'django.contrib.sessions.backends.db'
SESSION_COOKIE_AGE = 1209600 # 2 weeks
SESSION_SAVE_EVERY_REQUEST = True

# Cache Configuration (falls back to local memory if redis is not running in dev)
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'unique-snowflake',
    }
}

# Celery Configuration
CELERY_BROKER_URL = env('CELERY_BROKER_URL')
CELERY_RESULT_BACKEND = env('REDIS_URL')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE

# Store Business Defaults
BRAND_NAME = env('BRAND_NAME')
STORE_DOMAIN = env('STORE_DOMAIN')
STORE_CURRENCY = env('STORE_CURRENCY')
DEFAULT_SHIPPING_FEE = env('DEFAULT_SHIPPING_FEE')
FREE_SHIPPING_THRESHOLD = env('FREE_SHIPPING_THRESHOLD')
DEFAULT_COD_FEE = env('DEFAULT_COD_FEE')

# Meta Tracking
META_PIXEL_ID = env('META_PIXEL_ID')
META_CAPI_ACCESS_TOKEN = env('META_CAPI_ACCESS_TOKEN')
META_TEST_EVENT_CODE = env('META_TEST_EVENT_CODE')

# Email
EMAIL_BACKEND = env('EMAIL_BACKEND', default='django.core.mail.backends.console.EmailBackend')
DEFAULT_FROM_EMAIL = env('DEFAULT_FROM_EMAIL', default='orders@beddingorchid.com')
LOGIN_URL = 'accounts:login'
LOGIN_REDIRECT_URL = 'accounts:profile'
LOGOUT_REDIRECT_URL = 'catalog:home'
