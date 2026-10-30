from django.urls import path
from . import views

app_name = 'seo'

urlpatterns = [
    path('robots.txt', views.robots_txt, name='robots_txt'),
    path('sitemap.xml', views.sitemap_xml, name='sitemap_xml'),
    path('admin/seo-audit/', views.seo_audit_view, name='seo_audit'),
]
