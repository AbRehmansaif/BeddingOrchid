from decimal import Decimal
from django.shortcuts import redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_POST
from .models import Review
from apps.catalog.models import Product

@login_required
@require_POST
def submit_review(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    try:
        rating = float(request.POST.get('rating', 5.0))
    except (TypeError, ValueError):
        rating = 5.0
    title = request.POST.get('title', '').strip()
    comment = request.POST.get('comment', '').strip()

    if not comment:
        messages.error(request, "Please write a review comment.")
        return redirect(product.get_absolute_url())

    rating_clamped = Decimal(str(round(min(max(rating, 1.0), 5.0), 1)))

    Review.objects.create(
        product=product,
        user=request.user,
        rating=rating_clamped,
        title=title or f"Review by {request.user.full_name or 'Customer'}",
        comment=comment,
        is_verified_buyer=True,
        is_approved=True
    )
    messages.success(request, "Thank you! Your review has been published.")
    return redirect(product.get_absolute_url())
