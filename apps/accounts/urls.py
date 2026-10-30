from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),
    path('logout/', views.logout_view, name='logout'),
    path('', views.profile_overview, name='profile'),
    path('orders/', views.my_orders, name='orders'),
    path('orders/<str:order_number>/', views.order_detail, name='order_detail'),
    path('addresses/', views.addresses_list, name='addresses'),
    path('addresses/create/', views.address_create, name='address_create'),
    path('addresses/<int:address_id>/edit/', views.address_edit, name='address_edit'),
    path('addresses/<int:address_id>/delete/', views.address_delete, name='address_delete'),
    path('addresses/<int:address_id>/set-default/', views.address_set_default, name='address_set_default'),
    path('wishlist/', views.wishlist_view, name='wishlist'),
    path('wishlist/toggle/', views.wishlist_toggle_ajax, name='wishlist_toggle'),
]
