from celery import shared_task
from apps.orders.models import Order
from .services import NotificationService

@shared_task
def send_order_placed_async(order_id):
    try:
        order = Order.objects.get(id=order_id)
        NotificationService.send_order_placed_notification(order)
    except Order.DoesNotExist:
        pass

@shared_task
def send_order_status_update_async(order_id, old_status, new_status):
    try:
        order = Order.objects.get(id=order_id)
        NotificationService.send_order_status_update(order, old_status, new_status)
    except Order.DoesNotExist:
        pass
