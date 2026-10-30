from .models import SiteSettings
from django.core.cache import cache

def site_context(request):
    """
    Context processor to inject SiteSettings, categories menu, and store constants
    into all templates.
    """
    settings_obj = SiteSettings.get_settings()

    # Cached category tree for navigation / mega-menu
    categories_tree = cache.get('nav_categories_tree')
    if categories_tree is None:
        try:
            from apps.catalog.models import Category
            categories_tree = Category.objects.filter(is_active=True, show_in_menu=True, parent__isnull=True).prefetch_related('children')
            cache.set('nav_categories_tree', list(categories_tree), timeout=3600)
        except Exception:
            categories_tree = []

    # Clean WhatsApp URL
    whatsapp_clean = ''.join(filter(str.isdigit, str(settings_obj.whatsapp_number)))
    whatsapp_chat_url = f"https://wa.me/{whatsapp_clean}?text=Hello%20{settings_obj.store_name},%20I%20have%20an%20inquiry%20about%20your%20bedding%20collection."

    return {
        'site_settings': settings_obj,
        'categories_tree': categories_tree,
        'STORE_NAME': settings_obj.store_name,
        'CURRENCY_SYMBOL': settings_obj.currency_symbol,
        'WHATSAPP_CHAT_URL': whatsapp_chat_url,
    }
