from django.urls import path
from . import views

app_name = 'pages'

urlpatterns = [
    path('contact-us/', views.contact_us, name='contact'),
    path('faq/', views.faq_page, name='faq'),
    path('<slug:slug>/', views.page_detail, name='detail'),
]
