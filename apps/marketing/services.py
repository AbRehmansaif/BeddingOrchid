import time
import requests
from django.conf import settings
from .models import MetaEventLog
from apps.core.models import SiteSettings
from apps.core.utils import hash_sha256, normalize_phone_pk

class MetaConversionsApiService:
    """
    Sends server-side events directly to Meta Graph API for Conversions API (CAPI).
    Deduplicates with browser Pixel via matching event_id.
    """
    GRAPH_API_VERSION = 'v19.0'

    @classmethod
    def send_purchase_event(cls, order) -> bool:
        site_settings = SiteSettings.get_settings()
        pixel_id = site_settings.meta_pixel_id or getattr(settings, 'META_PIXEL_ID', '')
        access_token = site_settings.meta_capi_access_token or getattr(settings, 'META_CAPI_ACCESS_TOKEN', '')

        # User data hashed
        phone_norm = normalize_phone_pk(order.customer_phone or order.shipping_phone)
        user_data = {
            'ph': [hash_sha256(phone_norm)] if phone_norm else [],
            'fn': [hash_sha256(order.customer_name)] if order.customer_name else [],
            'ct': [hash_sha256(order.shipping_city)] if order.shipping_city else [],
            'country': [hash_sha256('pk')],
            'client_ip_address': order.ip_address or '',
            'client_user_agent': order.user_agent or '',
        }
        if order.customer_email:
            user_data['em'] = [hash_sha256(order.customer_email)]
        if order.fbp:
            user_data['fbp'] = order.fbp
        if order.fbc:
            user_data['fbc'] = order.fbc

        # Contents payload
        contents = []
        for item in order.items.all():
            contents.append({
                'id': item.variant_sku or str(item.product_id),
                'quantity': item.quantity,
                'item_price': float(item.unit_price)
            })

        custom_data = {
            'currency': 'PKR',
            'value': float(order.grand_total),
            'order_id': order.order_number,
            'content_type': 'product',
            'contents': contents,
        }

        event_payload = {
            'event_name': 'Purchase',
            'event_time': int(time.time()),
            'event_id': order.order_number, # Shared deduplication key with browser Pixel
            'action_source': 'website',
            'user_data': user_data,
            'custom_data': custom_data,
        }

        # If test code configured
        test_code = site_settings.meta_test_event_code or getattr(settings, 'META_TEST_EVENT_CODE', '')

        data_body = {
            'data': [event_payload],
        }
        if test_code:
            data_body['test_event_code'] = test_code

        # Log event payload
        log = MetaEventLog.objects.create(
            event_name='Purchase',
            event_id=order.order_number,
            payload=data_body
        )

        if not pixel_id or not access_token:
            # Running in local or stub mode
            log.response_body = "Local/Stub mode: META_PIXEL_ID or META_CAPI_ACCESS_TOKEN not configured."
            log.is_success = True
            log.save()
            return True

        url = f"https://graph.facebook.com/{cls.GRAPH_API_VERSION}/{pixel_id}/events?access_token={access_token}"
        try:
            res = requests.post(url, json=data_body, timeout=5)
            log.response_status = res.status_code
            log.response_body = res.text
            log.is_success = res.status_code == 200
            log.save()
            return res.status_code == 200
        except Exception as e:
            log.response_body = f"Exception during request: {str(e)}"
            log.is_success = False
            log.save()
            return False
