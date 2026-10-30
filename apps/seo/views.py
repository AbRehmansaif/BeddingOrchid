from django.http import HttpResponse
from django.shortcuts import render
from django.contrib.admin.views.decorators import staff_member_required
from apps.catalog.models import Category, Product
from apps.pages.models import Page

def robots_txt(request):
    domain = request.get_host()
    lines = [
        "User-agent: *",
        "Disallow: /admin/",
        "Disallow: /cart/",
        "Disallow: /checkout/",
        "Disallow: /account/",
        "Disallow: /search/",
        "Disallow: /*?*",
        "",
        f"Sitemap: https://{domain}/sitemap.xml",
    ]
    return HttpResponse("\n".join(lines), content_type="text/plain")


def sitemap_xml(request):
    domain = request.get_host()
    protocol = "https" if request.is_secure() else "http"
    base_url = f"{protocol}://{domain}"

    categories = Category.objects.filter(is_active=True)
    products = Product.objects.filter(is_active=True)
    pages = Page.objects.all()

    context = {
        'base_url': base_url,
        'categories': categories,
        'products': products,
        'pages': pages,
    }
    xml_content = render(request, 'seo/sitemap.xml', context, content_type="application/xml")
    return xml_content


@staff_member_required
def seo_audit_view(request):
    products_missing_meta = Product.objects.filter(is_active=True, meta_title__exact='')
    categories_missing_meta = Category.objects.filter(is_active=True, meta_title__exact='')
    return render(request, 'seo/audit.html', {
        'products_missing_meta': products_missing_meta,
        'categories_missing_meta': categories_missing_meta,
    })
