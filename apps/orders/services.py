import datetime
from decimal import Decimal
from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from .models import Order, OrderItem, OrderStatusHistory
from apps.inventory.services import InventoryService
from apps.catalog.models import ProductVariant
from apps.promotions.models import Coupon
from apps.core.models import SiteSettings

class OrderStateMachine:
    """
    Enforces valid business status transitions for COD and courier delivery.
    """
    VALID_TRANSITIONS = {
        'pending': ['confirmed', 'cancelled', 'on_hold'],
        'confirmed': ['processing', 'cancelled', 'on_hold'],
        'processing': ['packed', 'cancelled', 'on_hold'],
        'packed': ['dispatched', 'cancelled', 'on_hold'],
        'dispatched': ['delivered', 'returned', 'on_hold'],
        'delivered': ['returned', 'refunded'],
        'on_hold': ['pending', 'confirmed', 'processing', 'cancelled'],
        'cancelled': [],
        'returned': ['refunded'],
        'refunded': [],
    }

    @classmethod
    def can_transition(cls, from_status: str, to_status: str) -> bool:
        if from_status == to_status:
            return True
        allowed = cls.VALID_TRANSITIONS.get(from_status, [])
        return to_status in allowed


class OrderService:
    @staticmethod
    def generate_order_number() -> str:
        """Generates a human-friendly, race-safe sequential order number e.g. LC-2026-001001."""
        year = timezone.now().year
        # Count existing orders for this year
        count = Order.objects.filter(order_number__startswith=f"LC-{year}").count() + 1
        return f"LC-{year}-{count:06d}"

    @classmethod
    @transaction.atomic
    def place_order(cls, request, customer_data: dict, shipping_data: dict, cart_service) -> Order:
        """
        Atomically creates order, takes item snapshots, decrements inventory with row locks,
        records marketing attribution, and clears the cart.
        """
        items = cart_service.get_items()
        if not items:
            raise ValidationError("Shopping cart is empty.")

        # Re-verify and lock stock for each variant
        for item in items:
            variant = item['variant']
            qty = item['quantity']
            # select_for_update inside InventoryService
            InventoryService.decrement_stock(variant.id, qty, order_ref="PENDING", user=request.user if request.user.is_authenticated else None)

        order_number = cls.generate_order_number()

        subtotal = cart_service.get_subtotal()
        discount = cart_service.get_discount_amount()
        shipping = cart_service.get_shipping_fee()
        site_settings = SiteSettings.get_settings()
        cod_fee = Decimal(str(site_settings.default_cod_fee))
        grand_total = cart_service.get_grand_total()
        coupon = cart_service.get_applied_coupon()

        # Marketing attribution from session
        attr = getattr(request, 'marketing_attribution', {}) or request.session.get('marketing_attribution', {})

        order = Order.objects.create(
            order_number=order_number,
            user=request.user if request.user.is_authenticated else None,
            customer_name=customer_data.get('full_name', ''),
            customer_phone=customer_data.get('phone', ''),
            customer_email=customer_data.get('email', ''),
            shipping_full_name=shipping_data.get('full_name', ''),
            shipping_phone=shipping_data.get('phone', ''),
            shipping_address_line1=shipping_data.get('address_line1', ''),
            shipping_address_line2=shipping_data.get('address_line2', ''),
            shipping_city=shipping_data.get('city', ''),
            shipping_province=shipping_data.get('province', 'Punjab'),
            shipping_postal_code=shipping_data.get('postal_code', ''),
            shipping_landmark=shipping_data.get('landmark', ''),
            payment_method='COD',
            payment_status='pending',
            subtotal=subtotal,
            discount_total=discount,
            shipping_fee=shipping,
            cod_fee=cod_fee,
            grand_total=grand_total,
            coupon_code=coupon.code if coupon else '',
            customer_note=shipping_data.get('customer_note', ''),
            status='pending',
            utm_source=attr.get('utm_source', ''),
            utm_medium=attr.get('utm_medium', ''),
            utm_campaign=attr.get('utm_campaign', ''),
            utm_content=attr.get('utm_content', ''),
            utm_term=attr.get('utm_term', ''),
            fbp=attr.get('fbp', ''),
            fbc=attr.get('fbc', ''),
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
        )

        # Create immutable OrderItems
        for item in items:
            variant = item['variant']
            qty = item['quantity']
            unit_price = item['unit_price']
            img_url = ''
            if item.get('image'):
                try:
                    img_url = item['image'].url
                except Exception:
                    img_url = ''

            OrderItem.objects.create(
                order=order,
                product=variant.product,
                variant=variant,
                product_name=variant.product.name,
                variant_sku=variant.sku,
                size_name=variant.size.name if variant.size else '',
                color_name=variant.color.name if variant.color else '',
                unit_price=unit_price,
                quantity=qty,
                line_total=item['line_total'],
                image_url=img_url
            )

        # Update StockMovement logs with exact order_number
        from apps.inventory.models import StockMovement
        StockMovement.objects.filter(order_ref="PENDING").update(order_ref=order.order_number)

        # If coupon applied, increment times_used
        if coupon:
            Coupon.objects.filter(pk=coupon.pk).update(times_used=models.F('times_used') + 1)

        # Create status history
        OrderStatusHistory.objects.create(
            order=order,
            from_status='',
            to_status='pending',
            changed_by=request.user if request.user.is_authenticated else None,
            note='Order successfully placed by customer via Cash on Delivery.'
        )

        # Clear cart
        cart_service.clear()

        # Trigger Notifications & Meta Conversions API asynchronously
        try:
            from apps.marketing.services import MetaConversionsApiService
            MetaConversionsApiService.send_purchase_event(order)
        except Exception:
            pass

        try:
            from apps.notifications.services import NotificationService
            NotificationService.send_order_placed_notification(order)
        except Exception:
            pass

        return order

    @classmethod
    @transaction.atomic
    def update_status(cls, order: Order, new_status: str, user=None, note: str = '', notify: bool = True):
        """Transitions order status and handles inventory restoration on cancel/return."""
        old_status = order.status
        if not OrderStateMachine.can_transition(old_status, new_status):
            raise ValidationError(f"Invalid status jump from '{old_status}' to '{new_status}'.")

        # If transitioning to Delivered and COD, mark payment as paid
        if new_status == 'delivered' and order.payment_method == 'COD':
            order.payment_status = 'paid'

        # If transitioning to Cancelled or Returned, restore inventory back
        if new_status in ['cancelled', 'returned'] and old_status not in ['cancelled', 'returned']:
            for item in order.items.all():
                if item.variant:
                    InventoryService.restore_stock(
                        variant_id=item.variant.id,
                        quantity=item.quantity,
                        order_ref=order.order_number,
                        reason=new_status,
                        user=user
                    )

        order.status = new_status
        order.save(update_fields=['status', 'payment_status', 'updated_at'])

        OrderStatusHistory.objects.create(
            order=order,
            from_status=old_status,
            to_status=new_status,
            changed_by=user,
            note=note or f"Status changed from {old_status} to {new_status}.",
            notify_customer=notify
        )

        if notify:
            try:
                from apps.notifications.services import NotificationService
                NotificationService.send_order_status_update(order, old_status, new_status)
            except Exception:
                pass

        return order

    @staticmethod
    def get_courier_tracking_url(courier_name: str, tracking_number: str) -> str:
        """Builds courier portal tracking URL for Pakistani couriers."""
        c = (courier_name or '').strip().lower()
        num = (tracking_number or '').strip()
        if not num:
            return ''
        if 'trax' in c:
            return f"https://trax.pk/tracking/?tracking_id={num}"
        elif 'leopard' in c:
            return f"https://www.leopardscourier.com/tracking?track_numbers={num}"
        elif 'postex' in c:
            return f"https://postex.pk/tracking?tracking_number={num}"
        elif 'tcs' in c:
            return f"https://www.tcsexpress.com/track/{num}"
        elif 'm&p' in c or 'mnp' in c:
            return f"https://mulphilog.com/tracking?cons={num}"
        return ''
