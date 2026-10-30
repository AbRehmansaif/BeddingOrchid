"""
Test Section 10 Worked Example
==============================
Verifies the exact scenario from Section 10 of the spec:
- 100 orders placed at Rs 3,000 each.
- 70 delivered, 20 returned (RTO), 10 cancelled before dispatch.
- Unit cost: Rs 1,200.
- Ad spend: Rs 40,000.
- Courier forward: 90 x 250 = Rs 22,500.
- Courier return: 20 x 150 = Rs 3,000.
- COD fee: 2% of delivered (Rs 4,200).
- Packaging: 90 x 60 = Rs 5,400.
- Damaged returns write-off: 3 x 1,200 = Rs 3,600.
- Opex: Rs 20,000.
All figures verified to the rupee!
"""

from decimal import Decimal
import datetime
from django.test import TestCase
from django.utils import timezone

from apps.orders.models import Order, OrderItem
from apps.catalog.models import Category, Product, ProductVariant
from apps.finance.models import (
    FinanceSettings, VariantCost, OrderFinancials, CourierCharge,
    ReturnRecord, ReturnItem, AdSpendEntry, OperatingExpense, ExpenseCategory,
    DailyFinancialSummary
)
from apps.finance.services import OrderFinancialsService, DailySummaryService, DashboardService


class WorkedExampleTestCase(TestCase):

    def setUp(self):
        self.test_date = datetime.date(2026, 1, 15)
        self.dt = timezone.make_aware(datetime.datetime.combine(self.test_date, datetime.time(12, 0)))

        # 1. Setup FinanceSettings
        self.settings = FinanceSettings.get_settings()
        self.settings.base_currency = 'PKR'
        self.settings.include_shipping_fee_in_revenue = False
        self.settings.include_cod_fee_in_revenue = False
        self.settings.default_packaging_cost_per_order = Decimal('60.00')
        self.settings.default_cod_fee_percent = Decimal('2.00')
        self.settings.save()

        # 2. Setup Category, Product & Variant
        self.category = Category.objects.create(name='Bedding', slug='bedding')
        self.product = Product.objects.create(name='Luxury Sheet Set', slug='sheet-set', category=self.category, base_price=Decimal('3000.00'))
        self.variant = ProductVariant.objects.create(product=self.product, sku='SHEET-KING-WH', price=Decimal('3000.00'), stock_quantity=500)

        # 3. Setup VariantCost: Rs 1,200
        VariantCost.objects.create(
            variant=self.variant,
            unit_cost=Decimal('1200.00'),
            packaging_cost=Decimal('0.00'),
            effective_from=datetime.date(2025, 1, 1),
        )

        # 4. Create 100 Orders
        self.orders = []
        for i in range(1, 101):
            if i <= 70:
                status = 'delivered'
            elif i <= 90:
                status = 'returned'
            else:
                status = 'cancelled'

            o = Order.objects.create(
                order_number=f"ORD-{i:04d}",
                customer_name=f"Customer {i}",
                customer_phone='03001234567',
                shipping_full_name=f"Customer {i}",
                shipping_phone='03001234567',
                shipping_address_line1='Street 1',
                shipping_city='Lahore',
                status=status,
                payment_method='COD',
                payment_status='paid' if status == 'delivered' else 'pending',
                subtotal=Decimal('3000.00'),
                grand_total=Decimal('3000.00'),
                courier='TCS',
                tracking_number=f"TCS-{i:04d}",
                placed_at=self.dt,
            )

            # Item
            item = OrderItem.objects.create(
                order=o,
                product_name=self.product.name,
                variant=self.variant,
                variant_sku=self.variant.sku,
                unit_price=Decimal('3000.00'),
                quantity=1,
                line_total=Decimal('3000.00'),
            )

            # Courier charges for dispatched orders (1 to 90)
            if i <= 90:
                is_ret = (i > 70)
                CourierCharge.objects.create(
                    order=o,
                    tracking_number=o.tracking_number,
                    courier='TCS',
                    forward_charge=Decimal('250.00'),
                    cod_fee=Decimal('60.00') if status == 'delivered' else Decimal('0.00'),
                    return_charge=Decimal('150.00') if is_ret else Decimal('0.00'),
                )

            # Returns logging: 3 orders have damaged items written off
            if 71 <= i <= 90:
                is_damaged = (i <= 73)  # exactly 3 damaged
                rr = ReturnRecord.objects.create(
                    order=o,
                    return_type='rto',
                    reason='refused',
                    loss_amount=Decimal('1200.00') if is_damaged else Decimal('0.00'),
                )
                ReturnItem.objects.create(
                    return_record=rr,
                    variant=item.variant,
                    product_name=item.product_name,
                    quantity=1,
                    condition='damaged' if is_damaged else 'sellable',
                    unit_cost_at_return=Decimal('1200.00'),
                )

            # Snapshot costs & calculate OrderFinancials
            OrderFinancialsService.snapshot_costs_for_order(o)
            OrderFinancialsService.calculate(o)
            self.orders.append(o)

        # 5. Ad spend: Rs 40,000 (reported purchases: 100 placed value 300,000)
        AdSpendEntry.objects.create(
            date=self.test_date,
            platform='meta',
            campaign='Main Scaling Campaign',
            spend=Decimal('40000.00'),
            spend_base=Decimal('40000.00'),
            currency='PKR',
            purchases_reported=100,
            purchase_value_reported=Decimal('300000.00'),
            source='api',
        )

        # 6. Operating Expenses: Rs 20,000 (one-time on that day for clean test)
        cat = ExpenseCategory.objects.create(name='Salaries & Office')
        OperatingExpense.objects.create(
            date=self.test_date,
            category=cat,
            description='Office & Salaries Allocation',
            amount=Decimal('20000.00'),
            is_recurring=False,
        )

        # 7. Rebuild Daily Financial Summary
        DailySummaryService.rebuild(self.test_date, self.test_date)

    def test_section_10_worked_example_figures(self):
        summary = DashboardService.get_summary(self.test_date, self.test_date)

        # 1. Order counts
        self.assertEqual(summary['orders_placed'], 100)
        self.assertEqual(summary['orders_dispatched'], 90)
        self.assertEqual(summary['orders_delivered'], 70)
        self.assertEqual(summary['orders_returned'], 20)
        self.assertEqual(summary['orders_cancelled'], 10)

        # 2. Revenue & COGS
        self.assertEqual(summary['net_revenue'], Decimal('210000.00'))
        self.assertEqual(summary['product_cost'], Decimal('84000.00'))
        self.assertEqual(summary['gross_profit'], Decimal('126000.00'))

        # 3. Direct Operational Expenses
        self.assertEqual(summary['courier_forward'], Decimal('22500.00'))   # 90 x 250
        self.assertEqual(summary['courier_return'], Decimal('3000.00'))     # 20 x 150
        self.assertEqual(summary['courier_cod_fee'], Decimal('4200.00'))    # 70 x 60 (2% of 210,000)
        self.assertEqual(summary['total_courier_cost'], Decimal('29700.00')) # 22,500 + 3,000 + 4,200
        self.assertEqual(summary['packaging_cost'], Decimal('5400.00'))     # 90 x 60
        self.assertEqual(summary['return_loss'], Decimal('3600.00'))        # 3 x 1,200 damaged write-off
        self.assertEqual(summary['ad_spend'], Decimal('40000.00'))

        # Total costs above gross profit:
        # 40,000 (ad) + 22,500 (fwd) + 3,000 (ret) + 4,200 (cod) + 5,400 (pkg) + 3,600 (dmg) = 78,700
        total_costs_above_gross = (
            summary['ad_spend'] + summary['courier_forward'] + summary['courier_return'] +
            summary['courier_cod_fee'] + summary['packaging_cost'] + summary['return_loss']
        )
        self.assertEqual(total_costs_above_gross, Decimal('78700.00'))

        # Contribution profit (before ads) = 126,000 - 38,700 = 87,300
        self.assertEqual(summary['contribution_profit_before_ads'], Decimal('87300.00'))

        # Contribution profit (after ads) = 126,000 - 78,700 = 47,300
        self.assertEqual(summary['contribution_profit'], Decimal('47300.00'))

        # 4. Operating Expenses & Net Profit
        self.assertEqual(summary['operating_expenses'], Decimal('20000.00'))
        self.assertEqual(summary['net_profit'], Decimal('27300.00'))

        # 5. Target KPIs
        # Net margin = 27,300 / 210,000 = 13.0%
        self.assertEqual(summary['net_margin_pct'], Decimal('13.00'))

        # Delivery success rate = 70 / 90 = 77.8%
        self.assertEqual(summary['delivery_success_rate'], Decimal('77.78'))

        # RTO rate = 20 / 90 = 22.2%
        self.assertEqual(summary['rto_rate'], Decimal('22.22'))

        # Profit per delivered order = 27,300 / 70 = Rs 390
        self.assertEqual(summary['profit_per_delivered_order'], Decimal('390.00'))

        # Real CPA = 40,000 / 70 = Rs 571.43 (~ Rs 571)
        self.assertEqual(round(summary['real_cpa']), Decimal('571'))

        # Platform ROAS = 300,000 / 40,000 = 7.50
        self.assertEqual(summary['platform_roas'], Decimal('7.50'))

        # Real ROAS = 210,000 / 40,000 = 5.25
        self.assertEqual(summary['real_roas'], Decimal('5.25'))

        # Break-even ROAS = 1 / (87,300 / 210,000) = 1 / 0.415714 = 2.41
        self.assertEqual(summary['break_even_roas'], Decimal('2.41'))
