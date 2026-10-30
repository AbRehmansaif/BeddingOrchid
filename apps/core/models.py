from django.db import models
from django.core.cache import cache

class TimeStampedModel(models.Model):
    """Abstract model providing self-updating created_at and updated_at fields."""
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class SiteSettings(TimeStampedModel):
    """
    Singleton model to hold store-wide business settings, contact info,
    delivery rules, and marketing IDs.
    """
    store_name = models.CharField(max_length=100, default='BeddingOrchid')
    tagline = models.CharField(max_length=255, default='Luxury Bedding & Home Textiles — Crafted for Serene Sleep')
    phone = models.CharField(max_length=30, default='+92 300 1234567')
    whatsapp_number = models.CharField(max_length=30, default='923001234567', help_text='Numbers only with country code (e.g. 923001234567)')
    email = models.EmailField(default='orders@beddingorchid.com')
    address = models.TextField(default='Plot 45-B, Textile City, Industrial Area, Karachi, Pakistan')
    
    # Currency and shipping rules
    currency = models.CharField(max_length=10, default='PKR')
    currency_symbol = models.CharField(max_length=10, default='Rs.')
    default_shipping_fee = models.DecimalField(max_digits=10, decimal_places=2, default=250.00)
    free_shipping_threshold = models.DecimalField(max_digits=10, decimal_places=2, default=4000.00)
    default_cod_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    max_cod_amount = models.DecimalField(max_digits=10, decimal_places=2, default=50000.00)
    
    # Storefront announcements
    announcement_bar_text = models.CharField(max_length=255, default='✨ Free Delivery Nationwide on orders above Rs. 4,000 | Cash on Delivery Available')
    announcement_bar_link = models.CharField(max_length=255, blank=True, default='/collections/bed-sheets/')
    footer_about_text = models.TextField(default="BeddingOrchid is Pakistan's premier luxury bedding brand. We handcraft hotel-grade bed sheets, plush quilts, and luxury duvet covers using 100% combed cotton.")
    
    # Marketing & Tracking
    meta_pixel_id = models.CharField(max_length=50, blank=True, default='')
    meta_capi_access_token = models.TextField(blank=True, default='')
    meta_test_event_code = models.CharField(max_length=50, blank=True, default='')
    meta_domain_verification = models.CharField(max_length=100, blank=True, default='')
    ga4_id = models.CharField(max_length=50, blank=True, default='')
    google_site_verification = models.CharField(max_length=100, blank=True, default='')

    # Social links
    facebook_url = models.URLField(blank=True, default='https://facebook.com')
    instagram_url = models.URLField(blank=True, default='https://instagram.com')
    tiktok_url = models.URLField(blank=True, default='https://tiktok.com')

    class Meta:
        verbose_name = 'Site Settings'
        verbose_name_plural = 'Site Settings'

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)
        try:
            cache.set('site_settings_instance', self, timeout=86400)
        except Exception:
            pass

    @classmethod
    def get_settings(cls):
        try:
            cached = cache.get('site_settings_instance')
            if cached:
                return cached
        except Exception:
            pass
        instance, _ = cls.objects.get_or_create(pk=1)
        try:
            cache.set('site_settings_instance', instance, timeout=86400)
        except Exception:
            pass
        return instance

    def __str__(self):
        return f'{self.store_name} Settings'
