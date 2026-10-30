"""Meta Ads API importer."""
import os
import datetime
from decimal import Decimal

ZERO = Decimal('0.00')


class MetaAdsImporter:
    """
    Pulls ad insights from the Meta Marketing API.
    Idempotent: uses external_id=(date+campaign_id) for deduplication.
    Token must be in the environment variable defined in FinanceSettings.
    """

    BASE_URL = 'https://graph.facebook.com/v19.0'

    def __init__(self):
        from apps.finance.models import FinanceSettings
        self.fs = FinanceSettings.get_settings()
        env_key = self.fs.meta_ads_access_token_env_key or 'META_ADS_ACCESS_TOKEN'
        self.token = os.environ.get(env_key, '')
        self.ad_account_id = self.fs.meta_ad_account_id

    def pull(self, date_from: datetime.date, date_to: datetime.date) -> dict:
        """Fetch daily campaign insights and upsert AdSpendEntry records."""
        if not self.token or not self.ad_account_id:
            return {'error': 'Meta Ads token or ad account ID not configured'}

        try:
            import requests
        except ImportError:
            return {'error': 'requests library not installed'}

        url = f"{self.BASE_URL}/{self.ad_account_id}/insights"
        params = {
            'access_token': self.token,
            'level': 'campaign',
            'time_range': json.dumps({'since': str(date_from), 'until': str(date_to)}),
            'time_increment': 1,  # daily breakdown
            'fields': ','.join([
                'campaign_name', 'campaign_id', 'spend', 'impressions',
                'clicks', 'actions', 'action_values', 'date_start',
            ]),
            'limit': 500,
        }

        imported = 0
        errors = 0

        try:
            import json
            resp = requests.get(url, params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()

            rows = data.get('data', [])
            for row in rows:
                try:
                    self._upsert_row(row)
                    imported += 1
                except Exception as e:
                    errors += 1

            return {'imported': imported, 'errors': errors, 'rows': len(rows)}

        except Exception as e:
            return {'error': str(e)}

    def _upsert_row(self, row: dict):
        import json
        from apps.finance.models import AdSpendEntry, ExchangeRate, FinanceSettings

        date = datetime.date.fromisoformat(row['date_start'])
        campaign_name = row.get('campaign_name', '')
        campaign_id = row.get('campaign_id', '')
        spend = Decimal(str(row.get('spend', '0')))

        # Purchases & value from actions/action_values
        purchases = 0
        purchase_value = ZERO
        for action in row.get('actions', []):
            if action.get('action_type') == 'purchase':
                purchases = int(float(action.get('value', 0)))
        for av in row.get('action_values', []):
            if av.get('action_type') == 'purchase':
                purchase_value = Decimal(str(av.get('value', '0')))

        # Exchange rate
        exchange_rate = Decimal('1.000000')
        fs = self.fs
        # Meta spends in USD for international accounts; check currency
        currency = 'PKR'  # adjust per account configuration
        if currency != fs.base_currency:
            er = ExchangeRate.objects.filter(
                date=date,
                from_currency=currency,
                to_currency=fs.base_currency,
            ).first()
            exchange_rate = er.rate if er else fs.usd_to_base_default_rate
        spend_base = (spend * exchange_rate).quantize(Decimal('0.01'))

        external_id = f"meta_{date}_{campaign_id}"

        AdSpendEntry.objects.update_or_create(
            source='api',
            external_id=external_id,
            defaults={
                'date': date,
                'platform': 'meta',
                'account': self.ad_account_id,
                'campaign': campaign_name,
                'campaign_id': campaign_id,
                'spend': spend,
                'currency': currency,
                'exchange_rate_to_base': exchange_rate,
                'spend_base': spend_base,
                'impressions': int(row.get('impressions', 0)),
                'clicks': int(row.get('clicks', 0)),
                'purchases_reported': purchases,
                'purchase_value_reported': purchase_value,
            }
        )
