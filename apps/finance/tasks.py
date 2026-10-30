"""
Finance Celery Tasks
====================
All background jobs for finance calculations.
"""

from celery import shared_task
from django.utils import timezone
import datetime


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def recalculate_order_financials(self, order_id: int):
    """
    Recalculate OrderFinancials for a single order.
    Idempotent — safe to call multiple times.
    Also rebuilds the daily summary for the order's date.
    """
    try:
        from apps.orders.models import Order
        from apps.finance.services import OrderFinancialsService
        from apps.finance.services.summary import DailySummaryService

        order = Order.objects.select_related().get(pk=order_id)
        OrderFinancialsService.calculate(order)

        order_date = order.placed_at.date()
        DailySummaryService.rebuild(order_date, order_date)

    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=2)
def rebuild_daily_summary(self, date_from_iso: str, date_to_iso: str):
    """
    Rebuild DailyFinancialSummary for a date range.
    Called when ad spend or operating expenses are saved.
    """
    try:
        from apps.finance.services.summary import DailySummaryService
        date_from = datetime.date.fromisoformat(date_from_iso)
        date_to = datetime.date.fromisoformat(date_to_iso)
        DailySummaryService.rebuild(date_from, date_to)
    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task
def nightly_rebuild_summaries():
    """
    Nightly Celery beat task: rebuild last 7 days of summaries.
    Also pulls latest Meta ad data.
    """
    from apps.finance.services.summary import DailySummaryService
    today = timezone.now().date()
    seven_days_ago = today - datetime.timedelta(days=7)
    DailySummaryService.rebuild(seven_days_ago, today)


@shared_task
def pull_meta_ad_spend():
    """
    Pull Meta Ads insights for the last 7 days.
    Idempotent: updates existing records.
    """
    try:
        from apps.finance.importers.meta_ads import MetaAdsImporter
        importer = MetaAdsImporter()
        today = timezone.now().date()
        date_from = today - datetime.timedelta(days=7)
        result = importer.pull(date_from, today)
        return result
    except Exception as e:
        return {'error': str(e)}


@shared_task
def allocate_ad_spend_to_orders(date_from_iso: str, date_to_iso: str):
    """
    Allocate period ad spend to individual orders.
    Method: order count or revenue share (from FinanceSettings).
    """
    from apps.finance.models import FinanceSettings, OrderFinancials, AdSpendEntry
    from apps.orders.models import Order
    from django.db.models import Sum, Count, DecimalField
    from django.db.models.functions import Coalesce
    from decimal import Decimal

    fs = FinanceSettings.get_settings()
    date_from = datetime.date.fromisoformat(date_from_iso)
    date_to = datetime.date.fromisoformat(date_to_iso)

    total_ad_spend = AdSpendEntry.objects.filter(
        date__range=(date_from, date_to)
    ).aggregate(
        total=Coalesce(Sum('spend_base'), Decimal('0'), output_field=DecimalField())
    )['total']

    if total_ad_spend == 0:
        return {'allocated': 0}

    delivered_orders = Order.objects.filter(
        status='delivered',
        placed_at__date__range=(date_from, date_to),
    )

    if fs.ad_cost_allocation_method == 'order_count':
        count = delivered_orders.count()
        if count == 0:
            return {'allocated': 0}
        per_order = (total_ad_spend / count).quantize(Decimal('0.01'))
        for order in delivered_orders:
            OrderFinancials.objects.filter(order=order).update(
                ad_cost_allocated=per_order,
                contribution_profit=order.financials.contribution_profit_before_ads - per_order,
            )
        return {'allocated': count, 'per_order': float(per_order)}

    else:  # revenue share
        total_revenue = delivered_orders.aggregate(
            total=Coalesce(Sum('financials__net_revenue'), Decimal('0'), output_field=DecimalField())
        )['total']
        if not total_revenue:
            return {'allocated': 0}
        for order in delivered_orders.select_related('financials'):
            try:
                fin = order.financials
                share = (fin.net_revenue / total_revenue) * total_ad_spend
                share = share.quantize(Decimal('0.01'))
                fin.ad_cost_allocated = share
                fin.contribution_profit = fin.contribution_profit_before_ads - share
                fin.save(update_fields=['ad_cost_allocated', 'contribution_profit'])
            except Exception:
                continue
        return {'allocated': delivered_orders.count()}
