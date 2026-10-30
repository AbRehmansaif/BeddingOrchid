"""
Management command: recalculate_financials
Usage:
    python manage.py recalculate_financials
    python manage.py recalculate_financials --from 2024-01-01 --to 2024-01-31
    python manage.py recalculate_financials --rebuild-summaries
"""

import datetime
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone


class Command(BaseCommand):
    help = 'Recalculate OrderFinancials and DailyFinancialSummary for a date range.'

    def add_arguments(self, parser):
        parser.add_argument('--from', dest='date_from', type=str, help='Start date YYYY-MM-DD')
        parser.add_argument('--to', dest='date_to', type=str, help='End date YYYY-MM-DD')
        parser.add_argument('--rebuild-summaries', action='store_true', help='Also rebuild daily summaries')
        parser.add_argument('--batch-size', type=int, default=100, help='Orders per batch')

    def handle(self, *args, **options):
        from apps.orders.models import Order
        from apps.finance.services import OrderFinancialsService
        from apps.finance.services.summary import DailySummaryService

        date_from_str = options.get('date_from')
        date_to_str = options.get('date_to')

        if date_from_str:
            date_from = datetime.date.fromisoformat(date_from_str)
        else:
            date_from = datetime.date(2020, 1, 1)  # All history

        if date_to_str:
            date_to = datetime.date.fromisoformat(date_to_str)
        else:
            date_to = timezone.now().date()

        self.stdout.write(f"Recalculating financials from {date_from} to {date_to}...")

        qs = Order.objects.filter(
            placed_at__date__range=(date_from, date_to)
        ).order_by('placed_at')

        total = qs.count()
        processed = 0
        errors = 0
        batch_size = options['batch_size']

        for i in range(0, total, batch_size):
            batch = qs[i:i + batch_size]
            for order in batch:
                try:
                    # Ensure cost snapshots exist
                    OrderFinancialsService.snapshot_costs_for_order(order)
                    OrderFinancialsService.calculate(order)
                    processed += 1
                except Exception as e:
                    self.stderr.write(f"  Error on order {order.order_number}: {e}")
                    errors += 1

            self.stdout.write(f"  Processed {min(i + batch_size, total)}/{total}...")

        self.stdout.write(self.style.SUCCESS(f"Done! Processed: {processed}, Errors: {errors}"))

        if options['rebuild_summaries']:
            self.stdout.write(f"Rebuilding daily summaries from {date_from} to {date_to}...")
            DailySummaryService.rebuild(date_from, date_to)
            self.stdout.write(self.style.SUCCESS("Daily summaries rebuilt."))
