from django.contrib import admin
from .models import SiteSettings

@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    fieldsets = (
        ('Store Identity & Contact', {
            'fields': ('store_name', 'tagline', 'phone', 'whatsapp_number', 'email', 'address')
        }),
        ('Shipping & COD Rules', {
            'fields': ('currency', 'currency_symbol', 'default_shipping_fee', 'free_shipping_threshold', 'default_cod_fee', 'max_cod_amount')
        }),
        ('Storefront Banners & Text', {
            'fields': ('announcement_bar_text', 'announcement_bar_link', 'footer_about_text')
        }),
        ('Marketing & Analytics Tracking', {
            'fields': ('meta_pixel_id', 'meta_capi_access_token', 'meta_test_event_code', 'meta_domain_verification', 'ga4_id', 'google_site_verification')
        }),
        ('Social Links', {
            'fields': ('facebook_url', 'instagram_url', 'tiktok_url')
        }),
    )

    def has_add_permission(self, request):
        return not SiteSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False
