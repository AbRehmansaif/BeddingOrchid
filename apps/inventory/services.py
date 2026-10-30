from django.db import transaction
from django.core.exceptions import ValidationError
from apps.catalog.models import ProductVariant
from .models import StockMovement

class InventoryService:
    @staticmethod
    def check_availability(variant_id: int, quantity: int) -> bool:
        """Check if variant has sufficient stock available."""
        try:
            variant = ProductVariant.objects.get(id=variant_id, is_active=True)
            return variant.stock_quantity >= quantity
        except ProductVariant.DoesNotExist:
            return False

    @staticmethod
    @transaction.atomic
    def decrement_stock(variant_id: int, quantity: int, order_ref: str = '', user=None) -> ProductVariant:
        """
        Atomically decrements stock using select_for_update() to prevent race conditions
        and overselling under heavy concurrent user load.
        """
        variant = ProductVariant.objects.select_for_update().get(id=variant_id)

        if variant.stock_quantity < quantity:
            raise ValidationError(
                f"Insufficient stock for {variant}. Requested: {quantity}, Available: {variant.stock_quantity}"
            )

        variant.stock_quantity -= quantity
        variant.save(update_fields=['stock_quantity', 'updated_at'])

        StockMovement.objects.create(
            variant=variant,
            quantity_change=-quantity,
            balance_after=variant.stock_quantity,
            reason='sale',
            order_ref=order_ref,
            user=user,
            note=f"Deducted for order {order_ref}"
        )
        return variant

    @staticmethod
    @transaction.atomic
    def restore_stock(variant_id: int, quantity: int, order_ref: str = '', reason: str = 'cancellation', user=None) -> ProductVariant:
        """
        Atomically restores stock back when an order is cancelled or returned.
        """
        variant = ProductVariant.objects.select_for_update().get(id=variant_id)
        variant.stock_quantity += quantity
        variant.save(update_fields=['stock_quantity', 'updated_at'])

        StockMovement.objects.create(
            variant=variant,
            quantity_change=quantity,
            balance_after=variant.stock_quantity,
            reason=reason,
            order_ref=order_ref,
            user=user,
            note=f"Restored from order {order_ref} ({reason})"
        )
        return variant
