from django.db.models import Q
from .models import Product, Category, Size, Color

class CatalogService:
    @staticmethod
    def get_filtered_products(category=None, query=None, size_id=None, color_id=None, min_price=None, max_price=None, sort_by=None, on_sale=False):
        qs = Product.objects.filter(is_active=True).select_related('category').prefetch_related('images', 'variants', 'sale_tags')

        if category:
            descendant_cats = category.get_descendants(include_self=True)
            qs = qs.filter(Q(category__in=descendant_cats) | Q(additional_categories__in=descendant_cats)).distinct()

        if query:
            qs = qs.filter(
                Q(name__icontains=query) |
                Q(material__icontains=query) |
                Q(short_description__icontains=query) |
                Q(description__icontains=query) |
                Q(tags__name__icontains=query)
            ).distinct()

        if size_id:
            qs = qs.filter(variants__size_id=size_id, variants__stock_quantity__gt=0).distinct()

        if color_id:
            qs = qs.filter(variants__color_id=color_id, variants__stock_quantity__gt=0).distinct()

        if min_price:
            qs = qs.filter(base_price__gte=min_price)

        if max_price:
            qs = qs.filter(base_price__lte=max_price)

        if on_sale:
            qs = qs.filter(compare_at_price__gt=models.F('base_price'))

        # Sorting
        if sort_by == 'price_asc':
            qs = qs.order_by('base_price')
        elif sort_by == 'price_desc':
            qs = qs.order_by('-base_price')
        elif sort_by == 'best_sellers':
            qs = qs.order_by('-is_best_seller', '-created_at')
        elif sort_by == 'newest':
            qs = qs.order_by('-created_at')
        else:
            qs = qs.order_by('-is_featured', '-is_best_seller', '-created_at')

        return qs
