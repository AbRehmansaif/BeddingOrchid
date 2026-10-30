import logging
from django.core.mail import send_mail
from django.conf import settings
from apps.core.models import SiteSettings

logger = logging.getLogger(__name__)

class NotificationService:
    @classmethod
    def send_order_placed_notification(cls, order):
        """Sends order confirmation to customer and notification to store admin."""
        site_settings = SiteSettings.get_settings()
        subject = f"Order Confirmed: {order.order_number} - {site_settings.store_name}"
        
        message_lines = [
            f"Dear {order.customer_name},",
            "",
            f"Thank you for shopping at {site_settings.store_name}! We have received your order.",
            f"Order Number: {order.order_number}",
            f"Payment Method: Cash on Delivery (COD)",
            f"Grand Total: Rs. {order.grand_total:,.0f}",
            "",
            "Delivery Address:",
            f"{order.shipping_full_name}",
            f"{order.full_shipping_address}",
            f"Phone: {order.shipping_phone}",
            "",
            "We are preparing your parcel for dispatch. Our courier partner will deliver to your doorstep.",
            f"For inquiries, contact us on WhatsApp: {site_settings.whatsapp_number}",
            "",
            f"Warm regards,",
            f"{site_settings.store_name}"
        ]
        body = "\n".join(message_lines)

        recipient_email = order.customer_email
        if recipient_email:
            try:
                send_mail(
                    subject=subject,
                    message=body,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[recipient_email],
                    fail_silently=True
                )
            except Exception as e:
                logger.warning(f"Could not send order confirmation email: {e}")

        # Also trigger SMS/WhatsApp stub
        cls.send_sms_or_whatsapp(
            phone=order.shipping_phone or order.customer_phone,
            text=f"Hi {order.customer_name}, your {site_settings.store_name} order {order.order_number} of Rs. {order.grand_total:,.0f} (COD) is confirmed! Track here: https://{settings.STORE_DOMAIN}/track-order/?order_number={order.order_number}"
        )

    @classmethod
    def send_order_status_update(cls, order, old_status, new_status):
        site_settings = SiteSettings.get_settings()
        status_readable = dict(order.STATUS_CHOICES).get(new_status, new_status.title())

        tracking_info = ""
        if order.tracking_number:
            tracking_info = f"Courier: {order.courier or 'Courier'}\nTracking Number: {order.tracking_number}\nTracking URL: {order.tracking_url or 'See portal'}\n"

        body = (
            f"Dear {order.customer_name},\n\n"
            f"Your order {order.order_number} status has been updated to: {status_readable}.\n\n"
            f"{tracking_info}"
            f"Thank you for choosing {site_settings.store_name}."
        )

        if order.customer_email:
            try:
                send_mail(
                    subject=f"Update on your Order {order.order_number} - {status_readable}",
                    message=body,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[order.customer_email],
                    fail_silently=True
                )
            except Exception as e:
                logger.warning(f"Could not send status update email: {e}")

        cls.send_sms_or_whatsapp(
            phone=order.shipping_phone or order.customer_phone,
            text=f"Update: Order {order.order_number} is now {status_readable}. {site_settings.store_name}"
        )

    @classmethod
    def send_sms_or_whatsapp(cls, phone: str, text: str):
        """
        Pluggable SMS & WhatsApp messaging provider stub.
        Ready to connect with Twilio, Infobip, Brandverse, or WhatsApp Cloud API.
        """
        logger.info(f"[SMS/WhatsApp Provider Stub] To: {phone} | Message: {text}")
        return True
