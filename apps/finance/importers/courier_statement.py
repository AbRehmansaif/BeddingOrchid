"""
Courier Statement Importer
==========================
Parses statements from Pakistani couriers (TCS, Leopards, PostEx, Trax, M&P)
or generic formats. Matches rows to existing Orders by tracking number,
updates or creates CourierCharge records, and handles unmatched rows.
"""

import csv
import io
import datetime
from decimal import Decimal, InvalidOperation
from django.utils import timezone

from apps.orders.models import Order
from apps.finance.models import CourierCharge, CourierSettlement

ZERO = Decimal('0.00')

COURIER_PRESETS = {
    'tcs': {
        'tracking': ['cn', 'consignment no', 'tracking no', 'cn number', 'cwb'],
        'order_number': ['reference', 'order no', 'ref no', 'order id'],
        'status': ['status', 'delivery status', 'current status'],
        'delivered_date': ['delivery date', 'delivery_date', 'delivered on'],
        'weight': ['weight', 'charged weight', 'wt'],
        'cod_collected': ['cod amount', 'cod collected', 'collected amount', 'cash collected'],
        'forward_charge': ['freight', 'delivery charge', 'courier fee', 'shipping charge', 'rate'],
        'cod_fee': ['cod fee', 'handling fee', 'cod charges', 'cash fee'],
        'return_charge': ['return charge', 'rto charge', 'return fee'],
        'fuel_surcharge': ['fuel', 'fuel surcharge', 'fsc'],
        'gst': ['gst', 'sales tax', 'tax'],
    },
    'leopards': {
        'tracking': ['cn number', 'cn', 'tracking', 'tracking_no', 'consignment'],
        'order_number': ['order ref', 'client ref', 'reference no', 'order number'],
        'status': ['status', 'parcel status', 'delivery status'],
        'delivered_date': ['delivery date', 'delivered date'],
        'weight': ['weight', 'wt (kg)'],
        'cod_collected': ['cod amt', 'cod amount', 'amount collected'],
        'forward_charge': ['delivery charges', 'freight charges', 'shipping charges'],
        'cod_fee': ['cod charges', 'commission', 'cod fee'],
        'return_charge': ['return charges', 'rto charges'],
        'fuel_surcharge': ['fuel surcharge'],
        'gst': ['gst', 'tax amount'],
    },
    'postex': {
        'tracking': ['tracking code', 'tracking no', 'cn', 'waybill'],
        'order_number': ['order id', 'order ref', 'merchant reference'],
        'status': ['status', 'transaction status'],
        'delivered_date': ['delivered at', 'delivery date'],
        'weight': ['weight', 'weight kg'],
        'cod_collected': ['invoice amount', 'order amount', 'collected amount'],
        'forward_charge': ['delivery fee', 'shipping fee', 'service charge'],
        'cod_fee': ['handling charges', 'commission', 'cod fee'],
        'return_charge': ['return delivery fee', 'return charge'],
        'fuel_surcharge': ['fuel charge'],
        'gst': ['tax', 'gst'],
    },
    'trax': {
        'tracking': ['tracking_number', 'consignment_number', 'tracking number'],
        'order_number': ['order_id', 'shipper_reference_number', 'order reference'],
        'status': ['status', 'current_status'],
        'delivered_date': ['delivered_date', 'date'],
        'weight': ['weight'],
        'cod_collected': ['amount_collected', 'cod_amount'],
        'forward_charge': ['charges', 'shipping_charge', 'delivery_charge'],
        'cod_fee': ['cod_fee', 'cash_collection_fee'],
        'return_charge': ['return_fee', 'return_charge'],
        'fuel_surcharge': ['fuel_surcharge'],
        'gst': ['tax'],
    },
    'mnp': {
        'tracking': ['consignment no', 'cn number', 'tracking'],
        'order_number': ['reference no', 'order no'],
        'status': ['delivery status', 'status'],
        'delivered_date': ['delivery date'],
        'weight': ['weight'],
        'cod_collected': ['cod amount'],
        'forward_charge': ['freight charge', 'service charge'],
        'cod_fee': ['cod charges'],
        'return_charge': ['return charge'],
        'fuel_surcharge': ['fuel'],
        'gst': ['gst'],
    },
}


def _clean_decimal(value, default=ZERO):
    if value is None:
        return default
    val_str = str(value).replace(',', '').replace('Rs', '').replace('PKR', '').replace('$', '').strip()
    if not val_str or val_str.lower() in ('none', 'null', 'nan', '-'):
        return default
    try:
        return Decimal(val_str)
    except (InvalidOperation, ValueError):
        return default


def _clean_date(value):
    if not value or str(value).strip().lower() in ('none', 'null', 'nan', '-', ''):
        return None
    val_str = str(value).strip()
    for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y', '%m/%d/%Y', '%Y/%m/%d', '%d-%b-%Y', '%d %b %Y', '%Y-%m-%d %H:%M:%S', '%d/%m/%Y %H:%M:%S'):
        try:
            return datetime.datetime.strptime(val_str.split(' ')[0], fmt.split(' ')[0]).date()
        except (ValueError, IndexError):
            continue
    return None


class CourierStatementImporter:
    def __init__(self, courier_name, file_content, custom_mapping=None, update_order_status=False, settlement=None):
        self.courier_name = courier_name.lower().strip()
        self.file_content = file_content
        self.custom_mapping = custom_mapping or {}
        self.update_order_status = update_order_status
        self.settlement = settlement

    def parse_and_process(self):
        if isinstance(self.file_content, bytes):
            try:
                text = self.file_content.decode('utf-8-sig')
            except UnicodeDecodeError:
                text = self.file_content.decode('latin-1')
        else:
            text = self.file_content

        reader = csv.reader(io.StringIO(text))
        header_row = None
        rows = []
        for row in reader:
            if not row or not any(row):
                continue
            if header_row is None:
                header_row = [h.strip().lower() for h in row]
            else:
                rows.append(row)

        if not header_row:
            return {'errors': ['File is empty or contains no headers.']}

        mapping = self._resolve_mapping(header_row)
        if 'tracking' not in mapping:
            return {
                'errors': [f"Could not find a tracking number column. Headers detected: {', '.join(header_row[:10])}"]
            }

        matched_count = 0
        created_count = 0
        updated_count = 0
        unmatched_rows = []
        errors = []
        total_cod = ZERO
        total_charges = ZERO

        tracking_idx = mapping.get('tracking')
        tracking_numbers = set()
        for r in rows:
            if len(r) > tracking_idx and r[tracking_idx].strip():
                tracking_numbers.add(r[tracking_idx].strip())

        orders_by_tracking = {
            o.tracking_number.strip(): o
            for o in Order.objects.filter(tracking_number__in=tracking_numbers).select_related('financials')
            if o.tracking_number
        }

        order_num_idx = mapping.get('order_number')
        order_numbers = set()
        if order_num_idx is not None:
            for r in rows:
                if len(r) > order_num_idx and r[order_num_idx].strip():
                    order_numbers.add(r[order_num_idx].strip())
            orders_by_number = {
                o.order_number.strip(): o
                for o in Order.objects.filter(order_number__in=order_numbers).select_related('financials')
            }
        else:
            orders_by_number = {}

        for row_idx, row in enumerate(rows, start=2):
            try:
                tracking = row[mapping['tracking']].strip() if len(row) > mapping['tracking'] else ''
                order_num = row[mapping['order_number']].strip() if ('order_number' in mapping and len(row) > mapping['order_number']) else ''

                if not tracking and not order_num:
                    continue

                order = orders_by_tracking.get(tracking) or orders_by_number.get(order_num)

                forward_chg = _clean_decimal(row[mapping['forward_charge']]) if 'forward_charge' in mapping and len(row) > mapping['forward_charge'] else ZERO
                cod_fee = _clean_decimal(row[mapping['cod_fee']]) if 'cod_fee' in mapping and len(row) > mapping['cod_fee'] else ZERO
                ret_chg = _clean_decimal(row[mapping['return_charge']]) if 'return_charge' in mapping and len(row) > mapping['return_charge'] else ZERO
                fuel = _clean_decimal(row[mapping['fuel_surcharge']]) if 'fuel_surcharge' in mapping and len(row) > mapping['fuel_surcharge'] else ZERO
                gst = _clean_decimal(row[mapping['gst']]) if 'gst' in mapping and len(row) > mapping['gst'] else ZERO
                cod_coll = _clean_decimal(row[mapping['cod_collected']]) if 'cod_collected' in mapping and len(row) > mapping['cod_collected'] else ZERO

                status_raw = row[mapping['status']].strip().lower() if 'status' in mapping and len(row) > mapping['status'] else ''
                weight = _clean_decimal(row[mapping['weight']]) if 'weight' in mapping and len(row) > mapping['weight'] else Decimal('0.5')
                deliv_date = _clean_date(row[mapping['delivered_date']]) if 'delivered_date' in mapping and len(row) > mapping['delivered_date'] else None

                courier_status = 'delivered' if any(w in status_raw for w in ('deliv', 'delivered', 'done', 'success', 'paid')) else (
                    'returned' if any(w in status_raw for w in ('ret', 'rto', 'return', 'refused')) else 'dispatched'
                )

                total_charge = forward_chg + cod_fee + ret_chg + fuel + gst
                total_cod += cod_coll
                total_charges += total_charge

                if not order:
                    unmatched_rows.append({
                        'row': row_idx,
                        'tracking': tracking,
                        'order_number': order_num,
                        'status': status_raw,
                        'cod_collected': str(cod_coll),
                        'charges': str(total_charge),
                        'raw': row,
                    })
                    continue

                matched_count += 1

                charge, created = CourierCharge.objects.update_or_create(
                    tracking_number=tracking or order.tracking_number or f"ORD-{order.order_number}",
                    defaults={
                        'order': order,
                        'courier': self.courier_name.capitalize(),
                        'forward_charge': forward_chg,
                        'cod_fee': cod_fee,
                        'return_charge': ret_chg,
                        'fuel_surcharge': fuel,
                        'tax_on_fee': gst,
                        'source': 'statement',
                        'settlement': self.settlement,
                    }
                )

                if created:
                    created_count += 1
                else:
                    updated_count += 1

                if self.update_order_status and order:
                    if courier_status == 'delivered' and order.status != 'delivered':
                        order.status = 'delivered'
                        if order.payment_method == 'COD':
                            order.payment_status = 'paid'
                            order.save(update_fields=['status', 'payment_status'])
                        else:
                            order.save(update_fields=['status'])
                    elif courier_status == 'returned' and order.status != 'returned':
                        order.status = 'returned'
                        order.save(update_fields=['status'])

                from apps.finance.services import OrderFinancialsService
                OrderFinancialsService.calculate_for_order(order)

            except Exception as e:
                errors.append(f"Row {row_idx}: {str(e)}")

        return {
            'total_rows': len(rows),
            'matched': matched_count,
            'created': created_count,
            'updated': updated_count,
            'unmatched': unmatched_rows,
            'errors': errors,
            'total_cod_collected': total_cod,
            'total_charges': total_charges,
        }

    def _resolve_mapping(self, headers):
        mapping = {}
        preset = COURIER_PRESETS.get(self.courier_name, {})

        for field, col_name in self.custom_mapping.items():
            col_lower = str(col_name).strip().lower()
            if col_lower in headers:
                mapping[field] = headers.index(col_lower)

        for field, candidate_names in preset.items():
            if field in mapping:
                continue
            for cand in candidate_names:
                for idx, h in enumerate(headers):
                    if cand == h or cand in h:
                        mapping[field] = idx
                        break
                if field in mapping:
                    break

        if 'tracking' not in mapping:
            for idx, h in enumerate(headers):
                if any(k in h for k in ('track', 'cn', 'waybill', 'awb', 'consignment')):
                    mapping['tracking'] = idx
                    break

        return mapping
