"""
DailySummaryService
===================
Rebuilds the DailyFinancialSummary table for a date range.
Called nightly by Celery beat and on demand.
Idempotent — safe to run multiple times.
"""

from decimal import Decimal
import datetime
from django.db.models import Sum, Count, Q, Case, When, DecimalField, IntegerField
from django.db.models.functions import Coalesce
from django.utils import timezone

ZERO = Decimal('0.00')


class DailySummaryService:

    @classmethod
    def rebuild(cls, date_from: datetime.date, date_to: datetime.date):
        """
        Rebuild DailyFinancialSummary rows for each date in [date_from, date_to].
        """
        from apps.finance.models import (
            DailyFinancialSummary, OrderFinancials, AdSpendEntry, OperatingExpense,
        )
        from apps.orders.models import Order

        current = date_from
        while current <= date_to:
            cls._rebuild_day(current)
            current += datetime.timedelta(days=1)

    rebuild_range = rebuild

    @classmethod
    def _rebuild_day(cls, date: datetime.date):
        from apps.finance.models import (
            DailyFinancialSummary, OrderFinancials, AdSpendEntry, OperatingExpense,
        )
        from apps.orders.models import Order

        # ---- Order counts (by placed_at date) ----
        order_agg = Order.objects.filter(
            placed_at__date=date
        ).aggregate(
            placed=Count('id'),
            confirmed=Sum(Case(When(status='confirmed', then=1), default=0, output_field=IntegerField())),
            dispatched=Sum(Case(When(status__in=['dispatched','delivered','returned','refunded'], then=1), default=0, output_field=IntegerField())),
            delivered=Sum(Case(When(status='delivered', then=1), default=0, output_field=IntegerField())),
            returned=Sum(Case(When(status__in=['returned','refunded'], then=1), default=0, output_field=IntegerField())),
            cancelled=Sum(Case(When(status='cancelled', then=1), default=0, output_field=IntegerField())),
        )

        # ---- Financial aggregates for all orders placed on this date ----
        fin_agg = OrderFinancials.objects.filter(
            order__placed_at__date=date,
        ).aggregate(
            gross_sales=Coalesce(Sum('gross_sales'), ZERO, output_field=DecimalField()),
            discount_total=Coalesce(Sum('discount_total'), ZERO, output_field=DecimalField()),
            refund_total=Coalesce(Sum('refund_total'), ZERO, output_field=DecimalField()),
            shipping_income=Coalesce(Sum('shipping_charged'), ZERO, output_field=DecimalField()),
            cod_fee_income=Coalesce(Sum('cod_fee_charged'), ZERO, output_field=DecimalField()),
            net_revenue=Coalesce(Sum('net_revenue'), ZERO, output_field=DecimalField()),
            product_cost=Coalesce(Sum('product_cost'), ZERO, output_field=DecimalField()),
            packaging_cost=Coalesce(Sum('packaging_cost'), ZERO, output_field=DecimalField()),
            gross_profit=Coalesce(Sum('gross_profit'), ZERO, output_field=DecimalField()),
            courier_forward=Coalesce(Sum('courier_forward_charge'), ZERO, output_field=DecimalField()),
            courier_cod_fee=Coalesce(Sum('courier_cod_fee'), ZERO, output_field=DecimalField()),
            courier_return=Coalesce(Sum('courier_return_charge'), ZERO, output_field=DecimalField()),
            courier_other=Coalesce(Sum('courier_other_charge'), ZERO, output_field=DecimalField()),
            total_courier_cost=Coalesce(Sum('total_courier_cost'), ZERO, output_field=DecimalField()),
            return_loss=Coalesce(Sum('return_loss'), ZERO, output_field=DecimalField()),
            payment_gateway_fee=Coalesce(Sum('payment_gateway_fee'), ZERO, output_field=DecimalField()),
            sales_tax=Coalesce(Sum('sales_tax'), ZERO, output_field=DecimalField()),
            contrib_before_ads=Coalesce(Sum('contribution_profit_before_ads'), ZERO, output_field=DecimalField()),
        )

        total_courier = Decimal(fin_agg['total_courier_cost'] or 0)

        # ---- Ad spend ----
        ad_spend = AdSpendEntry.objects.filter(date=date).aggregate(
            total=Coalesce(Sum('spend_base'), ZERO, output_field=DecimalField())
        )['total'] or ZERO

        # ---- Operating expenses (spread recurring daily) ----
        opex = cls._get_daily_opex(date)

        # ---- Contribution & net profit ----
        nr = Decimal(fin_agg['net_revenue'] or 0)
        cogs = Decimal(fin_agg['product_cost'] or 0)
        pkg = Decimal(fin_agg['packaging_cost'] or 0)
        ret_loss = Decimal(fin_agg['return_loss'] or 0)
        pgw_fee = Decimal(fin_agg['payment_gateway_fee'] or 0)

        contrib_before = nr - cogs - pkg - total_courier - pgw_fee - ret_loss
        contrib_after = contrib_before - Decimal(ad_spend)
        net_profit = contrib_after - Decimal(opex)

        # ---- Quality flags ----
        has_missing = OrderFinancials.objects.filter(
            order__placed_at__date=date, cost_missing=True
        ).exists()
        has_estimated = OrderFinancials.objects.filter(
            order__placed_at__date=date, is_estimated=True
        ).exists()
        has_no_ad = (Decimal(ad_spend) == ZERO)

        DailyFinancialSummary.objects.update_or_create(
            date=date,
            defaults={
                'orders_placed': order_agg.get('placed') or 0,
                'orders_confirmed': order_agg.get('confirmed') or 0,
                'orders_dispatched': order_agg.get('dispatched') or 0,
                'orders_delivered': order_agg.get('delivered') or 0,
                'orders_returned': order_agg.get('returned') or 0,
                'orders_cancelled': order_agg.get('cancelled') or 0,

                'gross_sales': Decimal(fin_agg['gross_sales'] or 0),
                'discount_total': Decimal(fin_agg['discount_total'] or 0),
                'refund_total': Decimal(fin_agg['refund_total'] or 0),
                'shipping_income': Decimal(fin_agg['shipping_income'] or 0),
                'cod_fee_income': Decimal(fin_agg['cod_fee_income'] or 0),
                'net_revenue': nr,
                'product_cost': cogs,
                'packaging_cost': pkg,
                'gross_profit': Decimal(fin_agg['gross_profit'] or 0),

                'courier_forward': Decimal(fin_agg['courier_forward'] or 0),
                'courier_cod_fee': Decimal(fin_agg['courier_cod_fee'] or 0),
                'courier_return': Decimal(fin_agg['courier_return'] or 0),
                'courier_other': Decimal(fin_agg['courier_other'] or 0),
                'total_courier_cost': total_courier,

                'return_loss': ret_loss,
                'payment_gateway_fee': pgw_fee,
                'sales_tax': Decimal(fin_agg['sales_tax'] or 0),

                'ad_spend': Decimal(ad_spend),
                'operating_expenses': Decimal(opex),
                'contribution_profit_before_ads': contrib_before,
                'contribution_profit': contrib_after,
                'net_profit': net_profit,

                'has_missing_costs': has_missing,
                'has_estimated_charges': has_estimated,
                'has_missing_ad_spend': has_no_ad,
            }
        )

    @classmethod
    def _get_daily_opex(cls, date: datetime.date) -> Decimal:
        """
        Calculate the operating expenses attributable to a given day.
        One-time expenses: count on their date.
        Monthly recurring: amount / days-in-month.
        Weekly: amount / 7.
        Yearly: amount / 365.
        """
        from apps.finance.models import OperatingExpense
        import calendar

        # One-time expenses on this exact date
        one_time = OperatingExpense.objects.filter(
            date=date, is_recurring=False
        ).aggregate(total=Coalesce(Sum('amount'), ZERO, output_field=DecimalField()))['total'] or ZERO

        # Monthly recurring: find all monthly expenses where date.month/year matches
        monthly = OperatingExpense.objects.filter(
            date__year=date.year, date__month=date.month,
            is_recurring=True, recurrence='monthly',
        ).aggregate(total=Coalesce(Sum('amount'), ZERO, output_field=DecimalField()))['total'] or ZERO

        days_in_month = calendar.monthrange(date.year, date.month)[1]
        daily_monthly = Decimal(monthly) / Decimal(days_in_month)

        # Weekly recurring
        weekly = OperatingExpense.objects.filter(
            is_recurring=True, recurrence='weekly',
        ).aggregate(total=Coalesce(Sum('amount'), ZERO, output_field=DecimalField()))['total'] or ZERO
        daily_weekly = Decimal(weekly) / Decimal(7)

        # Yearly recurring
        yearly = OperatingExpense.objects.filter(
            is_recurring=True, recurrence='yearly',
        ).aggregate(total=Coalesce(Sum('amount'), ZERO, output_field=DecimalField()))['total'] or ZERO
        daily_yearly = Decimal(yearly) / Decimal(365)

        return (
            Decimal(one_time) + daily_monthly + daily_weekly + daily_yearly
        ).quantize(Decimal('0.01'))
