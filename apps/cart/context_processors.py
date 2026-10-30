from .services import CartService

def cart_context(request):
    """
    Injects cart count, subtotal, and free shipping progress into all templates.
    """
    # Safe check in case request has no session
    if not hasattr(request, 'session'):
        return {}

    cart_service = CartService(request)
    return {
        'cart_count': cart_service.get_count(),
        'cart_subtotal': cart_service.get_subtotal(),
        'cart_free_shipping': cart_service.get_free_shipping_progress(),
        'applied_coupon': cart_service.get_applied_coupon(),
    }
