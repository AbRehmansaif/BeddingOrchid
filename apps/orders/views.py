from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import login, get_user_model
from django.views.decorators.http import require_POST
from django.db import transaction
from .models import Order
from .services import OrderService
from apps.cart.services import CartService
from apps.accounts.models import Address
from apps.catalog.models import ProductVariant
from apps.core.models import SiteSettings

User = get_user_model()

# Pakistani cities offered in the dropdown (must match checkout.html options exactly)
PK_CITIES = [
    'Karachi', 'Lahore', 'Islamabad', 'Rawalpindi', 'Faisalabad',
    'Multan', 'Peshawar', 'Quetta', 'Sialkot', 'Gujranwala',
    'Hyderabad', 'Bahawalpur', 'Abbottabad', 'Sargodha', 'Sukkur',
]


def checkout_view(request):
    cart_service = CartService(request)
    items = cart_service.get_items()

    if not items:
        messages.warning(request, "Your bag is empty. Please add items to checkout.")
        return redirect('cart:detail')

    site_settings = SiteSettings.get_settings()
    user = request.user if request.user.is_authenticated else None
    saved_addresses = Address.objects.filter(user=user) if user else Address.objects.none()
    default_address = (
        saved_addresses.filter(is_default=True).first()
        or (saved_addresses.first() if saved_addresses.exists() else None)
    )

    if request.method == 'POST':
        full_name = request.POST.get('full_name', '').strip()
        phone = request.POST.get('phone', '').strip()
        email = request.POST.get('email', '').strip() or None
        password = request.POST.get('password', '').strip()
        address_line1 = request.POST.get('address_line1', '').strip()
        address_line2 = request.POST.get('address_line2', '').strip()
        city = request.POST.get('city', '').strip()
        other_city = request.POST.get('other_city', '').strip()  # free-text fallback
        province = request.POST.get('province', 'Punjab').strip()
        postal_code = request.POST.get('postal_code', '').strip()
        landmark = request.POST.get('landmark', '').strip()
        customer_note = request.POST.get('customer_note', '').strip()
        save_address = request.POST.get('save_address') == 'on'

        # Resolve city: if "Other City" selected, use the text input
        if city == 'Other City' and other_city:
            city = other_city
        elif city == 'Other City':
            city = 'Other City'

        # --- Basic field validation ---
        errors = []
        if not full_name:
            errors.append("Full name is required.")
        if not phone or len(phone.replace(' ', '')) < 10:
            errors.append("A valid mobile phone number is required.")
        if not address_line1:
            errors.append("Street address is required.")
        if not city:
            errors.append("Please select or enter your city.")

        if errors:
            for e in errors:
                messages.error(request, e)
            return redirect('orders:checkout')

        # --- Account handling for guest checkout ---
        if not request.user.is_authenticated:
            # If customer didn't add email or left password empty, do NOT create an account.
            # Only create an account if both email and password (min 6 chars) are explicitly provided.
            if email and password and len(password) >= 6:
                existing_user = User.objects.filter(email=email).first()
                if not existing_user and phone:
                    existing_user = User.objects.filter(phone=phone).first()

                if existing_user:
                    # Authenticate if password matches
                    if existing_user.check_password(password):
                        login(request, existing_user, backend='apps.accounts.backends.EmailOrPhoneModelBackend')
                else:
                    try:
                        new_user = User.objects.create_user(
                            phone=phone,
                            email=email,
                            password=password,
                            full_name=full_name,
                        )
                        login(request, new_user, backend='apps.accounts.backends.EmailOrPhoneModelBackend')
                    except Exception:
                        # Continue as guest order without interrupting checkout
                        pass
            # If no email or empty password, proceed smoothly as guest without creating an account

        # Optionally save address to account book
        if save_address and request.user.is_authenticated:
            try:
                Address.objects.create(
                    user=request.user,
                    label='Home',
                    full_name=full_name,
                    phone=phone,
                    address_line1=address_line1,
                    address_line2=address_line2,
                    city=city,
                    province=province,
                    postal_code=postal_code,
                    landmark=landmark,
                    is_default=not request.user.addresses.exists(),
                )
            except Exception:
                pass  # Don't block order if address save fails

        customer_data = {
            'full_name': full_name,
            'phone': phone,
            'email': email or (getattr(request.user, 'email', None) if request.user.is_authenticated else None) or '',
        }

        shipping_data = {
            'full_name': full_name,
            'phone': phone,
            'address_line1': address_line1,
            'address_line2': address_line2,
            'city': city,
            'province': province,
            'postal_code': postal_code,
            'landmark': landmark,
            'customer_note': customer_note,
        }

        try:
            order = OrderService.place_order(
                request=request,
                customer_data=customer_data,
                shipping_data=shipping_data,
                cart_service=cart_service,
            )
            return redirect('orders:thank_you', public_id=order.public_id)
        except Exception as e:
            messages.error(request, f"Unable to place order: {str(e)}")
            return redirect('orders:checkout')

    # Determine default city for the form ("Other City" default for smooth nationwide process)
    default_city = default_address.city if (default_address and default_address.city) else 'Other City'
    # If the default city is not in our fixed list, treat as other city
    default_city_is_listed = default_city in PK_CITIES
    default_other_city = '' if (default_city_is_listed or default_city == 'Other City') else default_city

    context = {
        'items': items,
        'subtotal': cart_service.get_subtotal(),
        'discount': cart_service.get_discount_amount(),
        'shipping_fee': cart_service.get_shipping_fee(),
        'cod_fee': site_settings.default_cod_fee,
        'grand_total': cart_service.get_grand_total(),
        'coupon': cart_service.get_applied_coupon(),
        'saved_addresses': saved_addresses,
        'default_address': default_address,
        'site_settings': site_settings,
        'user_full_name': request.user.full_name if request.user.is_authenticated else '',
        'user_phone': request.user.phone if request.user.is_authenticated else '',
        'user_email': request.user.email if request.user.is_authenticated else '',
        'pk_cities': PK_CITIES,
        'default_city': default_city if default_city_is_listed else 'Other City',
        'default_other_city': default_other_city,
    }
    return render(request, 'orders/checkout.html', context)


@require_POST
def buy_now(request):
    """Bypasses normal cart and goes straight to checkout with selected items."""
    variant_ids = request.POST.getlist('variant_ids')
    cart_service = CartService(request)
    cart_service.clear()

    # Multiple customized items (Item 1, Item 2, etc.)
    if variant_ids:
        added_count = 0
        for vid in variant_ids:
            try:
                variant = ProductVariant.objects.get(id=int(vid), is_active=True)
                cart_service.add(variant.id, 1)
                added_count += 1
            except (ProductVariant.DoesNotExist, ValueError, TypeError):
                continue
        if added_count == 0:
            messages.error(request, "Selected product options are no longer available.")
            return redirect(request.META.get('HTTP_REFERER', 'catalog:home'))
        return redirect('orders:checkout')

    variant_id = request.POST.get('variant_id')
    quantity = int(request.POST.get('quantity', 1))

    if not variant_id:
        messages.error(request, "Please select your bed sheet size and color before buying.")
        return redirect(request.META.get('HTTP_REFERER', 'catalog:home'))

    # Validate variant exists
    try:
        variant = ProductVariant.objects.get(id=int(variant_id), is_active=True)
    except ProductVariant.DoesNotExist:
        messages.error(request, "Selected product variant is no longer available.")
        return redirect(request.META.get('HTTP_REFERER', 'catalog:home'))

    cart_service.add(variant.id, quantity)
    return redirect('orders:checkout')


def thank_you(request, public_id):
    order = get_object_or_404(Order.objects.prefetch_related('items'), public_id=public_id)
    return render(request, 'orders/thank_you.html', {'order': order})


def track_order(request):
    order = None
    searched = False
    error_msg = None

    if request.method == 'GET' and ('order_number' in request.GET or 'phone' in request.GET):
        searched = True
        num = request.GET.get('order_number', '').strip().upper()
        ph = request.GET.get('phone', '').strip()

        if num and ph:
            order = Order.objects.filter(order_number__iexact=num).prefetch_related('items').first()
            if not order or ph[-7:] not in (order.shipping_phone or ''):
                order = None
                error_msg = "No order found matching this order number and mobile phone."
        elif num:
            order = Order.objects.filter(order_number__iexact=num).prefetch_related('items').first()
            if not order:
                error_msg = "No order found with this order number."
        else:
            error_msg = "Please enter your order number to track your parcel."

    return render(request, 'orders/tracking.html', {
        'order': order,
        'searched': searched,
        'error_msg': error_msg,
    })


def admin_invoice(request, order_number):
    """Clean printable parcel shipping label and packing slip."""
    order = get_object_or_404(Order.objects.prefetch_related('items'), order_number=order_number)
    site_settings = SiteSettings.get_settings()
    return render(request, 'orders/invoice.html', {
        'orders': [order],
        'order': order,
        'is_bulk': False,
        'site_settings': site_settings,
    })


def admin_bulk_invoices(request):
    """Bulk printable shipping labels and packing slips for selected orders."""
    ids_str = request.GET.get('ids', '')
    if not ids_str:
        return HttpResponse("No orders selected for printing. Please select orders from the Admin panel.")
    order_ids = [int(x) for x in ids_str.split(',') if x.isdigit()]
    orders = Order.objects.filter(id__in=order_ids).prefetch_related('items').order_by('-placed_at')
    site_settings = SiteSettings.get_settings()
    return render(request, 'orders/invoice.html', {
        'orders': orders,
        'is_bulk': True,
        'site_settings': site_settings,
    })

