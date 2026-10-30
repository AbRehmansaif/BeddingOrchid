from .base import *

DEBUG = True

ALLOWED_HOSTS = ['*']

# In dev, static files can be served directly without manifest requirements
STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.StaticFilesStorage'
