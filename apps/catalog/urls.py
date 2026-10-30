from django.urls import path
from . import views

app_name = 'catalog'

urlpatterns = [
    path('', views.home_view, name='home'),
    path('collections/<path:category_path>/', views.category_detail, name='category_detail'),
    path('products/<slug:slug>/', views.product_detail, name='product_detail'),
    path('search/', views.search_view, name='search'),
    path('api/variant-info/', views.variant_info_api, name='variant_info_api'),
]
