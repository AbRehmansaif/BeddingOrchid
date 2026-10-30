from django.urls import path
from . import views

app_name = 'orders'

urlpatterns = [
    path('checkout/', views.checkout_view, name='checkout'),
    path('buy-now/', views.buy_now, name='buy_now'),
    path('thank-you/<uuid:public_id>/', views.thank_you, name='thank_you'),
    path('track-order/', views.track_order, name='track_order'),
    path('invoice/<str:order_number>/', views.admin_invoice, name='admin_invoice'),
    path('invoices/bulk/', views.admin_bulk_invoices, name='admin_bulk_invoices'),
    path('admin-status/<str:order_number>/<str:new_status>/', views.admin_invoice, name='admin_change_status'),
]
