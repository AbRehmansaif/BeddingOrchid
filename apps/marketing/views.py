import csv
from django.http import HttpResponse
from django.shortcuts import render, get_object_or_404
from apps.catalog.models import ProductVariant, Product

def meta_catalog_feed_xml(request):
    """
    Generates Meta Commerce Manager / Dynamic Product Ads XML Product Feed.
    Content ID matches variant SKU or product ID used in Meta Pixel events.
    """
    domain = request.get_host()
    protocol = "https" if request.is_secure() else "http"
    base_url = f"{protocol}://{domain}"

    variants = ProductVariant.objects.filter(is_active=True, product__is_active=True).select_related(
        'product', 'product__category', 'size', 'color', 'image'
    )

    context = {
        'base_url': base_url,
        'variants': variants,
    }
    return render(request, 'marketing/meta_catalog_feed.xml', context, content_type='application/xml')


def meta_catalog_feed_csv(request):
    """
    Generates Meta Commerce Manager CSV Product Feed.
    """
    domain = request.get_host()
    protocol = "https" if request.is_secure() else "http"
    base_url = f"{protocol}://{domain}"

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="meta_catalog_feed.csv"'

    writer = csv.writer(response)
    writer.writerow([
        'id', 'title', 'description', 'availability', 'condition', 'price',
        'link', 'image_link', 'brand', 'google_product_category', 'product_type',
        'item_group_id', 'color', 'size', 'material'
    ])

    variants = ProductVariant.objects.filter(is_active=True, product__is_active=True).select_related(
        'product', 'product__category', 'size', 'color', 'image'
    )

    for v in variants:
        img_url = ""
        if v.image and v.image.image:
            img_url = f"{base_url}{v.image.image.url}"
        elif v.product.primary_image:
            img_url = f"{base_url}{v.product.primary_image.image.url}"

        writer.writerow([
            v.sku,
            f"{v.product.name} - {v.size.name if v.size else ''} {v.color.name if v.color else ''}".strip(),
            v.product.short_description or v.product.description[:200],
            'in stock' if v.is_in_stock else 'out of stock',
            'new',
            f"{float(v.effective_price):.2f} PKR",
            f"{base_url}{v.product.get_absolute_url()}?variant={v.sku}",
            img_url,
            'BeddingOrchid',
            'Home & Garden > Linens & Bedding > Bedding',
            v.product.category.name,
            v.product.slug,
            v.color.name if v.color else '',
            v.size.name if v.size else '',
            v.product.material
        ])

    return response


def landing_page_view(request, slug):
    """
    Distraction-free high-converting landing page for Meta/TikTok Ads campaigns.
    """
    product = get_object_or_404(Product.objects.prefetch_related('images', 'variants'), slug=slug, is_active=True)
    return render(request, 'marketing/landing_page.html', {'product': product})
