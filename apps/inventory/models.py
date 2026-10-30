from django.db import models
from django.conf import settings
from apps.core.models import TimeStampedModel

class StockMovement(TimeStampedModel):
    """
    Log of all physical stock movements for variants (sales, cancellations, restocks).
    """
    REASON_CHOICES = (
        ('sale', 'Customer Order Placed'),
        ('cancellation', 'Order Cancelled (Restocked)'),
        ('return', 'Customer Return (Restocked)'),
        ('restock', 'Warehouse Restock'),
        ('manual', 'Manual Adjustment / Audit'),
    )

    variant = models.ForeignKey('catalog.ProductVariant', on_delete=models.CASCADE, related_name='stock_movements')
    quantity_change = models.IntegerField(help_text='Negative for deduction, positive for addition')
    balance_after = models.IntegerField(help_text='Stock balance immediately following this operation')
    reason = models.CharField(max_length=30, choices=REASON_CHOICES, default='sale')
    order_ref = models.CharField(max_length=100, blank=True, help_text='Associated order number e.g. BS-2026-000101')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    note = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.variant.sku} {self.quantity_change:+d} ({self.reason})"
