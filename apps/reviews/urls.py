from django.urls import path
from . import views

app_name = 'reviews'

urlpatterns = [
    path('submit/<int:product_id>/', views.submit_review, name='submit'),
]
