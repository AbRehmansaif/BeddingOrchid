from decimal import Decimal
from django.db import models
from django.conf import settings
from apps.core.models import TimeStampedModel

class Review(TimeStampedModel):
    product = models.ForeignKey('catalog.Product', on_delete=models.CASCADE, related_name='reviews')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='reviews')
    rating = models.DecimalField(max_digits=2, decimal_places=1, default=Decimal('5.0'))
    title = models.CharField(max_length=150)
    comment = models.TextField()
    is_verified_buyer = models.BooleanField(default=True)
    is_approved = models.BooleanField(default=True, db_index=True)

    class Meta:
        ordering = ['-created_at']

    @property
    def stars_display(self):
        val = float(self.rating)
        full_stars = int(val)
        has_half = (val - full_stars) >= 0.25
        empty_stars = 5 - full_stars - (1 if has_half else 0)
        return ('★' * full_stars) + ('½' if has_half else '') + ('☆' * max(0, empty_stars))

    def __str__(self):
        return f"{self.rating}★ by {self.user} on {self.product.name}"
