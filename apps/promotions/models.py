from django.db import models
from django.utils import timezone
from apps.core.models import TimeStampedModel
from decimal import Decimal

class SaleTag(TimeStampedModel):
    """
    Badge overlay for product card and gallery images.
    Admin can assign to products or categories.
    """
    POSITION_CHOICES = (
        ('top-left', 'Top Left'),
        ('top-right', 'Top Right'),
        ('bottom-left', 'Bottom Left'),
    )

    label = models.CharField(max_length=50, help_text='e.g. HOT SELLER, -35%, BESTSELLER, LUXURY PERCALE')
    background_color = models.CharField(max_length=20, default='#C25E38', help_text='Hex code e.g. #C25E38 (terracotta), #1E293B (navy)')
    text_color = models.CharField(max_length=20, default='#FFFFFF')
    position = models.CharField(max_length=20, choices=POSITION_CHOICES, default='top-left')
    priority = models.PositiveIntegerField(default=10, help_text='Higher number appears first')
    products = models.ManyToManyField('catalog.Product', blank=True, related_name='sale_tags')
    categories = models.ManyToManyField('catalog.Category', blank=True, related_name='sale_tags')

    class Meta:
        ordering = ['-priority', 'id']

    def __str__(self):
        return f"Badge: {self.label}"


class FlashSale(TimeStampedModel):
    """Timed flash sale event with countdown timer."""
    DISCOUNT_TYPES = (
        ('percent', 'Percentage (%)'),
        ('fixed', 'Fixed Amount (PKR)'),
    )

    name = models.CharField(max_length=150)
    slug = models.SlugField(max_length=160, unique=True)
    start_at = models.DateTimeField()
    end_at = models.DateTimeField()
    discount_type = models.CharField(max_length=20, choices=DISCOUNT_TYPES, default='percent')
    discount_value = models.DecimalField(max_digits=10, decimal_places=2, default=20.00)
    products = models.ManyToManyField('catalog.Product', blank=True, related_name='flash_sales')
    banner_image = models.ImageField(upload_to='promotions/flash_sales/', blank=True, null=True)
    is_active = models.BooleanField(default=True)

    @property
    def is_currently_running(self):
        now = timezone.now()
        return self.is_active and self.start_at <= now <= self.end_at

    def __str__(self):
        return self.name


class Coupon(TimeStampedModel):
    """Discount coupon code applicable at checkout."""
    DISCOUNT_TYPES = (
        ('percentage', 'Percentage Discount'),
        ('fixed', 'Fixed PKR Amount'),
    )

    code = models.CharField(max_length=30, unique=True, db_index=True)
    discount_type = models.CharField(max_length=20, choices=DISCOUNT_TYPES, default='percentage')
    value = models.DecimalField(max_digits=10, decimal_places=2, help_text='Percentage e.g. 10.00 or amount e.g. 500.00')
    min_order_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    max_discount_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    usage_limit = models.PositiveIntegerField(null=True, blank=True, help_text='Total usage count limit across all users')
    times_used = models.PositiveIntegerField(default=0)
    valid_from = models.DateTimeField(default=timezone.now)
    valid_until = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    def is_valid_for(self, subtotal: Decimal):
        now = timezone.now()
        if not self.is_active:
            return False, "This coupon is currently inactive."
        if self.valid_from and now < self.valid_from:
            return False, "This coupon has not started yet."
        if self.valid_until and now > self.valid_until:
            return False, "This coupon has expired."
        if self.usage_limit and self.times_used >= self.usage_limit:
            return False, "This coupon usage limit has been reached."
        if subtotal < self.min_order_amount:
            return False, f"Minimum order amount for this coupon is Rs. {self.min_order_amount:,.0f}."
        return True, "Coupon is valid."

    def calculate_discount(self, subtotal: Decimal) -> Decimal:
        if self.discount_type == 'percentage':
            disc = (subtotal * self.value) / Decimal('100.00')
        else:
            disc = self.value

        if self.max_discount_amount and disc > self.max_discount_amount:
            disc = self.max_discount_amount

        return min(disc, subtotal)

    def __str__(self):
        return f"{self.code} ({self.value}{'%' if self.discount_type == 'percentage' else ' PKR'})"


class Banner(TimeStampedModel):
    """Hero slide and storefront promotional banners."""
    title = models.CharField(max_length=150, help_text='Main headline e.g. Export-Quality Hotel Bedding')
    subtitle = models.TextField(help_text='SEO & value subheading e.g. Precision-woven by Twiltex...')
    badge_text = models.CharField(max_length=80, blank=True, default='EXPORT QUALITY • SINCE 2004', help_text='Seasonal or promotional pill e.g. 2026 Summer Collection (editable anytime)')
    featured_product = models.ForeignKey(
        'catalog.Product',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='hero_banners',
        help_text='Select a product to feature in the hero button and card'
    )
    button_text = models.CharField(max_length=50, default='Shop Bed Sheets')
    button_link = models.CharField(max_length=255, blank=True, default='/collections/bed-sheets/', help_text='Custom link (used if no featured product is chosen)')
    image_desktop = models.ImageField(upload_to='banners/', help_text='High res banner 1920x800 px')
    image_mobile = models.ImageField(upload_to='banners/mobile/', blank=True, null=True, help_text='Mobile crop 800x1000 px')
    promo_discount_text = models.CharField(
        max_length=160,
        blank=True,
        default='⚡ Flat 10% OFF first order: WELCOME10 | Direct Manufacturer Pricing',
        help_text='Discount bar displayed under the hero image (editable anytime from admin)'
    )
    sort_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['sort_order', 'id']

    def __str__(self):
        return self.title

    @property
    def effective_button_link(self):
        if self.featured_product:
            return self.featured_product.get_absolute_url()
        return self.button_link or '/collections/bed-sheets/'

