from django.shortcuts import render, get_object_or_404
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.db.models import Prefetch
from django.db import models
from .models import Category, Product, ProductVariant, Size, Color, QuantityDiscount
from .services import CatalogService
from apps.promotions.models import Banner, FlashSale
from apps.reviews.models import Review

def home_view(request):
    banners = Banner.objects.filter(is_active=True).order_by('sort_order')
    categories = Category.objects.filter(is_active=True, show_on_home=True, parent__isnull=True).order_by('sort_order')[:8]
    best_sellers = Product.objects.filter(is_active=True, is_best_seller=True).prefetch_related('images', 'variants', 'sale_tags')[:8]
    new_arrivals = Product.objects.filter(is_active=True, is_new=True).prefetch_related('images', 'variants', 'sale_tags')[:8]
    flash_sales = FlashSale.objects.filter(is_active=True).prefetch_related('products__images')[:1]
    recent_reviews = Review.objects.filter(is_approved=True).select_related('product', 'user')[:6]

    context = {
        'banners': banners,
        'categories': categories,
        'best_sellers': best_sellers,
        'new_arrivals': new_arrivals,
        'flash_sale': flash_sales.first() if flash_sales.exists() else None,
        'reviews': recent_reviews,
    }
    return render(request, 'home.html', context)


def category_detail(request, category_path):
    slugs = category_path.strip('/').split('/')
    leaf_slug = slugs[-1]
    category = get_object_or_404(Category, slug=leaf_slug, is_active=True)

    # Filter params
    size_id = request.GET.get('size')
    color_id = request.GET.get('color')
    min_price = request.GET.get('min_price')
    max_price = request.GET.get('max_price')
    sort_by = request.GET.get('sort', 'featured')

    products_qs = CatalogService.get_filtered_products(
        category=category,
        size_id=size_id,
        color_id=color_id,
        min_price=min_price,
        max_price=max_price,
        sort_by=sort_by
    )

    paginator = Paginator(products_qs, 12)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    # Filter options
    all_sizes = Size.objects.all()
    all_colors = Color.objects.all()
    subcategories = category.get_children().filter(is_active=True)

    context = {
        'category': category,
        'subcategories': subcategories,
        'products': page_obj,
        'all_sizes': all_sizes,
        'all_colors': all_colors,
        'current_sort': sort_by,
        'current_size': size_id,
        'current_color': color_id,
        'total_count': paginator.count,
    }
    return render(request, 'catalog/category_detail.html', context)


def product_detail(request, slug):
    product = get_object_or_404(
        Product.objects.prefetch_related(
            'images',
            Prefetch('variants', queryset=ProductVariant.objects.filter(is_active=True).select_related('size', 'color', 'image')),
            'quantity_discounts'
        ),
        slug=slug,
        is_active=True
    )

    # Related products
    related_products = Product.objects.filter(
        category=product.category, is_active=True
    ).exclude(id=product.id).prefetch_related('images', 'variants', 'sale_tags')[:4]

    # Collect available sizes and colors for this product
    active_variants = product.variants.all()
    available_sizes = {v.size for v in active_variants if v.size}
    available_colors = {v.color for v in active_variants if v.color}

    # Default variant
    default_variant = active_variants.first()

    # Product reviews
    reviews = product.reviews.filter(is_approved=True).select_related('user').order_by('-created_at')

    # Quantity / bulk savings discounts
    quantity_discounts = list(product.quantity_discounts.all().order_by('min_quantity'))
    if not quantity_discounts:
        quantity_discounts = list(QuantityDiscount.objects.filter(product__isnull=True).order_by('min_quantity'))

    context = {
        'product': product,
        'default_variant': default_variant,
        'available_sizes': sorted(list(available_sizes), key=lambda s: s.sort_order),
        'available_colors': sorted(list(available_colors), key=lambda c: c.name),
        'variants': active_variants,
        'quantity_discounts': quantity_discounts,
        'related_products': related_products,
        'reviews': reviews,
    }
    return render(request, 'catalog/product_detail.html', context)


def search_view(request):
    query = request.GET.get('q', '').strip()
    products_qs = CatalogService.get_filtered_products(query=query) if query else Product.objects.none()

    paginator = Paginator(products_qs, 16)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    context = {
        'query': query,
        'products': page_obj,
        'total_count': paginator.count,
    }
    return render(request, 'catalog/search.html', context)


def variant_info_api(request):
    """AJAX API endpoint returning variant SKU, price, compare price, image, and stock for selected options."""
    product_id = request.GET.get('product_id')
    size_id = request.GET.get('size_id')
    color_id = request.GET.get('color_id')

    qs = ProductVariant.objects.filter(product_id=product_id, is_active=True).select_related('image')
    if size_id:
        qs = qs.filter(size_id=size_id)
    if color_id:
        qs = qs.filter(color_id=color_id)

    variant = qs.first()
    if not variant:
        return JsonResponse({'success': False, 'message': 'Selected combination is currently unavailable.'}, status=404)

    image_url = None
    if variant.image and variant.image.image:
        image_url = variant.image.image.url

    return JsonResponse({
        'success': True,
        'variant_id': variant.id,
        'sku': variant.sku,
        'price': float(variant.effective_price),
        'compare_at_price': float(variant.effective_compare_at_price) if variant.effective_compare_at_price else None,
        'discount_percent': variant.discount_percent,
        'stock_quantity': variant.stock_quantity,
        'in_stock': variant.is_in_stock,
        'image_url': image_url,
    })
