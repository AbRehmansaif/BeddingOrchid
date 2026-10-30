from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

# Customize Admin Site Headers
admin.site.site_header = "BeddingOrchid Admin"
admin.site.site_title = "BeddingOrchid Management"
admin.site.index_title = "BeddingOrchid Operations & Catalog"

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # Storefront Core & Products
    path('', include('apps.catalog.urls')),
    
    # Cart & Checkout
    path('cart/', include('apps.cart.urls')),
    path('', include('apps.orders.urls')),
    
    # Customer Accounts
    path('account/', include('apps.accounts.urls')),
    
    # Reviews
    path('reviews/', include('apps.reviews.urls')),
    
    # Marketing, Meta feeds, and Landing pages
    path('', include('apps.marketing.urls')),
    
    # SEO, Sitemaps, Robots
    path('', include('apps.seo.urls')),
    
    # Informational & Policy Pages
    path('pages/', include('apps.pages.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
