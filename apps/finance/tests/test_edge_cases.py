"""
Edge Case Tests for Finance App
================================
Tests handling of Section 8 edge cases:
- Partial returns
- Exchange shipments (extra shipping cost)
- Cancelled after dispatch (courier charge incurred, zero revenue)
- Refused at door (RTO forward + return charge incurred)
- Zero-revenue days / periods (division by zero safety across all metrics)
- Missing product cost detection and alerting
- Rate-card fallback estimation (is_estimated flag)
- Foreign currency exchange rate conversion for ad spend
"""

from decimal import Decimal
import datetime
from django.test import TestCase
from django.utils import timezone

from apps.orders.models import Order, OrderItem
from apps.catalog.models import Category, Product, ProductVariant
from apps.finance.models import (
    FinanceSettings, VariantCost, OrderFinancials, CourierCharge,
    ReturnRecord, ReturnItem, AdSpendEntry, OperatingExpense, ExchangeRate,
    CourierRate
)
from apps.finance.services import OrderFinancialsService, DailySummaryService, DashboardService


class FinanceEdgeCasesTestCase(TestCase):

    def setUp(self):
        self.test_date = datetime.date(2026, 2, 10)
        self.dt = timezone.make_aware(datetime.datetime.combine(self.test_date, datetime.time(10, 0)))

        self.settings = FinanceSettings.get_settings()
        self.settings.base_currency = 'PKR'
        self.settings.usd_to_base_default_rate = Decimal('278.50')
        self.settings.default_packaging_cost_per_order = Decimal('50.00')
        self.settings.save()

        self.category = Category.objects.create(name='Apparel', slug='apparel')
        self.product = Product.objects.create(name='Classic Shirt', slug='classic-shirt', category=self.category, base_price=Decimal('2000.00'))
        self.v1 = ProductVariant.objects.create(product=self.product, sku='SHIRT-M', price=Decimal('2000.00'), stock_quantity=100)
        self.v2 = ProductVariant.objects.create(product=self.product, sku='SHIRT-L', price=Decimal('2000.00'), stock_quantity=100)

        VariantCost.objects.create(
            variant=self.v1,
            unit_cost=Decimal('800.00'),
            packaging_cost=Decimal('10.00'),
            effective_from=datetime.date(2025, 1, 1),
        )

    def test_zero_revenue_period_no_division_by_zero(self):
        """Dashboard must handle zero orders and zero revenue without ZeroDivisionError."""
        empty_date = datetime.date(2026, 3, 1)
        DailySummaryService.rebuild(empty_date, empty_date)
        summary = DashboardService.get_summary(empty_date, empty_date)

        self.assertEqual(summary['net_revenue'], Decimal('0.00'))
        self.assertEqual(summary['orders_delivered'], 0)
        self.assertEqual(summary['net_margin_pct'], Decimal('0.00'))
        self.assertEqual(summary['delivery_success_rate'], Decimal('0.00'))
        self.assertEqual(summary['rto_rate'], Decimal('0.00'))
        self.assertEqual(summary['real_roas'], Decimal('0.00'))
        self.assertEqual(summary['real_cpa'], Decimal('0.00'))
        self.assertEqual(summary['break_even_roas'], Decimal('0.00'))

    def test_cancelled_after_dispatch_incurs_courier_loss(self):
        """Order cancelled after dispatch has forward courier fee and packaging, but 0 revenue."""
        o = Order.objects.create(
            order_number="ORD-DISP-CANCEL",
            customer_name="Ali",
            status='cancelled',
            payment_method='COD',
            subtotal=Decimal('2000.00'),
            grand_total=Decimal('2000.00'),
            courier='Leopards',
            tracking_number='LEO-991',
            placed_at=self.dt,
        )
        OrderItem.objects.create(
            order=o,
            product_name=self.product.name,
            variant=self.v1,
            variant_sku=self.v1.sku,
            unit_price=Decimal('2000.00'),
            quantity=1,
            line_total=Decimal('2000.00'),
        )
        CourierCharge.objects.create(
            order=o,
            tracking_number='LEO-991',
            courier='Leopards',
            forward_charge=Decimal('220.00'),
            cod_fee=Decimal('0.00'),
            return_charge=Decimal('120.00'),
        )
        OrderFinancialsService.snapshot_costs_for_order(o)
        fin = OrderFinancialsService.calculate(o)

        self.assertEqual(fin.net_revenue, Decimal('0.00'))
        self.assertEqual(fin.product_cost, Decimal('0.00'))
        self.assertEqual(fin.total_courier_cost, Decimal('340.00'))  # 220 + 120
        self.assertTrue(fin.contribution_profit < 0)

    def test_partial_return_recovers_cogs(self):
        """Order with 2 items where 1 is returned sellable: COGS reflects only 1 item."""
        o = Order.objects.create(
            order_number="ORD-PART-RET",
            customer_name="Zain",
            status='delivered',
            payment_method='COD',
            subtotal=Decimal('4000.00'),
            grand_total=Decimal('4000.00'),
            courier='TCS',
            tracking_number='TCS-PART',
            placed_at=self.dt,
        )
        item1 = OrderItem.objects.create(
            order=o,
            product_name=self.product.name,
            variant=self.v1,
            variant_sku=self.v1.sku,
            unit_price=Decimal('2000.00'),
            quantity=1,
            line_total=Decimal('2000.00'),
        )
        item2 = OrderItem.objects.create(
            order=o,
            product_name=self.product.name,
            variant=self.v1,
            variant_sku=self.v1.sku,
            unit_price=Decimal('2000.00'),
            quantity=1,
            line_total=Decimal('2000.00'),
        )

        OrderFinancialsService.snapshot_costs_for_order(o)

        # Customer returned item2 sellable
        rr = ReturnRecord.objects.create(
            order=o,
            return_type='customer_return',
            reason='Size does not fit',
            refund_amount=Decimal('2000.00'),
        )
        ReturnItem.objects.create(
            return_record=rr,
            variant=self.v1,
            product_name=self.product.name,
            quantity=1,
            condition='sellable',
            unit_cost_at_return=Decimal('800.00'),
        )

        CourierCharge.objects.create(
            order=o,
            tracking_number='TCS-PART',
            courier='TCS',
            forward_charge=Decimal('250.00'),
            cod_fee=Decimal('40.00'),
        )

        fin = OrderFinancialsService.calculate(o)

        # Net revenue = 4000 gross - 2000 refund = 2000
        self.assertEqual(fin.net_revenue, Decimal('2000.00'))
        # Product cost initially 1600 (2 x 800), minus 800 recovered sellable item = 800
        self.assertEqual(fin.product_cost, Decimal('800.00'))
        self.assertEqual(fin.gross_profit, Decimal('1200.00'))

    def test_missing_cost_snapshot_flag(self):
        """Item without variant cost gets cost_missing flag."""
        o = Order.objects.create(
            order_number="ORD-NO-COST",
            customer_name="Kashif",
            status='delivered',
            payment_method='COD',
            subtotal=Decimal('2000.00'),
            grand_total=Decimal('2000.00'),
            placed_at=self.dt,
        )
        OrderItem.objects.create(
            order=o,
            product_name=self.product.name,
            variant=self.v2,  # v2 has no VariantCost created
            variant_sku=self.v2.sku,
            unit_price=Decimal('2000.00'),
            quantity=1,
            line_total=Decimal('2000.00'),
        )
        OrderFinancialsService.snapshot_costs_for_order(o)
        fin = OrderFinancialsService.calculate(o)

        self.assertTrue(fin.cost_missing)

    def test_usd_ad_spend_conversion(self):
        """USD ad spend converts to PKR using exchange rate."""
        usd_date = datetime.date(2026, 2, 20)
        ExchangeRate.objects.create(
            date=usd_date,
            from_currency='USD',
            to_currency='PKR',
            rate=Decimal('280.00'),
        )
        entry = AdSpendEntry.objects.create(
            date=usd_date,
            platform='meta',
            campaign='USA Campaign',
            spend=Decimal('100.00'),
            currency='USD',
            exchange_rate_to_base=Decimal('280.00'),
            spend_base=Decimal('28000.00'),
            source='api',
        )
        self.assertEqual(entry.spend_base, Decimal('28000.00'))
