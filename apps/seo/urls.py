from django.urls import path
from . import views

app_name = 'seo'

urlpatterns = [
    path('robots.txt', views.robots_txt, name='robots_txt'),
    path('sitemap.xml', views.sitemap_xml, name='sitemap_xml'),
    path('manifest.json', views.manifest_json, name='manifest_json'),
    path('sw.js', views.service_worker_js, name='service_worker_js'),
    path('admin/seo-audit/', views.seo_audit_view, name='seo_audit'),
]
