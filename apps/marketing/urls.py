from django.urls import path
from . import views

app_name = 'marketing'

urlpatterns = [
    path('feeds/meta-catalog.xml', views.meta_catalog_feed_xml, name='meta_catalog_xml'),
    path('feeds/meta-catalog.csv', views.meta_catalog_feed_csv, name='meta_catalog_csv'),
    path('lp/<slug:slug>/', views.landing_page_view, name='landing_page'),
]
