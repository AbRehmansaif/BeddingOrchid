from django.db import models
from django.conf import settings
from apps.core.models import TimeStampedModel
from apps.catalog.models import ProductVariant

class Cart(TimeStampedModel):
    """Database backed shopping cart for logged-in or identified customers."""
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True, related_name='cart')
    session_key = models.CharField(max_length=40, null=True, blank=True, db_index=True)

    def __str__(self):
        return f"Cart ({self.user or self.session_key})"


class CartItem(TimeStampedModel):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')
    variant = models.ForeignKey(ProductVariant, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)

    class Meta:
        unique_together = ('cart', 'variant')

    @property
    def line_total(self):
        return self.variant.effective_price * self.quantity

    def __str__(self):
        return f"{self.quantity}x {self.variant}"
