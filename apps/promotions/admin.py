from django.contrib import admin
from .models import SaleTag, FlashSale, Coupon, Banner

@admin.register(SaleTag)
class SaleTagAdmin(admin.ModelAdmin):
    list_display = ('label', 'background_color', 'position', 'priority')
    filter_horizontal = ('products', 'categories')
    search_fields = ('label',)


@admin.register(FlashSale)
class FlashSaleAdmin(admin.ModelAdmin):
    list_display = ('name', 'start_at', 'end_at', 'discount_type', 'discount_value', 'is_active', 'is_currently_running')
    filter_horizontal = ('products',)
    prepopulated_fields = {'slug': ('name',)}
    list_filter = ('is_active', 'discount_type')


@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = ('code', 'discount_type', 'value', 'min_order_amount', 'times_used', 'usage_limit', 'valid_until', 'is_active')
    list_filter = ('discount_type', 'is_active')
    search_fields = ('code',)


@admin.register(Banner)
class BannerAdmin(admin.ModelAdmin):
    list_display = ('title', 'badge_text', 'featured_product', 'button_text', 'sort_order', 'is_active')
    list_editable = ('sort_order', 'is_active')
    search_fields = ('title', 'subtitle', 'badge_text')
    autocomplete_fields = ('featured_product',)
    fieldsets = (
        ('Banner Headlines & SEO Copy', {
            'fields': ('title', 'subtitle', 'badge_text')
        }),
        ('Product Link & Call to Action (Manageable from Admin)', {
            'description': 'Select a specific product to feature, or set a custom button link.',
            'fields': ('featured_product', 'button_text', 'button_link')
        }),
        ('Hero Imagery', {
            'fields': ('image_desktop', 'image_mobile')
        }),
        ('Discount & Promo Offer (Manageable from Admin)', {
            'description': 'Text displayed in the discount bar directly below the hero image.',
            'fields': ('promo_discount_text',)
        }),
        ('Display & Ordering', {
            'fields': ('sort_order', 'is_active')
        }),
    )
