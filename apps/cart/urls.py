from django.urls import path
from . import views

app_name = 'cart'

urlpatterns = [
    path('', views.cart_detail, name='detail'),
    path('add/', views.cart_add, name='add'),
    path('update/', views.cart_update, name='update'),
    path('remove/', views.cart_remove, name='remove'),
    path('coupon/apply/', views.apply_coupon, name='apply_coupon'),
    path('coupon/remove/', views.remove_coupon, name='remove_coupon'),
    path('drawer/', views.mini_cart_drawer, name='drawer'),
]
