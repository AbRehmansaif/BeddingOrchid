from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.template.loader import render_to_string
from django.views.decorators.http import require_POST
from django.contrib import messages
from .services import CartService
from apps.catalog.models import ProductVariant

def cart_detail(request):
    cart_service = CartService(request)
    items = cart_service.get_items()
    context = {
        'items': items,
        'subtotal': cart_service.get_subtotal(),
        'discount': cart_service.get_discount_amount(),
        'shipping_fee': cart_service.get_shipping_fee(),
        'grand_total': cart_service.get_grand_total(),
        'free_shipping': cart_service.get_free_shipping_progress(),
        'coupon': cart_service.get_applied_coupon(),
    }
    return render(request, 'cart/cart.html', context)


@require_POST
def cart_add(request):
    cart_service = CartService(request)
    variant_ids = request.POST.getlist('variant_ids')
    
    # Batch add multiple custom items (e.g. Item 1 size/color + Item 2 size/color)
    if variant_ids:
        added_count = 0
        for vid in variant_ids:
            try:
                cart_service.add(int(vid), 1)
                added_count += 1
            except (TypeError, ValueError):
                continue
        if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.GET.get('format') == 'json':
            items = cart_service.get_items()
            drawer_html = render_to_string('partials/_mini_cart.html', {
                'items': items,
                'subtotal': cart_service.get_subtotal(),
                'discount': cart_service.get_discount_amount(),
                'grand_total': cart_service.get_grand_total(),
                'free_shipping': cart_service.get_free_shipping_progress(),
                'cart_count': cart_service.get_count(),
            }, request=request)
            return JsonResponse({
                'success': True,
                'message': f"{added_count} items added to your bag!",
                'cart_count': cart_service.get_count(),
                'drawer_html': drawer_html,
            })
        messages.success(request, f"{added_count} items added to your bag!")
        return redirect('cart:detail')

    variant_id = request.POST.get('variant_id')
    try:
        quantity = max(1, int(request.POST.get('quantity', 1)))
    except (TypeError, ValueError):
        quantity = 1

    if not variant_id:
        if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.GET.get('format') == 'json':
            return JsonResponse({'success': False, 'message': 'Please select size and color.'}, status=400)
        messages.error(request, 'Please select size and color.')
        return redirect(request.META.get('HTTP_REFERER', 'cart:detail'))

    try:
        vid_int = int(variant_id)
    except (TypeError, ValueError):
        if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.GET.get('format') == 'json':
            return JsonResponse({'success': False, 'message': 'Invalid product variant.'}, status=400)
        messages.error(request, 'Invalid product variant.')
        return redirect(request.META.get('HTTP_REFERER', 'cart:detail'))

    success = cart_service.add(vid_int, quantity)

    if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.GET.get('format') == 'json':
        items = cart_service.get_items()
        drawer_html = render_to_string('partials/_mini_cart.html', {
            'items': items,
            'subtotal': cart_service.get_subtotal(),
            'discount': cart_service.get_discount_amount(),
            'grand_total': cart_service.get_grand_total(),
            'free_shipping': cart_service.get_free_shipping_progress(),
            'cart_count': cart_service.get_count(),
        }, request=request)

        return JsonResponse({
            'success': success,
            'message': 'Product added to bag!' if success else 'Unable to add product (out of stock).',
            'cart_count': cart_service.get_count(),
            'subtotal': float(cart_service.get_subtotal()),
            'drawer_html': drawer_html,
        })

    if success:
        messages.success(request, 'Item added to your shopping bag.')
    else:
        messages.error(request, 'Item could not be added due to limited stock.')

    return redirect(request.META.get('HTTP_REFERER', 'cart:detail'))


@require_POST
def cart_update(request):
    cart_service = CartService(request)
    try:
        variant_id = int(request.POST.get('variant_id'))
        quantity = max(1, int(request.POST.get('quantity', 1)))
    except (TypeError, ValueError):
        return JsonResponse({'success': False, 'message': 'Invalid parameters.'}, status=400) if request.headers.get('x-requested-with') == 'XMLHttpRequest' else redirect('cart:detail')

    cart_service.update(variant_id, quantity)

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True,
            'cart_count': cart_service.get_count(),
            'subtotal': float(cart_service.get_subtotal()),
            'discount': float(cart_service.get_discount_amount()),
            'grand_total': float(cart_service.get_grand_total()),
            'shipping_fee': float(cart_service.get_shipping_fee()),
            'free_shipping': cart_service.get_free_shipping_progress(),
        })

    return redirect('cart:detail')


@require_POST
def cart_remove(request):
    cart_service = CartService(request)
    try:
        variant_id = int(request.POST.get('variant_id'))
    except (TypeError, ValueError):
        return JsonResponse({'success': False, 'message': 'Invalid parameters.'}, status=400) if request.headers.get('x-requested-with') == 'XMLHttpRequest' else redirect('cart:detail')

    cart_service.remove(variant_id)

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True,
            'cart_count': cart_service.get_count(),
            'subtotal': float(cart_service.get_subtotal()),
            'grand_total': float(cart_service.get_grand_total()),
        })

    messages.info(request, "Item removed from your bag.")
    return redirect('cart:detail')


@require_POST
def apply_coupon(request):
    cart_service = CartService(request)
    code = request.POST.get('coupon_code', '')
    success, message = cart_service.apply_coupon(code)

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({
            'success': success,
            'message': message,
            'discount': float(cart_service.get_discount_amount()),
            'grand_total': float(cart_service.get_grand_total()),
        })

    if success:
        messages.success(request, message)
    else:
        messages.error(request, message)

    return redirect(request.META.get('HTTP_REFERER', 'cart:detail'))


@require_POST
def remove_coupon(request):
    cart_service = CartService(request)
    cart_service.remove_coupon()
    messages.info(request, "Coupon removed.")
    return redirect(request.META.get('HTTP_REFERER', 'cart:detail'))


def mini_cart_drawer(request):
    """Returns HTML for slide-out cart drawer."""
    cart_service = CartService(request)
    return render(request, 'partials/_mini_cart.html', {
        'items': cart_service.get_items(),
        'subtotal': cart_service.get_subtotal(),
        'discount': cart_service.get_discount_amount(),
        'grand_total': cart_service.get_grand_total(),
        'free_shipping': cart_service.get_free_shipping_progress(),
        'cart_count': cart_service.get_count(),
    })
