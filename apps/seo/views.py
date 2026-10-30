import json
import os
from django.conf import settings
from django.http import HttpResponse, FileResponse
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


def manifest_json(request):
    manifest_path = os.path.join(settings.BASE_DIR, 'static', 'manifest.json')
    if os.path.exists(manifest_path):
        with open(manifest_path, 'r', encoding='utf-8') as f:
            data = f.read()
        return HttpResponse(data, content_type="application/manifest+json")
    
    # Fallback inline manifest
    fallback = {
        "name": "BeddingOrchid - Luxury Bedding & Outerwear",
        "short_name": "BeddingOrchid",
        "start_url": "/",
        "display": "standalone",
        "background_color": "#FAF8F5",
        "theme_color": "#1E293B",
        "icons": [
            {
                "src": "/static/images/pwa/icon-192.png",
                "sizes": "192x192",
                "type": "image/png",
                "purpose": "any maskable"
            },
            {
                "src": "/static/images/pwa/icon-512.png",
                "sizes": "512x512",
                "type": "image/png",
                "purpose": "any maskable"
            }
        ]
    }
    return HttpResponse(json.dumps(fallback), content_type="application/manifest+json")


def service_worker_js(request):
    sw_path = os.path.join(settings.BASE_DIR, 'static', 'sw.js')
    if os.path.exists(sw_path):
        with open(sw_path, 'r', encoding='utf-8') as f:
            code = f.read()
    else:
        code = "self.addEventListener('fetch', () => {});"
    
    response = HttpResponse(code, content_type="application/javascript")
    response["Service-Worker-Allowed"] = "/"
    response["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return response


@staff_member_required
def seo_audit_view(request):
    products_missing_meta = Product.objects.filter(is_active=True, meta_title__exact='')
    categories_missing_meta = Category.objects.filter(is_active=True, meta_title__exact='')
    return render(request, 'seo/audit.html', {
        'products_missing_meta': products_missing_meta,
        'categories_missing_meta': categories_missing_meta,
    })
