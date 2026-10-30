"""
Finance signals: queue recalculation whenever order data changes.
All heavy work is done in Celery, never blocking the request cycle.
"""

from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver


# -----------------------------------------------------------------------
# Order signals → queue financials recalculation
# -----------------------------------------------------------------------

def _queue_recalc(order_id):
    """Queue recalculation without importing tasks at module load time."""
    try:
        from apps.finance.tasks import recalculate_order_financials
        recalculate_order_financials.delay(order_id)
    except Exception:
        # Fallback to sync recalculation if Redis broker is offline / in testing
        try:
            from apps.finance.services import OrderFinancialsService
            from apps.orders.models import Order
            order = Order.objects.filter(pk=order_id).first()
            if order:
                OrderFinancialsService.calculate(order)
        except Exception:
            pass


@receiver(post_save, sender='orders.Order')
def order_saved(sender, instance, created, **kwargs):
    if created:
        # Snapshot costs immediately (sync, fast)
        try:
            from apps.finance.services import OrderFinancialsService
            # items may not exist yet if saved before items; signal fires again after add
        except Exception:
            pass
    # Always queue recalc on any save
    _queue_recalc(instance.pk)


@receiver(post_save, sender='orders.OrderItem')
def order_item_saved(sender, instance, created, **kwargs):
    if created:
        # Take cost snapshot immediately
        try:
            from apps.finance.services import OrderFinancialsService
            OrderFinancialsService.snapshot_costs_for_order(instance.order)
        except Exception:
            pass
    _queue_recalc(instance.order_id)


@receiver(post_delete, sender='orders.OrderItem')
def order_item_deleted(sender, instance, **kwargs):
    _queue_recalc(instance.order_id)


# -----------------------------------------------------------------------
# Courier charge / return / ad spend signals → rebuild daily summary
# -----------------------------------------------------------------------

@receiver(post_save, sender='finance.CourierCharge')
def courier_charge_saved(sender, instance, **kwargs):
    if instance.order_id:
        _queue_recalc(instance.order_id)


@receiver(post_save, sender='finance.ReturnRecord')
def return_record_saved(sender, instance, **kwargs):
    _queue_recalc(instance.order_id)


@receiver(post_save, sender='finance.ReturnItem')
def return_item_saved(sender, instance, **kwargs):
    _queue_recalc(instance.return_record.order_id)


@receiver(post_save, sender='finance.AdSpendEntry')
def ad_spend_saved(sender, instance, **kwargs):
    try:
        from apps.finance.tasks import rebuild_daily_summary
        rebuild_daily_summary.delay(
            instance.date.isoformat(),
            instance.date.isoformat(),
        )
    except Exception:
        pass


@receiver(post_save, sender='finance.OperatingExpense')
def opex_saved(sender, instance, **kwargs):
    try:
        from apps.finance.tasks import rebuild_daily_summary
        rebuild_daily_summary.delay(
            instance.date.isoformat(),
            instance.date.isoformat(),
        )
    except Exception:
        pass
