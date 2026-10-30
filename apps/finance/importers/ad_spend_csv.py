"""
Ad Spend CSV Importer
=====================
Allows bulk upload of advertising spend via CSV.
Supports Meta Ads, Google Ads, TikTok Ads, and generic formats.
"""

import csv
import io
import datetime
from decimal import Decimal, InvalidOperation
from django.utils import timezone
from apps.finance.models import AdSpendEntry, ExchangeRate, FinanceSettings

ZERO = Decimal('0.00')


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


def _clean_int(value, default=0):
    dec = _clean_decimal(value, Decimal('0'))
    try:
        return int(dec)
    except Exception:
        return default


def _clean_date(value):
    if not value:
        return None
    val_str = str(value).strip()
    for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y', '%m/%d/%Y', '%Y/%m/%d', '%d-%b-%Y', '%d %b %Y'):
        try:
            return datetime.datetime.strptime(val_str.split(' ')[0], fmt).date()
        except (ValueError, IndexError):
            continue
    return None


class AdSpendCSVImporter:
    """
    Parses ad spend CSV files and creates/updates AdSpendEntry records.
    """

    def __init__(self, platform='meta', default_currency='USD'):
        self.platform = platform.lower()
        self.default_currency = default_currency.upper()

    def process(self, file_content):
        if isinstance(file_content, bytes):
            try:
                text = file_content.decode('utf-8-sig')
            except UnicodeDecodeError:
                text = file_content.decode('latin-1')
        else:
            text = file_content

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
            return {'errors': ['File is empty.']}

        mapping = self._detect_mapping(header_row)
        if 'date' not in mapping or 'spend' not in mapping:
            return {'errors': [f"CSV must contain at least 'Date' and 'Spend/Amount' columns. Headers found: {', '.join(header_row)}"]}

        created_count = 0
        updated_count = 0
        errors = []
        total_spend_base = ZERO
        dates_affected = set()

        settings = FinanceSettings.get_settings()
        base_curr = settings.base_currency or 'PKR'

        for row_idx, row in enumerate(rows, start=2):
            try:
                date_val = _clean_date(row[mapping['date']]) if len(row) > mapping['date'] else None
                if not date_val:
                    continue

                spend_val = _clean_decimal(row[mapping['spend']]) if len(row) > mapping['spend'] else ZERO
                campaign_name = row[mapping['campaign']].strip() if 'campaign' in mapping and len(row) > mapping['campaign'] else 'General Campaign'
                campaign_id = row[mapping['campaign_id']].strip() if 'campaign_id' in mapping and len(row) > mapping['campaign_id'] else ''
                platform = row[mapping['platform']].strip().lower() if 'platform' in mapping and len(row) > mapping['platform'] else self.platform

                currency = row[mapping['currency']].strip().upper() if 'currency' in mapping and len(row) > mapping['currency'] else self.default_currency

                impressions = _clean_int(row[mapping['impressions']]) if 'impressions' in mapping and len(row) > mapping['impressions'] else 0
                clicks = _clean_int(row[mapping['clicks']]) if 'clicks' in mapping and len(row) > mapping['clicks'] else 0
                purchases = _clean_int(row[mapping['purchases']]) if 'purchases' in mapping and len(row) > mapping['purchases'] else 0
                purchase_val = _clean_decimal(row[mapping['purchase_value']]) if 'purchase_value' in mapping and len(row) > mapping['purchase_value'] else ZERO

                # Calculate base spend
                if currency == base_curr:
                    spend_base = spend_val
                    rate_used = Decimal('1.00')
                else:
                    rate_obj = ExchangeRate.objects.filter(from_currency=currency, to_currency=base_curr, date__lte=date_val).order_by('-date').first()
                    rate_used = rate_obj.rate if rate_obj else (settings.usd_to_base_default_rate if currency == 'USD' else Decimal('1.00'))
                    spend_base = spend_val * rate_used

                external_id = f"csv_{platform}_{date_val}_{campaign_name[:40].replace(' ', '_')}"

                entry, created = AdSpendEntry.objects.update_or_create(
                    external_id=external_id,
                    defaults={
                        'source': 'csv',
                        'date': date_val,
                        'platform': platform,
                        'campaign': campaign_name,
                        'campaign_id': campaign_id,
                        'spend': spend_val,
                        'currency': currency,
                        'exchange_rate_to_base': rate_used,
                        'spend_base': spend_base,
                        'impressions': impressions,
                        'clicks': clicks,
                        'purchases_reported': purchases,
                        'purchase_value_reported': purchase_val,
                    }
                )

                if created:
                    created_count += 1
                else:
                    updated_count += 1

                total_spend_base += spend_base
                dates_affected.add(date_val)

            except Exception as e:
                errors.append(f"Row {row_idx}: {str(e)}")

        # Trigger summary rebuild for affected dates
        if dates_affected:
            min_date = min(dates_affected)
            max_date = max(dates_affected)
            from apps.finance.services import DailySummaryService
            DailySummaryService.rebuild_range(min_date, max_date)

        return {
            'total_rows': len(rows),
            'created': created_count,
            'updated': updated_count,
            'errors': errors,
            'total_spend_base': total_spend_base,
            'dates_count': len(dates_affected),
        }

    def _detect_mapping(self, headers):
        mapping = {}
        for idx, h in enumerate(headers):
            if any(k in h for k in ('day', 'date', 'reporting starts')):
                mapping.setdefault('date', idx)
            elif any(k in h for k in ('amount spent', 'spend', 'cost', 'cost (pkr)', 'cost (usd)')):
                mapping.setdefault('spend', idx)
            elif any(k in h for k in ('campaign name', 'campaign', 'campaign_name')):
                mapping.setdefault('campaign', idx)
            elif any(k in h for k in ('campaign id', 'campaign_id')):
                mapping.setdefault('campaign_id', idx)
            elif any(k in h for k in ('platform', 'channel', 'source')):
                mapping.setdefault('platform', idx)
            elif any(k in h for k in ('currency', 'account currency')):
                mapping.setdefault('currency', idx)
            elif any(k in h for k in ('impressions', 'impr')):
                mapping.setdefault('impressions', idx)
            elif any(k in h for k in ('link clicks', 'clicks')):
                mapping.setdefault('clicks', idx)
            elif any(k in h for k in ('purchases', 'conversions', 'orders')):
                mapping.setdefault('purchases', idx)
            elif any(k in h for k in ('purchase conversion value', 'purchase value', 'conversion value', 'revenue')):
                mapping.setdefault('purchase_value', idx)
        return mapping
