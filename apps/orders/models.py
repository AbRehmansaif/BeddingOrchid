import uuid
from decimal import Decimal
from django.db import models
from django.conf import settings
from django.utils import timezone
from apps.core.models import TimeStampedModel

class Order(TimeStampedModel):
    """
    Primary Order Model for COD & Home Textiles Delivery.
    All financial and item details are frozen snapshots at time of order creation.
    """
    STATUS_CHOICES = (
        ('pending', 'Pending Confirmation'),
        ('confirmed', 'Confirmed (Verified)'),
        ('processing', 'Processing / In Production'),
        ('packed', 'Packed / Ready for Dispatch'),
        ('dispatched', 'Dispatched / Out for Delivery'),
        ('delivered', 'Delivered (COD Collected)'),
        ('on_hold', 'On Hold'),
        ('cancelled', 'Cancelled'),
        ('returned', 'Returned to Seller'),
        ('refunded', 'Refunded / Exchanged'),
    )

    PAYMENT_METHOD_CHOICES = (
        ('COD', 'Cash on Delivery (COD)'),
        ('BANK', 'Direct Bank Transfer / IBFT'),
    )

    PAYMENT_STATUS_CHOICES = (
        ('pending', 'Payment Pending (COD)'),
        ('paid', 'Paid'),
        ('refunded', 'Refunded'),
    )

    # Identifiers
    order_number = models.CharField(max_length=50, unique=True, db_index=True)
    public_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='orders')

    # Snapshot of customer contact
    customer_name = models.CharField(max_length=150)
    customer_phone = models.CharField(max_length=30, db_index=True)
    customer_email = models.EmailField(blank=True)

    # Snapshot of shipping address (Editable in Admin when customer calls to update!)
    shipping_full_name = models.CharField(max_length=150)
    shipping_phone = models.CharField(max_length=30)
    shipping_address_line1 = models.CharField(max_length=255)
    shipping_address_line2 = models.CharField(max_length=255, blank=True)
    shipping_city = models.CharField(max_length=100, db_index=True)
    shipping_province = models.CharField(max_length=100, default='Punjab')
    shipping_postal_code = models.CharField(max_length=20, blank=True)
    shipping_country = models.CharField(max_length=100, default='Pakistan')
    shipping_landmark = models.CharField(max_length=255, blank=True)

    # Payment & Financials (Snapshots)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES, default='COD')
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='pending')
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    discount_total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    shipping_fee = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    cod_fee = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    grand_total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))

    # Promotion Snapshot
    coupon_code = models.CharField(max_length=50, blank=True)

    # Order Lifecycle & Status
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='pending', db_index=True)
    courier = models.CharField(max_length=50, blank=True, help_text='e.g. TCS, Trax, Leopards, PostEx, M&P')
    tracking_number = models.CharField(max_length=100, blank=True, db_index=True)
    tracking_url = models.URLField(blank=True, help_text='Direct URL to courier tracking portal')

    # Notes
    customer_note = models.TextField(blank=True, help_text='Special delivery instructions from buyer')
    admin_note = models.TextField(blank=True, verbose_name='Admin / Tracking Note', help_text='Status update or special note displayed to customer on the Track Order page')

    # Marketing Attribution & Audit Snapshots
    utm_source = models.CharField(max_length=100, blank=True)
    utm_medium = models.CharField(max_length=100, blank=True)
    utm_campaign = models.CharField(max_length=150, blank=True)
    utm_content = models.CharField(max_length=150, blank=True)
    utm_term = models.CharField(max_length=150, blank=True)
    fbp = models.CharField(max_length=100, blank=True)
    fbc = models.CharField(max_length=150, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)

    placed_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ['-placed_at']

    @property
    def total_items_count(self):
        return sum(item.quantity for item in self.items.all())

    @property
    def full_shipping_address(self):
        parts = [self.shipping_address_line1]
        if self.shipping_address_line2:
            parts.append(self.shipping_address_line2)
        if self.shipping_landmark:
            parts.append(f"Near: {self.shipping_landmark}")
        parts.append(self.shipping_city)
        if self.shipping_province:
            parts.append(self.shipping_province)
        return ", ".join(parts)

    def __str__(self):
        return f"{self.order_number} ({self.customer_name} - Rs. {self.grand_total:,.0f})"


class OrderItem(TimeStampedModel):
    """
    Immutable line item snapshot in an order.
    Even if the original product/variant is modified or deleted later,
    this record retains the exact name, size, color, price and SKU sold.
    """
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey('catalog.Product', on_delete=models.SET_NULL, null=True, blank=True)
    variant = models.ForeignKey('catalog.ProductVariant', on_delete=models.SET_NULL, null=True, blank=True)
    
    # Snapshots
    product_name = models.CharField(max_length=255)
    variant_sku = models.CharField(max_length=100)
    size_name = models.CharField(max_length=60, blank=True)
    color_name = models.CharField(max_length=60, blank=True)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    quantity = models.PositiveIntegerField(default=1)
    line_total = models.DecimalField(max_digits=12, decimal_places=2)
    image_url = models.CharField(max_length=500, blank=True)

    def __str__(self):
        return f"{self.quantity}x {self.product_name} ({self.size_name}/{self.color_name})"


class OrderStatusHistory(TimeStampedModel):
    """Audit log of status changes for an order."""
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='status_history')
    from_status = models.CharField(max_length=30)
    to_status = models.CharField(max_length=30)
    changed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    note = models.TextField(blank=True)
    notify_customer = models.BooleanField(default=True)

    class Meta:
        verbose_name_plural = 'Order Status Histories'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.order.order_number}: {self.from_status} -> {self.to_status}"
