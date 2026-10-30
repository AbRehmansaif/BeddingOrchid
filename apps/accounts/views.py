from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from .models import User, Address, Wishlist, WishlistItem
from .forms import LoginForm, RegisterForm, AddressForm
from apps.orders.models import Order
from apps.catalog.models import Product


def login_view(request):
    if request.user.is_authenticated:
        return redirect('accounts:profile')

    form = LoginForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        username = form.cleaned_data['username'].strip()
        password = form.cleaned_data['password']
        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            messages.success(request, f"Welcome back, {user.full_name or user.username}! 👋")
            next_url = request.GET.get('next') or request.POST.get('next') or 'accounts:profile'
            return redirect(next_url)
        else:
            messages.error(request, "Incorrect mobile number / email or password. Please try again.")

    return render(request, 'accounts/login.html', {
        'form': form,
        'next': request.GET.get('next', ''),
    })


def register_view(request):
    if request.user.is_authenticated:
        return redirect('accounts:profile')

    form = RegisterForm(request.POST or None)
    if request.method == 'POST':
        if form.is_valid():
            user = form.save()
            # Create wishlist for new user
            Wishlist.objects.get_or_create(user=user)
            login(request, user, backend='apps.accounts.backends.EmailOrPhoneModelBackend')
            messages.success(request, f"Welcome to BeddingOrchid, {user.full_name or user.username}! 🎉 Your account is ready.")
            next_url = request.GET.get('next') or 'accounts:profile'
            return redirect(next_url)
        else:
            # Collect all form errors for display
            for field, error_list in form.errors.items():
                for error in error_list:
                    if field == '__all__':
                        messages.error(request, error)
                    else:
                        label = form.fields.get(field, None)
                        field_label = label.label if label else field.replace('_', ' ').title()
                        messages.error(request, f"{field_label}: {error}")

    return render(request, 'accounts/register.html', {
        'form': form,
        'next': request.GET.get('next', ''),
    })


def logout_view(request):
    logout(request)
    messages.info(request, "You have been signed out successfully.")
    return redirect('catalog:home')


@login_required
def profile_overview(request):
    recent_orders = Order.objects.filter(user=request.user).order_by('-placed_at')[:5]
    addresses = Address.objects.filter(user=request.user)[:3]
    return render(request, 'accounts/profile.html', {
        'recent_orders': recent_orders,
        'addresses': addresses,
    })


@login_required
def my_orders(request):
    orders = Order.objects.filter(user=request.user).order_by('-placed_at')
    return render(request, 'accounts/orders.html', {'orders': orders})


@login_required
def order_detail(request, order_number):
    order = get_object_or_404(Order, order_number=order_number, user=request.user)
    return render(request, 'accounts/order_detail.html', {'order': order})


@login_required
def addresses_list(request):
    addresses = Address.objects.filter(user=request.user)
    form = AddressForm()
    return render(request, 'accounts/addresses.html', {
        'addresses': addresses,
        'form': form,
    })


@login_required
def address_create(request):
    if request.method == 'POST':
        form = AddressForm(request.POST)
        if form.is_valid():
            address = form.save(commit=False)
            address.user = request.user
            # Make first address default automatically
            if not Address.objects.filter(user=request.user).exists():
                address.is_default = True
            address.save()
            messages.success(request, "✅ Address saved successfully.")
            return redirect('accounts:addresses')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, error)
    return redirect('accounts:addresses')


@login_required
def address_edit(request, address_id):
    address = get_object_or_404(Address, id=address_id, user=request.user)
    if request.method == 'POST':
        form = AddressForm(request.POST, instance=address)
        if form.is_valid():
            form.save()
            messages.success(request, "✅ Address updated successfully.")
            return redirect('accounts:addresses')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, error)
    else:
        form = AddressForm(instance=address)
    return render(request, 'accounts/address_edit.html', {
        'form': form,
        'address': address,
    })


@login_required
def address_delete(request, address_id):
    address = get_object_or_404(Address, id=address_id, user=request.user)
    if request.method == 'POST':
        address.delete()
        messages.success(request, "Address removed.")
    return redirect('accounts:addresses')


@login_required
def address_set_default(request, address_id):
    address = get_object_or_404(Address, id=address_id, user=request.user)
    address.is_default = True
    address.save()
    messages.success(request, "✅ Default delivery address updated.")
    return redirect('accounts:addresses')


@login_required
def wishlist_view(request):
    wishlist, _ = Wishlist.objects.get_or_create(user=request.user)
    items = wishlist.items.select_related('product').prefetch_related(
        'product__images', 'product__category'
    ).all()
    return render(request, 'accounts/wishlist.html', {'wishlist_items': items})


@require_POST
def wishlist_toggle_ajax(request):
    """AJAX endpoint — returns JSON. Returns 403 JSON (not HTML redirect) when not authenticated."""
    if not request.user.is_authenticated:
        return JsonResponse({
            'success': False,
            'message': 'Please log in to manage your wishlist.',
            'redirect': '/account/login/',
        }, status=403)

    product_id = request.POST.get('product_id')
    if not product_id:
        return JsonResponse({'success': False, 'message': 'Invalid product.'}, status=400)

    try:
        product = Product.objects.get(id=int(product_id), is_active=True)
    except (Product.DoesNotExist, ValueError):
        return JsonResponse({'success': False, 'message': 'Product not found.'}, status=404)

    wishlist, _ = Wishlist.objects.get_or_create(user=request.user)
    item = WishlistItem.objects.filter(wishlist=wishlist, product=product).first()

    if item:
        item.delete()
        in_wishlist = False
        message = "❤️ Removed from favourites"
    else:
        WishlistItem.objects.create(wishlist=wishlist, product=product)
        in_wishlist = True
        message = "❤️ Added to favourites"

    count = wishlist.items.count()
    return JsonResponse({
        'success': True,
        'in_wishlist': in_wishlist,
        'count': count,
        'message': message,
    })
