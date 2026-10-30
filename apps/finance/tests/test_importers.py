"""
Importer Tests
==============
Tests statement importers for:
- TCS Express CSV
- Leopards Courier CSV
- PostEx Courier CSV
- Meta Ads CSV fallback
"""

from decimal import Decimal
import datetime
from django.test import TestCase
from django.utils import timezone

from apps.orders.models import Order, OrderItem
from apps.catalog.models import Category, Product, ProductVariant
from apps.finance.models import FinanceSettings, CourierCharge, AdSpendEntry, VariantCost
from apps.finance.importers.courier_statement import CourierStatementImporter
from apps.finance.importers.ad_spend_csv import AdSpendCSVImporter


class ImporterTestCase(TestCase):

    def setUp(self):
        self.settings = FinanceSettings.get_settings()
        self.settings.base_currency = 'PKR'
        self.settings.usd_to_base_default_rate = Decimal('280.00')
        self.settings.save()

        self.category = Category.objects.create(name='Linens', slug='linens')
        self.product = Product.objects.create(name='Duvet Cover', slug='duvet-cover', category=self.category, base_price=Decimal('5000.00'))
        self.variant = ProductVariant.objects.create(product=self.product, sku='DUVET-KING', price=Decimal('5000.00'), stock_quantity=50)

        VariantCost.objects.create(
            variant=self.variant,
            unit_cost=Decimal('2000.00'),
            effective_from=datetime.date(2025, 1, 1),
        )

        # Create orders for tracking matching
        self.order1 = Order.objects.create(
            order_number="ORD-101",
            customer_name="Ahmed Khan",
            status='dispatched',
            payment_method='COD',
            subtotal=Decimal('5000.00'),
            grand_total=Decimal('5000.00'),
            courier='TCS',
            tracking_number='7710001234',
            placed_at=timezone.now(),
        )
        OrderItem.objects.create(
            order=self.order1,
            product_name=self.product.name,
            variant=self.variant,
            variant_sku=self.variant.sku,
            unit_price=Decimal('5000.00'),
            quantity=1,
            line_total=Decimal('5000.00'),
        )

        self.order2 = Order.objects.create(
            order_number="ORD-102",
            customer_name="Bilal Sheikh",
            status='dispatched',
            payment_method='COD',
            subtotal=Decimal('5000.00'),
            grand_total=Decimal('5000.00'),
            courier='Leopards',
            tracking_number='LEO-882001',
            placed_at=timezone.now(),
        )
        OrderItem.objects.create(
            order=self.order2,
            product_name=self.product.name,
            variant=self.variant,
            variant_sku=self.variant.sku,
            unit_price=Decimal('5000.00'),
            quantity=1,
            line_total=Decimal('5000.00'),
        )

    def test_tcs_csv_import(self):
        csv_content = """CN Number,Reference,Delivery Status,Delivered On,Weight,COD Amount,Freight,COD Charges,Return Fee
7710001234,ORD-101,Delivered,2026-02-15,1.2,5000,280,100,0
9999999999,UNKNOWN-ORD,Delivered,2026-02-15,0.5,3000,250,60,0
"""
        importer = CourierStatementImporter(courier_name='tcs', file_content=csv_content, update_order_status=True)
        res = importer.parse_and_process()

        self.assertEqual(res['matched'], 1)
        self.assertEqual(len(res['unmatched']), 1)
        self.assertEqual(res['unmatched'][0]['tracking'], '9999999999')

        self.order1.refresh_from_db()
        self.assertEqual(self.order1.status, 'delivered')

        cc = CourierCharge.objects.get(order=self.order1)
        self.assertEqual(cc.forward_charge, Decimal('280.00'))
        self.assertEqual(cc.cod_fee, Decimal('100.00'))

    def test_leopards_csv_import(self):
        csv_content = """CN,Order Ref,Status,Delivery Date,Weight,COD Amount,Delivery Charges,COD Fee,RTO Charges
LEO-882001,ORD-102,RTO,2026-02-16,1.0,0,250,0,150
"""
        importer = CourierStatementImporter(courier_name='leopards', file_content=csv_content, update_order_status=True)
        res = importer.parse_and_process()

        self.assertEqual(res['matched'], 1)
        self.order2.refresh_from_db()
        self.assertEqual(self.order2.status, 'returned')

        cc = CourierCharge.objects.get(order=self.order2)
        self.assertEqual(cc.forward_charge, Decimal('250.00'))
        self.assertEqual(cc.return_charge, Decimal('150.00'))

    def test_ad_spend_csv_import(self):
        csv_content = """Date,Platform,Campaign Name,Amount Spent,Currency,Impressions,Clicks,Purchases,Purchase Value
2026-02-15,meta,Top Funnel Video,50.00,USD,25000,600,12,60000
2026-02-15,google,Brand Search,15000,PKR,5000,400,10,50000
"""
        importer = AdSpendCSVImporter(platform='meta', default_currency='USD')
        res = importer.process(csv_content)

        self.assertEqual(res['created'], 2)
        # USD 50 @ 280 default rate = 14,000 + PKR 15,000 = 29,000
        self.assertEqual(res['total_spend_base'], Decimal('29000.00'))

        meta_entry = AdSpendEntry.objects.get(campaign='Top Funnel Video')
        self.assertEqual(meta_entry.spend_base, Decimal('14000.00'))
        self.assertEqual(meta_entry.purchases_reported, 12)
