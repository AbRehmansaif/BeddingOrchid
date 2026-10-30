"""
OrderFinancialsService
======================
All business logic for computing per-order financial figures.
Rules documented exactly as in Section 3 of the spec.

NEVER call this from views or admin classes – always from services.
"""

from decimal import Decimal, ROUND_HALF_UP
from django.utils import timezone
from django.db import transaction

ZERO = Decimal('0.00')
TWO_PLACES = Decimal('0.01')


def _q(value):
    """Quantize to 2 decimal places, rounding half-up."""
    return Decimal(value or 0).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


class OrderFinancialsService:
    """
    Entry point: OrderFinancialsService.calculate(order)
    Returns the saved OrderFinancials instance.
    Idempotent – safe to call multiple times.
    """

    @classmethod
    @transaction.atomic
    def calculate(cls, order):
        """
        Recalculate and persist OrderFinancials for a single order.
        Uses only database values – no Python loops over large querysets.
        """
        from apps.finance.models import (
            OrderFinancials, OrderItemCostSnapshot, CourierCharge,
            ReturnRecord, ReturnItem, FinanceSettings,
        )
        from apps.orders.models import OrderItem

        fs = FinanceSettings.get_settings()

        # -------------------------------------------------------
        # Step 1: Determine if this order counts as revenue
        # -------------------------------------------------------
        is_delivered = order.status == 'delivered'
        has_courier_charge = CourierCharge.objects.filter(order=order).exists()
        is_dispatched = order.status in (
            'dispatched', 'delivered', 'returned', 'refunded'
        ) or has_courier_charge

        # -------------------------------------------------------
        # Step 2: Revenue (Section 3.1)
        # -------------------------------------------------------
        items = list(order.items.all())

        gross_sales = ZERO
        if is_delivered:
            gross_sales = _q(sum(item.line_total for item in items))

        discount_total = _q(order.discount_total) if is_delivered else ZERO

        # Refund amounts from ReturnRecords linked to this delivered order
        refund_total = ZERO
        if is_delivered:
            for rr in order.return_records.all():
                refund_total += _q(rr.refund_amount)

        shipping_charged = ZERO
        if is_delivered and fs.include_shipping_fee_in_revenue:
            shipping_charged = _q(order.shipping_fee)

        cod_fee_charged = ZERO
        if is_delivered and fs.include_cod_fee_in_revenue:
            cod_fee_charged = _q(order.cod_fee)

        net_product_revenue = gross_sales - discount_total - refund_total
        net_revenue = _q(net_product_revenue + shipping_charged + cod_fee_charged)

        # -------------------------------------------------------
        # Step 3: COGS (Section 3.2)
        # -------------------------------------------------------
        product_cost = ZERO
        packaging_cost_items = ZERO
        cost_missing = False

        for item in items:
            try:
                snap = item.cost_snapshot
            except Exception:
                snap = None

            if snap is None:
                cost_missing = True
                continue

            if snap.cost_missing:
                cost_missing = True

            if is_delivered:
                qty = Decimal(item.quantity)
                product_cost += _q(qty * (snap.unit_cost_snapshot + snap.other_cost_snapshot))
                packaging_cost_items += _q(qty * snap.packaging_cost_snapshot)

        # Per-order packaging default if no variant-level packaging
        packaging_cost = packaging_cost_items
        if packaging_cost == ZERO and is_dispatched:
            packaging_cost = _q(fs.default_packaging_cost_per_order)

        # Subtract restocked sellable return items from COGS
        if is_delivered:
            for rr in order.return_records.all():
                for ri in rr.items.filter(condition='sellable'):
                    # recover cost of restocked item
                    product_cost -= _q(
                        Decimal(ri.quantity) * ri.unit_cost_at_return
                    )

        product_cost = max(ZERO, product_cost)

        # -------------------------------------------------------
        # Step 4: Gross Profit (Section 3.3)
        # -------------------------------------------------------
        gross_profit = _q(net_revenue - product_cost)

        # -------------------------------------------------------
        # Step 5: Courier costs (Section 3.4)
        # -------------------------------------------------------
        courier_forward_charge = ZERO
        courier_cod_fee = ZERO
        courier_return_charge = ZERO
        courier_other_charge = ZERO
        is_estimated = False

        if is_dispatched:
            try:
                cc = order.courier_charge
                courier_forward_charge = _q(cc.forward_charge + cc.weight_charge)
                courier_cod_fee = _q(cc.cod_fee)
                courier_return_charge = _q(cc.return_charge)
                courier_other_charge = _q(cc.fuel_surcharge + cc.tax_on_fee + cc.other_charge)
                is_estimated = False  # real charge found
            except Exception:
                # Fall back to rate card estimate
                estimated = cls._estimate_courier_charges(order, fs)
                courier_forward_charge = estimated['forward']
                courier_cod_fee = estimated['cod_fee']
                courier_return_charge = estimated['return_charge']
                courier_other_charge = estimated['other']
                is_estimated = True

        total_courier_cost = _q(
            courier_forward_charge + courier_cod_fee +
            courier_return_charge + courier_other_charge
        )

        # -------------------------------------------------------
        # Step 6: Return & loss costs (Section 3.5)
        # -------------------------------------------------------
        return_loss = ZERO
        for rr in order.return_records.all():
            for ri in rr.items.filter(condition__in=['damaged', 'lost']):
                return_loss += _q(Decimal(ri.quantity) * ri.unit_cost_at_return)
            # Extra shipping for exchanges
            return_loss += _q(rr.extra_shipping_cost)
            # Refunds not recovered (for non-COD)
            if order.payment_method != 'COD':
                return_loss += _q(rr.refund_amount)

        return_loss = max(ZERO, return_loss)

        # -------------------------------------------------------
        # Step 7: Payment fees & tax (Section 3.6)
        # -------------------------------------------------------
        payment_gateway_fee = ZERO
        if order.payment_method != 'COD' and is_delivered:
            payment_gateway_fee = _q(
                net_revenue * (fs.payment_gateway_fee_percent / Decimal('100'))
            )

        sales_tax = ZERO
        if fs.sales_tax_percent > ZERO and is_delivered and net_revenue > ZERO:
            rate = fs.sales_tax_percent / Decimal('100')
            if fs.sales_tax_included_in_prices:
                sales_tax = _q(net_revenue * rate / (1 + rate))
            else:
                sales_tax = _q(net_revenue * rate)

        # -------------------------------------------------------
        # Step 8: Contribution Profit (Section 3.8)
        # -------------------------------------------------------
        contribution_profit_before_ads = _q(
            net_revenue - product_cost - packaging_cost -
            total_courier_cost - payment_gateway_fee - return_loss
        )

        # ad_cost_allocated is set separately by the allocation job; keep existing or zero
        try:
            existing = OrderFinancials.objects.get(order=order)
            ad_cost_allocated = existing.ad_cost_allocated
        except OrderFinancials.DoesNotExist:
            ad_cost_allocated = ZERO

        contribution_profit = _q(contribution_profit_before_ads - ad_cost_allocated)

        # -------------------------------------------------------
        # Step 9: Save
        # -------------------------------------------------------
        financials, _ = OrderFinancials.objects.update_or_create(
            order=order,
            defaults={
                'gross_sales': gross_sales,
                'discount_total': discount_total,
                'refund_total': refund_total,
                'shipping_charged': shipping_charged,
                'cod_fee_charged': cod_fee_charged,
                'net_revenue': net_revenue,
                'product_cost': product_cost,
                'packaging_cost': packaging_cost,
                'courier_forward_charge': courier_forward_charge,
                'courier_cod_fee': courier_cod_fee,
                'courier_return_charge': courier_return_charge,
                'courier_other_charge': courier_other_charge,
                'total_courier_cost': total_courier_cost,
                'payment_gateway_fee': payment_gateway_fee,
                'sales_tax': sales_tax,
                'return_loss': return_loss,
                'ad_cost_allocated': ad_cost_allocated,
                'gross_profit': gross_profit,
                'contribution_profit_before_ads': contribution_profit_before_ads,
                'contribution_profit': contribution_profit,
                'is_estimated': is_estimated,
                'cost_missing': cost_missing,
                'calculated_at': timezone.now(),
            }
        )
        return financials

    calculate_for_order = calculate

    @classmethod
    def _estimate_courier_charges(cls, order, fs):
        """
        Use CourierRate card to estimate charges before the actual statement arrives.
        Returns a dict with forward, cod_fee, return_charge, other.
        """
        from apps.finance.models import CourierRate

        courier = order.courier.lower() if order.courier else ''
        city = order.shipping_city or ''

        # Try city-specific rate first, then courier default, then global default
        rate = (
            CourierRate.objects.filter(
                courier__iexact=courier,
                city_or_zone__iexact=city,
                effective_from__lte=order.placed_at.date()
            ).order_by('-effective_from').first()
            or
            CourierRate.objects.filter(
                courier__iexact=courier,
                city_or_zone='',
                effective_from__lte=order.placed_at.date()
            ).order_by('-effective_from').first()
            or
            CourierRate.objects.filter(
                city_or_zone='',
                effective_from__lte=order.placed_at.date()
            ).order_by('-effective_from').first()
        )

        if rate:
            forward = _q(rate.forward_charge)
            cod_amount = _q(order.grand_total) if order.payment_method == 'COD' else ZERO
            cod_fee = _q(cod_amount * rate.cod_fee_percent / Decimal('100'))
            return_charge = ZERO
            if order.status in ('returned', 'refunded'):
                return_charge = _q(rate.return_charge)
            fuel = _q(forward * rate.fuel_percent / Decimal('100'))
            return {
                'forward': forward,
                'cod_fee': cod_fee,
                'return_charge': return_charge,
                'other': fuel,
            }

        # Absolute fallback: use FinanceSettings defaults
        forward = Decimal('250.00')
        cod_amount = _q(order.grand_total) if order.payment_method == 'COD' else ZERO
        cod_fee = _q(cod_amount * fs.default_cod_fee_percent / Decimal('100'))
        return {
            'forward': forward,
            'cod_fee': cod_fee,
            'return_charge': ZERO,
            'other': ZERO,
        }

    @classmethod
    def snapshot_costs_for_order(cls, order):
        """
        Called at order placement time.
        Creates an OrderItemCostSnapshot for each OrderItem, snapshotting
        the VariantCost effective at the order date.
        Safe to call once – skips items that already have a snapshot.
        """
        from apps.finance.models import OrderItemCostSnapshot, VariantCost

        order_date = order.placed_at.date()

        for item in order.items.all():
            # Skip if already snapshotted
            if hasattr(item, 'cost_snapshot'):
                try:
                    _ = item.cost_snapshot
                    continue
                except Exception:
                    pass

            cost_missing = False
            unit_cost = ZERO
            packaging_cost = ZERO
            other_cost = ZERO

            if item.variant_id:
                vc = (
                    VariantCost.objects
                    .filter(variant_id=item.variant_id, effective_from__lte=order_date)
                    .order_by('-effective_from')
                    .first()
                )
                if vc:
                    unit_cost = vc.unit_cost
                    packaging_cost = vc.packaging_cost
                    other_cost = vc.other_unit_cost
                else:
                    cost_missing = True
            else:
                cost_missing = True

            OrderItemCostSnapshot.objects.get_or_create(
                order_item=item,
                defaults={
                    'unit_cost_snapshot': unit_cost,
                    'packaging_cost_snapshot': packaging_cost,
                    'other_cost_snapshot': other_cost,
                    'cost_missing': cost_missing,
                }
            )
