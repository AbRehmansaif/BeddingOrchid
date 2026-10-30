from decimal import Decimal
from django.contrib import admin, messages
from django.urls import path, reverse
from django.shortcuts import get_object_or_404, redirect
from django.utils.html import format_html
from mptt.admin import DraggableMPTTAdmin
from .models import Category, Size, Color, Tag, Product, ProductImage, ProductVariant, QuantityDiscount

@admin.register(Category)
class CategoryAdmin(DraggableMPTTAdmin):
    list_display = ('tree_actions', 'indented_title', 'slug', 'is_active', 'show_in_menu', 'show_on_home', 'sort_order')
    list_display_links = ('indented_title',)
    list_editable = ('is_active', 'show_in_menu', 'show_on_home', 'sort_order')
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ('name', 'description')
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'slug', 'parent', 'description', 'image', 'banner_image')
        }),
        ('Visibility & Hierarchy', {
            'fields': ('is_active', 'show_in_menu', 'show_on_home', 'sort_order')
        }),
        ('SEO Metadata', {
            'classes': ('collapse',),
            'fields': ('meta_title', 'meta_description', 'canonical_url')
        }),
    )


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1
    fields = ('image', 'image_preview', 'alt_text', 'is_primary', 'sort_order')
    readonly_fields = ('image_preview',)

    def image_preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" style="width: 50px; height: 50px; object-fit: cover; border-radius: 4px;" />', obj.image.url)
        return "-"
    image_preview.short_description = "Preview"


class ProductVariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 1
    fields = ('size', 'color', 'sku', 'price', 'compare_at_price', 'stock_quantity', 'image', 'is_active', 'weight_grams')
    show_change_link = True

    def get_fields(self, request, obj=None):
        fields = list(super().get_fields(request, obj))
        if request.user.has_perm('finance.view_dashboard'):
            if 'last_cost_display' not in fields:
                fields.extend(['last_cost_display', 'margin_display'])
        return fields

    def get_readonly_fields(self, request, obj=None):
        ro = list(super().get_readonly_fields(request, obj))
        if request.user.has_perm('finance.view_dashboard'):
            ro.extend(['last_cost_display', 'margin_display'])
        return ro

    def last_cost_display(self, obj):
        if not obj or not obj.pk:
            return "-"
        try:
            from apps.finance.models import VariantCost
            vc = VariantCost.objects.filter(variant=obj).order_by('-effective_from').first()
            if not vc:
                return format_html('<span style="color:#EF4444; font-weight:600; font-size:11px;">⚠️ No Cost Set</span>')
            total = vc.unit_cost + vc.packaging_cost + vc.other_unit_cost
            return format_html('Rs. {:,.2f}', total)
        except Exception:
            return "-"
    last_cost_display.short_description = "Unit Cost"

    def margin_display(self, obj):
        if not obj or not obj.pk:
            return "-"
        try:
            from apps.finance.models import VariantCost, FinanceSettings
            vc = VariantCost.objects.filter(variant=obj).order_by('-effective_from').first()
            if not vc:
                return "-"
            total = vc.unit_cost + vc.packaging_cost + vc.other_unit_cost
            price = obj.price or Decimal('0.00')
            if not price or price <= 0:
                return "-"
            margin_pct = ((price - total) / price) * 100
            fs = FinanceSettings.get_settings()
            min_margin = fs.min_margin_percent_alert or Decimal('20.00')

            if margin_pct < min_margin:
                return format_html(
                    '<span style="background:#EF4444; color:white; padding:2px 6px; border-radius:4px; font-weight:700; font-size:11px;">⚠️ {:,.1f}% (Low)</span>',
                    margin_pct
                )
            return format_html('<span style="color:#10B981; font-weight:700; font-size:11px;">{:,.1f}%</span>', margin_pct)
        except Exception:
            return "-"
    margin_display.short_description = "Margin %"

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "image":
            object_id = request.resolver_match.kwargs.get('object_id') if request.resolver_match else None
            if object_id:
                kwargs["queryset"] = ProductImage.objects.filter(product_id=object_id)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


class QuantityDiscountInline(admin.TabularInline):
    model = QuantityDiscount
    extra = 0


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'category', 'available_sizes_display', 'base_price_display', 'compare_at_price_display',
        'stock_status', 'is_active', 'is_featured', 'is_best_seller', 'is_new', 'created_at'
    )
    list_filter = ('is_active', 'is_featured', 'is_best_seller', 'is_new', 'category', 'tags')
    search_fields = ('name', 'slug', 'sku_prefix', 'description', 'material')
    prepopulated_fields = {'slug': ('name',)}
    filter_horizontal = ('additional_categories', 'tags')
    readonly_fields = ('quick_actions',)
    inlines = [ProductImageInline, ProductVariantInline, QuantityDiscountInline]
    actions = ['make_active', 'make_inactive', 'mark_as_featured', 'generate_default_variants']

    fieldsets = (
        ('Bed Sizes & Quick Generator', {
            'description': 'Click the button below to auto-generate King, Super King, Queen, and Single variants, or customize them in the Product variants table below.',
            'fields': ('quick_actions',)
        }),
        ('General Details', {
            'fields': ('name', 'slug', 'sku_prefix', 'category', 'additional_categories', 'tags')
        }),
        ('Textile & Bedding Specifications', {
            'fields': ('material', 'thread_count', 'pieces_included', 'care_instructions', 'warranty_days')
        }),
        ('Pricing & Availability', {
            'fields': ('base_price', 'compare_at_price', 'is_active', 'cod_available', 'is_featured', 'is_best_seller', 'is_new')
        }),
        ('Descriptions', {
            'fields': ('short_description', 'description')
        }),
        ('SEO Fields', {
            'classes': ('collapse',),
            'fields': ('meta_title', 'meta_description', 'og_image')
        }),
    )

    def available_sizes_display(self, obj):
        sizes = list(obj.variants.filter(is_active=True).values_list('size__name', flat=True).distinct())
        if sizes:
            return format_html('<span style="color: #1E293B; font-weight: 600;">{}</span>', ", ".join(sizes))
        return format_html('<span style="color: #EF4444; font-weight: 600;">No sizes (Click to generate)</span>')
    available_sizes_display.short_description = "Bed Sizes"

    def quick_actions(self, obj):
        if obj and obj.pk:
            url = reverse('admin:catalog_product_generate_sizes', args=[obj.pk])
            sizes = list(obj.variants.filter(is_active=True).values_list('size__name', flat=True).distinct())
            curr_sizes_str = f"Current sizes: <strong>{', '.join(sizes)}</strong>" if sizes else "<span style='color: #EF4444;'>No variants yet</span>"
            return format_html(
                '<div style="background: #F8FAFC; border: 1px solid #CBD5E1; padding: 14px 18px; border-radius: 12px; margin-bottom: 8px;">'
                '<p style="margin: 0 0 10px 0; font-size: 13px; color: #334155;">{}</p>'
                '<a class="button" style="background: #1E293B; color: #FFFFFF; padding: 9px 18px; border-radius: 8px; font-weight: bold; text-decoration: none; font-size: 12px; display: inline-block;" href="{}">⚡ Auto-Generate Bed Sizes (King, Queen, Single, Super King)</a>'
                '<p style="color: #64748B; font-size: 11px; margin: 8px 0 0 0;">Generates standard size variants for all active colors with accurate pricing and stock. You can also scroll down to <strong>Product variants</strong> to add custom sizes.</p>'
                '</div>',
                format_html(curr_sizes_str),
                url
            )
        return "Save product first to generate variants."
    quick_actions.short_description = "Bed Sizes Quick Setup"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('<path:object_id>/generate-sizes/', self.admin_site.admin_view(self.generate_sizes_view), name='catalog_product_generate_sizes'),
        ]
        return custom_urls + urls

    def generate_sizes_view(self, request, object_id):
        product = get_object_or_404(Product, pk=object_id)
        sizes = list(Size.objects.filter(name__in=['King', 'Super King', 'Queen', 'Single']))
        colors = list(Color.objects.all()[:3])
        count = 0
        for s in sizes:
            for c in colors:
                sku = f"BTX-P{product.id}-S{s.id}-C{c.id}"
                p_diff = Decimal('0.00')
                if s.name == 'Single':
                    p_diff = -Decimal('500.00')
                elif s.name == 'Super King':
                    p_diff = Decimal('500.00')
                elif s.name == 'Queen':
                    p_diff = -Decimal('200.00')
                v_price = max(Decimal('500.00'), product.base_price + p_diff)
                _, created = ProductVariant.objects.get_or_create(
                    product=product, size=s, color=c,
                    defaults={'sku': sku, 'stock_quantity': 35, 'price': v_price, 'compare_at_price': product.compare_at_price}
                )
                if created:
                    count += 1
        messages.success(request, f"Generated {count} size variants (King, Queen, Single, Super King) for '{product.name}'!")
        return redirect('admin:catalog_product_change', object_id)

    def base_price_display(self, obj):
        return f"Rs. {obj.base_price:,.0f}"
    base_price_display.short_description = "Price"

    def compare_at_price_display(self, obj):
        if obj.compare_at_price:
            formatted = f"{float(obj.compare_at_price):,.0f}"
            return format_html('<span style="text-decoration: line-through; color: #9CA3AF;">Rs. {}</span>', formatted)
        return "-"
    compare_at_price_display.short_description = "Compare At"

    def stock_status(self, obj):
        if obj.in_stock:
            return format_html('<span style="color: #10B981; font-weight: 600;">In Stock</span>')
        return format_html('<span style="color: #EF4444; font-weight: 600;">Out of Stock</span>')
    stock_status.short_description = "Stock"

    def make_active(self, request, queryset):
        queryset.update(is_active=True)
    make_active.short_description = "Activate selected products"

    def make_inactive(self, request, queryset):
        queryset.update(is_active=False)
    make_inactive.short_description = "Deactivate selected products"

    def mark_as_featured(self, request, queryset):
        queryset.update(is_featured=True)
    mark_as_featured.short_description = "Mark as Featured"

    def generate_default_variants(self, request, queryset):
        """Action to generate King, Queen, Single variants automatically."""
        sizes = Size.objects.all()[:4]
        colors = Color.objects.all()[:3]
        count = 0
        for p in queryset:
            for s in sizes:
                for c in colors:
                    sku = f"{p.sku_prefix or p.slug[:4].upper()}-{s.name[:2].upper()}-{c.name[:2].upper()}"
                    _, created = ProductVariant.objects.get_or_create(
                        product=p, size=s, color=c,
                        defaults={'sku': sku, 'stock_quantity': 25, 'price': p.base_price}
                    )
                    if created:
                        count += 1
        self.message_user(request, f"Generated {count} variants across selected products.")
    generate_default_variants.short_description = "Bulk generate standard variants (Size x Color)"


@admin.register(Size)
class SizeAdmin(admin.ModelAdmin):
    list_display = ('name', 'dimensions', 'sort_order')
    list_editable = ('sort_order',)


@admin.register(Color)
class ColorAdmin(admin.ModelAdmin):
    list_display = ('name', 'hex_code', 'color_preview')

    def color_preview(self, obj):
        return format_html(
            '<div style="width: 28px; height: 28px; border-radius: 50%; background-color: {}; border: 1px solid #ccc;"></div>',
            obj.hex_code
        )
    color_preview.short_description = "Swatch"


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}


@admin.register(ProductVariant)
class ProductVariantAdmin(admin.ModelAdmin):
    list_display = ('sku', 'product', 'size', 'color', 'price', 'stock_quantity', 'image', 'is_active')
    list_filter = ('is_active', 'size', 'color')
    search_fields = ('sku', 'product__name')

    def get_list_display(self, request):
        base = list(super().get_list_display(request))
        if request.user.has_perm('finance.view_dashboard'):
            return base[:5] + ['last_cost_display', 'margin_display'] + base[5:]
        return base

    def last_cost_display(self, obj):
        if not obj or not obj.pk:
            return "-"
        try:
            from apps.finance.models import VariantCost
            vc = VariantCost.objects.filter(variant=obj).order_by('-effective_from').first()
            if not vc:
                return format_html('<span style="color:#EF4444; font-weight:600; font-size:11px;">⚠️ No Cost Set</span>')
            total = vc.unit_cost + vc.packaging_cost + vc.other_unit_cost
            return format_html('Rs. {:,.2f}', total)
        except Exception:
            return "-"
    last_cost_display.short_description = "Unit Cost"

    def margin_display(self, obj):
        if not obj or not obj.pk:
            return "-"
        try:
            from apps.finance.models import VariantCost, FinanceSettings
            vc = VariantCost.objects.filter(variant=obj).order_by('-effective_from').first()
            if not vc:
                return "-"
            total = vc.unit_cost + vc.packaging_cost + vc.other_unit_cost
            price = obj.price or Decimal('0.00')
            if not price or price <= 0:
                return "-"
            margin_pct = ((price - total) / price) * 100
            fs = FinanceSettings.get_settings()
            min_margin = fs.min_margin_percent_alert or Decimal('20.00')

            if margin_pct < min_margin:
                return format_html(
                    '<span style="background:#EF4444; color:white; padding:2px 6px; border-radius:4px; font-weight:700; font-size:11px;">⚠️ {:,.1f}%</span>',
                    margin_pct
                )
            return format_html('<span style="color:#10B981; font-weight:700; font-size:11px;">{:,.1f}%</span>', margin_pct)
        except Exception:
            return "-"
    margin_display.short_description = "Margin %"
