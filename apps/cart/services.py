from decimal import Decimal
from django.conf import settings
from django.db.models import Q
from apps.catalog.models import ProductVariant, QuantityDiscount
from apps.promotions.models import Coupon
from apps.core.models import SiteSettings

class CartService:
    """
    Manages session and DB shopping carts.
    Guarantees that prices and discounts are ALWAYS re-calculated dynamically from the database.
    """
    SESSION_KEY = 'bedding_cart'

    def __init__(self, request):
        self.request = request
        self.session = request.session
        cart_data = self.session.get(self.SESSION_KEY)
        if not cart_data or not isinstance(cart_data, dict):
            cart_data = self.session[self.SESSION_KEY] = {}
        self.cart_data = cart_data
        self.site_settings = SiteSettings.get_settings()

    def add(self, variant_id: int, quantity: int = 1) -> bool:
        variant_id_str = str(variant_id)
        current_qty = self.cart_data.get(variant_id_str, 0)
        new_qty = current_qty + quantity
        
        # Verify variant exists and has stock
        try:
            variant = ProductVariant.objects.get(id=variant_id, is_active=True)
            if variant.stock_quantity < new_qty:
                new_qty = variant.stock_quantity
            if new_qty > 0:
                self.cart_data[variant_id_str] = new_qty
                self.save()
                return True
        except ProductVariant.DoesNotExist:
            pass
        return False

    def update(self, variant_id: int, quantity: int):
        variant_id_str = str(variant_id)
        if quantity <= 0:
            self.remove(variant_id)
        else:
            try:
                variant = ProductVariant.objects.get(id=variant_id, is_active=True)
                capped_qty = min(quantity, variant.stock_quantity)
                self.cart_data[variant_id_str] = capped_qty
                self.save()
            except ProductVariant.DoesNotExist:
                self.remove(variant_id)

    def remove(self, variant_id: int):
        variant_id_str = str(variant_id)
        if variant_id_str in self.cart_data:
            del self.cart_data[variant_id_str]
            self.save()

    def clear(self):
        self.session[self.SESSION_KEY] = {}
        self.session['applied_coupon_code'] = None
        self.save()

    def save(self):
        self.session.modified = True

    def get_applied_coupon(self):
        code = self.session.get('applied_coupon_code')
        if code:
            coupon = Coupon.objects.filter(code__iexact=code, is_active=True).first()
            return coupon
        return None

    def apply_coupon(self, code: str):
        coupon = Coupon.objects.filter(code__iexact=code.strip(), is_active=True).first()
        if not coupon:
            return False, "Invalid or expired coupon code."
        
        subtotal = self.get_subtotal()
        is_valid, msg = coupon.is_valid_for(subtotal)
        if not is_valid:
            return False, msg

        self.session['applied_coupon_code'] = coupon.code
        self.save()
        return True, f"Coupon '{coupon.code}' applied successfully!"

    def remove_coupon(self):
        self.session['applied_coupon_code'] = None
        self.save()

    def get_items(self):
        """Returns structured list of items with fresh database prices, variants and images."""
        variant_ids = [int(vid) for vid in self.cart_data.keys() if vid.isdigit()]
        variants = ProductVariant.objects.filter(id__in=variant_ids, is_active=True).select_related(
            'product', 'size', 'color', 'image'
        ).prefetch_related('product__images')

        variant_map = {v.id: v for v in variants}
        items = []

        for vid_str, qty in list(self.cart_data.items()):
            vid = int(vid_str)
            if vid in variant_map and qty > 0:
                variant = variant_map[vid]
                unit_price = variant.effective_price
                compare_price = variant.effective_compare_at_price
                line_total = unit_price * qty
                saving = (compare_price - unit_price) * qty if compare_price and compare_price > unit_price else Decimal('0.00')

                # Primary image lookup
                img = variant.image.image if variant.image else None
                if not img and variant.product.primary_image:
                    img = variant.product.primary_image.image

                items.append({
                    'variant': variant,
                    'quantity': qty,
                    'unit_price': unit_price,
                    'compare_price': compare_price,
                    'line_total': line_total,
                    'saving': saving,
                    'image': img,
                })
            else:
                # Remove inactive or invalid variants
                self.remove(vid)

        return items

    def get_count(self) -> int:
        return sum(self.cart_data.values())

    def get_subtotal(self) -> Decimal:
        items = self.get_items()
        return sum(item['line_total'] for item in items)

    def get_quantity_discount_amount(self) -> Decimal:
        """Calculates multi-buy / bulk volume savings from QuantityDiscount rules."""
        items = self.get_items()
        total_qd = Decimal('0.00')

        for item in items:
            variant = item['variant']
            qty = item['quantity']
            product = variant.product

            qd = QuantityDiscount.objects.filter(
                Q(product=product) | Q(product__isnull=True),
                min_quantity__lte=qty
            ).order_by('-discount_percentage', '-min_quantity').first()

            if qd:
                discount_rate = Decimal(str(qd.discount_percentage)) / Decimal('100')
                total_qd += item['line_total'] * discount_rate

        return round(total_qd, 2)

    def get_discount_amount(self) -> Decimal:
        coupon_discount = Decimal('0.00')
        coupon = self.get_applied_coupon()
        if coupon:
            subtotal = self.get_subtotal()
            is_valid, _ = coupon.is_valid_for(subtotal)
            if is_valid:
                coupon_discount = coupon.calculate_discount(subtotal)

        quantity_discount = self.get_quantity_discount_amount()
        return round(coupon_discount + quantity_discount, 2)

    def get_shipping_fee(self) -> Decimal:
        subtotal = self.get_subtotal()
        threshold = Decimal(str(self.site_settings.free_shipping_threshold))
        if subtotal == 0 or subtotal >= threshold:
            return Decimal('0.00')
        return Decimal(str(self.site_settings.default_shipping_fee))

    def get_grand_total(self) -> Decimal:
        subtotal = self.get_subtotal()
        discount = self.get_discount_amount()
        shipping = self.get_shipping_fee()
        cod_fee = Decimal(str(self.site_settings.default_cod_fee))
        total = (subtotal - discount) + shipping + cod_fee
        return max(total, Decimal('0.00'))

    def get_free_shipping_progress(self):
        subtotal = self.get_subtotal()
        threshold = Decimal(str(self.site_settings.free_shipping_threshold))
        if subtotal >= threshold:
            return {'progress': 100, 'remaining': Decimal('0.00'), 'achieved': True}
        remaining = threshold - subtotal
        progress = int((subtotal / threshold) * 100) if threshold > 0 else 100
        return {'progress': progress, 'remaining': remaining, 'achieved': False}
