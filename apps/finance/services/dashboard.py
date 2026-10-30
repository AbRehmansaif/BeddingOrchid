"""
DashboardService
================
Aggregates all data for the finance dashboard.
Reads from DailyFinancialSummary for speed; falls back to OrderFinancials.
All aggregation via DB, no Python loops.
"""

from decimal import Decimal, ROUND_HALF_UP
from django.db import models as db_models
from django.db.models import Sum, Count, Avg, F, Q, Case, When, Value, DecimalField
from django.db.models.functions import Coalesce
from django.utils import timezone
import datetime

ZERO = Decimal('0.00')
TWO = Decimal('0.01')


def _q(v):
    return Decimal(v or 0).quantize(TWO, rounding=ROUND_HALF_UP)


def _pct(numerator, denominator):
    """Safe percentage: 0 if denominator is zero."""
    if not denominator:
        return ZERO
    return _q(Decimal(numerator) / Decimal(denominator) * 100)


def _ratio(numerator, denominator):
    if not denominator:
        return ZERO
    return _q(Decimal(numerator) / Decimal(denominator))


class DashboardService:
    """
    All methods accept date_from, date_to as datetime.date objects.
    They use the delivery_date basis by default (revenue on delivery date).
    """

    @classmethod
    def get_summary(cls, date_from: datetime.date, date_to: datetime.date) -> dict:
        """
        Main dashboard summary. Reads from DailyFinancialSummary.
        Returns a dict of all KPIs for the date range.
        """
        from apps.finance.models import DailyFinancialSummary, AdSpendEntry, OperatingExpense

        rows = DailyFinancialSummary.objects.filter(
            date__range=(date_from, date_to)
        )

        totals = rows.aggregate(
            gross_sales=Coalesce(Sum('gross_sales'), ZERO, output_field=DecimalField()),
            discount_total=Coalesce(Sum('discount_total'), ZERO, output_field=DecimalField()),
            refund_total=Coalesce(Sum('refund_total'), ZERO, output_field=DecimalField()),
            shipping_income=Coalesce(Sum('shipping_income'), ZERO, output_field=DecimalField()),
            cod_fee_income=Coalesce(Sum('cod_fee_income'), ZERO, output_field=DecimalField()),
            net_revenue=Coalesce(Sum('net_revenue'), ZERO, output_field=DecimalField()),
            product_cost=Coalesce(Sum('product_cost'), ZERO, output_field=DecimalField()),
            packaging_cost=Coalesce(Sum('packaging_cost'), ZERO, output_field=DecimalField()),
            gross_profit=Coalesce(Sum('gross_profit'), ZERO, output_field=DecimalField()),
            courier_forward=Coalesce(Sum('courier_forward'), ZERO, output_field=DecimalField()),
            courier_cod_fee=Coalesce(Sum('courier_cod_fee'), ZERO, output_field=DecimalField()),
            courier_return=Coalesce(Sum('courier_return'), ZERO, output_field=DecimalField()),
            courier_other=Coalesce(Sum('courier_other'), ZERO, output_field=DecimalField()),
            total_courier_cost=Coalesce(Sum('total_courier_cost'), ZERO, output_field=DecimalField()),
            return_loss=Coalesce(Sum('return_loss'), ZERO, output_field=DecimalField()),
            payment_gateway_fee=Coalesce(Sum('payment_gateway_fee'), ZERO, output_field=DecimalField()),
            sales_tax=Coalesce(Sum('sales_tax'), ZERO, output_field=DecimalField()),
            ad_spend=Coalesce(Sum('ad_spend'), ZERO, output_field=DecimalField()),
            operating_expenses=Coalesce(Sum('operating_expenses'), ZERO, output_field=DecimalField()),
            contribution_profit_before_ads=Coalesce(Sum('contribution_profit_before_ads'), ZERO, output_field=DecimalField()),
            contribution_profit=Coalesce(Sum('contribution_profit'), ZERO, output_field=DecimalField()),
            net_profit=Coalesce(Sum('net_profit'), ZERO, output_field=DecimalField()),
            orders_placed=Coalesce(Sum('orders_placed'), 0),
            orders_confirmed=Coalesce(Sum('orders_confirmed'), 0),
            orders_dispatched=Coalesce(Sum('orders_dispatched'), 0),
            orders_delivered=Coalesce(Sum('orders_delivered'), 0),
            orders_returned=Coalesce(Sum('orders_returned'), 0),
            orders_cancelled=Coalesce(Sum('orders_cancelled'), 0),
        )

        # Recalculate net profit to include operating expenses properly
        # (DailySummary already stores it, but compute for consistency)
        nr = _q(totals.get('net_revenue') or ZERO)
        cogs = _q(totals.get('product_cost') or ZERO)
        pkg = _q(totals.get('packaging_cost') or ZERO)
        courier = _q(totals.get('total_courier_cost') or ZERO)
        ret_loss = _q(totals.get('return_loss') or ZERO)
        pgw_fee = _q(totals.get('payment_gateway_fee') or ZERO)
        ad_spend = _q(totals.get('ad_spend') or ZERO)
        opex = _q(totals.get('operating_expenses') or ZERO)
        gross_profit = _q(totals.get('gross_profit') or ZERO)

        contrib_before_ads = _q(nr - cogs - pkg - courier - pgw_fee - ret_loss)
        contrib_after_ads = _q(contrib_before_ads - ad_spend)
        net_profit = _q(contrib_after_ads - opex)

        dispatched = totals.get('orders_dispatched', 0) or 0
        delivered = totals.get('orders_delivered', 0) or 0
        returned = totals.get('orders_returned', 0) or 0
        placed = totals.get('orders_placed', 0) or 0
        cancelled = totals.get('orders_cancelled', 0) or 0

        # Platform ROAS comes from AdSpendEntry (not in daily summary breakdown by platform)
        platform_purchases_reported = AdSpendEntry.objects.filter(
            date__range=(date_from, date_to)
        ).aggregate(
            total_spend=Coalesce(Sum('spend_base'), ZERO, output_field=DecimalField()),
            total_platform_value=Coalesce(Sum('purchase_value_reported'), ZERO, output_field=DecimalField()),
            total_platform_purchases=Coalesce(Sum('purchases_reported'), 0),
        )

        platform_spend = _q(platform_purchases_reported['total_spend'])
        platform_value = _q(platform_purchases_reported['total_platform_value'])

        # Metrics
        gross_margin_pct = _pct(gross_profit, nr)
        net_margin_pct = _pct(net_profit, nr)
        delivery_success_rate = _pct(delivered, dispatched)
        return_rate = _pct(returned, delivered)  # customer returns / delivered
        rto_rate = _pct(returned, dispatched)
        cancellation_rate = _pct(cancelled, placed)

        real_roas = _ratio(nr, ad_spend) if ad_spend > ZERO else ZERO
        platform_roas = _ratio(platform_value, platform_spend) if platform_spend > ZERO else ZERO
        real_cpa = _ratio(ad_spend, delivered) if delivered > 0 else ZERO
        platform_cpa = _ratio(platform_spend, platform_purchases_reported['total_platform_purchases']) if platform_purchases_reported['total_platform_purchases'] > 0 else ZERO

        contrib_margin_pct = _pct(contrib_before_ads, nr)
        break_even_roas = _ratio(Decimal('100'), contrib_margin_pct) if contrib_margin_pct > ZERO else ZERO
        break_even_cpa = _ratio(contrib_before_ads, delivered) if delivered > 0 else ZERO

        profit_per_delivered_order = _ratio(net_profit, delivered) if delivered > 0 else ZERO

        return {
            # Revenue lines
            'gross_sales': _q(totals.get('gross_sales') or ZERO),
            'discount_total': _q(totals.get('discount_total') or ZERO),
            'refund_total': _q(totals.get('refund_total') or ZERO),
            'shipping_income': _q(totals.get('shipping_income') or ZERO),
            'cod_fee_income': _q(totals.get('cod_fee_income') or ZERO),
            'net_revenue': nr,

            # COGS
            'product_cost': cogs,
            'packaging_cost': pkg,
            'gross_profit': gross_profit,
            'gross_margin_pct': gross_margin_pct,

            # Courier
            'courier_forward': _q(totals.get('courier_forward') or ZERO),
            'courier_cod_fee': _q(totals.get('courier_cod_fee') or ZERO),
            'courier_return': _q(totals.get('courier_return') or ZERO),
            'courier_other': _q(totals.get('courier_other') or ZERO),
            'total_courier_cost': courier,

            # Losses & fees
            'return_loss': ret_loss,
            'payment_gateway_fee': pgw_fee,
            'sales_tax': _q(totals.get('sales_tax') or ZERO),

            # Profit levels
            'contribution_profit_before_ads': contrib_before_ads,
            'contribution_profit': contrib_after_ads,
            'ad_spend': ad_spend,
            'operating_expenses': opex,
            'net_profit': net_profit,
            'net_margin_pct': net_margin_pct,

            # Order counts
            'orders_placed': placed,
            'orders_confirmed': totals.get('orders_confirmed', 0) or 0,
            'orders_dispatched': dispatched,
            'orders_delivered': delivered,
            'orders_returned': returned,
            'orders_cancelled': cancelled,

            # KPI metrics
            'delivery_success_rate': delivery_success_rate,
            'return_rate': return_rate,
            'rto_rate': rto_rate,
            'cancellation_rate': cancellation_rate,
            'real_roas': real_roas,
            'platform_roas': platform_roas,
            'real_cpa': real_cpa,
            'platform_cpa': platform_cpa,
            'break_even_roas': break_even_roas,
            'break_even_cpa': break_even_cpa,
            'profit_per_delivered_order': profit_per_delivered_order,
            'contrib_margin_pct': contrib_margin_pct,
        }

    @classmethod
    def get_by_product(cls, date_from, date_to):
        """Profitability by product variant."""
        from apps.finance.models import OrderItemCostSnapshot
        from apps.orders.models import OrderItem

        qs = OrderItem.objects.filter(
            order__status='delivered',
            order__placed_at__date__range=(date_from, date_to),
        ).select_related('product', 'variant', 'cost_snapshot').values(
            'product__id', 'product__name', 'variant__sku',
        ).annotate(
            units=Sum('quantity'),
            revenue=Coalesce(Sum('line_total'), ZERO, output_field=DecimalField()),
            cogs=Coalesce(
                Sum(
                    F('quantity') * F('cost_snapshot__unit_cost_snapshot'),
                    output_field=DecimalField()
                ), ZERO, output_field=DecimalField()
            ),
        ).order_by('-revenue')

        return qs

    @classmethod
    def get_by_campaign(cls, date_from, date_to):
        """Ad performance by campaign."""
        from apps.finance.models import AdSpendEntry

        return AdSpendEntry.objects.filter(
            date__range=(date_from, date_to)
        ).values('campaign', 'platform').annotate(
            spend=Coalesce(Sum('spend_base'), ZERO, output_field=DecimalField()),
            platform_purchases=Sum('purchases_reported'),
            platform_value=Coalesce(Sum('purchase_value_reported'), ZERO, output_field=DecimalField()),
            impressions=Sum('impressions'),
            clicks=Sum('clicks'),
        ).order_by('-spend')

    @classmethod
    def get_by_courier(cls, date_from, date_to):
        """Profitability by courier."""
        from apps.finance.models import OrderFinancials
        from apps.orders.models import Order

        return Order.objects.filter(
            status__in=['dispatched', 'delivered', 'returned', 'refunded'],
            placed_at__date__range=(date_from, date_to),
        ).values('courier').annotate(
            orders=Count('id'),
            delivered=Sum(
                Case(When(status='delivered', then=1), default=0, output_field=db_models.IntegerField())
            ),
            returned=Sum(
                Case(When(status='returned', then=1), default=0, output_field=db_models.IntegerField())
            ),
            total_courier_cost=Coalesce(
                Sum('financials__total_courier_cost'), ZERO, output_field=DecimalField()
            ),
            net_revenue=Coalesce(
                Sum('financials__net_revenue'), ZERO, output_field=DecimalField()
            ),
        ).order_by('-orders')

    @classmethod
    def get_by_city(cls, date_from, date_to):
        """Profitability by shipping city."""
        from apps.orders.models import Order

        return Order.objects.filter(
            placed_at__date__range=(date_from, date_to),
        ).values('shipping_city').annotate(
            orders=Count('id'),
            delivered=Sum(
                Case(When(status='delivered', then=1), default=0, output_field=db_models.IntegerField())
            ),
            returned=Sum(
                Case(When(status='returned', then=1), default=0, output_field=db_models.IntegerField())
            ),
            net_revenue=Coalesce(
                Sum('financials__net_revenue'), ZERO, output_field=DecimalField()
            ),
            total_courier_cost=Coalesce(
                Sum('financials__total_courier_cost'), ZERO, output_field=DecimalField()
            ),
            contribution_profit=Coalesce(
                Sum('financials__contribution_profit_before_ads'), ZERO, output_field=DecimalField()
            ),
        ).order_by('-orders')

    @classmethod
    def get_alerts(cls, date_from, date_to):
        """
        Returns actionable alerts for the dashboard alert row.
        """
        from apps.finance.models import (
            OrderFinancials, OrderItemCostSnapshot, DailyFinancialSummary,
            CourierSettlement, FinanceSettings,
        )
        from apps.orders.models import Order

        fs = FinanceSettings.get_settings()
        alerts = []

        # 1. Missing costs
        missing_cost_count = OrderItemCostSnapshot.objects.filter(cost_missing=True).count()
        if missing_cost_count:
            alerts.append({
                'level': 'error',
                'message': f"{missing_cost_count} order items have no cost data — profit figures are overstated.",
                'action_url': '/admin/finance/orderitemcostsnapshot/?cost_missing__exact=1',
            })

        # 2. Estimated courier charges
        estimated_count = OrderFinancials.objects.filter(
            is_estimated=True,
            order__status__in=['delivered', 'dispatched'],
            order__placed_at__date__range=(date_from, date_to),
        ).count()
        if estimated_count:
            alerts.append({
                'level': 'warning',
                'message': f"{estimated_count} orders still use estimated courier charges. Import courier statements to confirm.",
                'action_url': '/admin/finance/couriercharge/?is_unmatched__exact=0',
            })

        # 3. Days with missing ad spend in range
        days_range = (date_to - date_from).days + 1
        days_with_spend = DailyFinancialSummary.objects.filter(
            date__range=(date_from, date_to),
            ad_spend__gt=0
        ).count()
        missing_ad_days = days_range - days_with_spend
        if missing_ad_days > 0:
            alerts.append({
                'level': 'warning',
                'message': f"{missing_ad_days} day(s) in this period have no ad spend recorded.",
                'action_url': '/admin/finance/adspendentry/add/',
            })

        # 4. Overdue settlements
        cutoff = timezone.now().date() - datetime.timedelta(days=fs.settlement_overdue_days)
        overdue = CourierSettlement.objects.filter(
            status='pending',
            statement_date__lt=cutoff,
        ).count()
        if overdue:
            alerts.append({
                'level': 'error',
                'message': f"{overdue} courier settlement(s) overdue by more than {fs.settlement_overdue_days} days.",
                'action_url': '/admin/finance/couriersettlement/?status__exact=pending',
            })

        return alerts

    @classmethod
    def get_cash_view(cls, date_from, date_to):
        """Section 3.9: Cash position."""
        from apps.finance.models import CourierSettlement, AdSpendEntry, OperatingExpense
        from apps.orders.models import Order

        # COD receivable = delivered orders not yet in a received settlement
        cod_receivable_by_courier = (
            Order.objects.filter(
                status='delivered',
                payment_method='COD',
            )
            .exclude(
                courier_charge__settlement__status='received'
            )
            .values('courier')
            .annotate(
                cod_receivable=Coalesce(Sum('grand_total'), ZERO, output_field=DecimalField()),
                order_count=Count('id'),
            )
        )

        # Cash received from settlements in period
        cash_received = CourierSettlement.objects.filter(
            paid_on__range=(date_from, date_to),
            status='received',
        ).aggregate(
            total=Coalesce(Sum('net_paid_to_us'), ZERO, output_field=DecimalField())
        )['total']

        # Cash out in period
        ad_spend_out = AdSpendEntry.objects.filter(
            date__range=(date_from, date_to)
        ).aggregate(total=Coalesce(Sum('spend_base'), ZERO, output_field=DecimalField()))['total']

        opex_out = OperatingExpense.objects.filter(
            date__range=(date_from, date_to)
        ).aggregate(total=Coalesce(Sum('amount'), ZERO, output_field=DecimalField()))['total']

        cash_in = _q(cash_received or ZERO)
        cash_out = _q((ad_spend_out or ZERO) + (opex_out or ZERO))

        return {
            'cod_receivable_by_courier': list(cod_receivable_by_courier),
            'total_cod_receivable': _q(
                sum(r['cod_receivable'] for r in cod_receivable_by_courier)
            ),
            'cash_received': cash_in,
            'cash_out': cash_out,
            'net_cash_movement': _q(cash_in - cash_out),
        }

    @classmethod
    def get_daily_trend(cls, date_from, date_to):
        """Daily trend data for charts."""
        from apps.finance.models import DailyFinancialSummary

        return list(
            DailyFinancialSummary.objects.filter(
                date__range=(date_from, date_to)
            ).values(
                'date', 'net_revenue', 'ad_spend', 'net_profit',
                'orders_delivered', 'orders_dispatched', 'orders_returned'
            ).order_by('date')
        )
