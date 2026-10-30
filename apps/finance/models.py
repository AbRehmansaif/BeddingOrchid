"""
Finance App Models
==================
All money fields use DecimalField(max_digits=14, decimal_places=2). No floats.
Revenue recognised on DELIVERY (COD). Costs snapshot at order time.
"""

from decimal import Decimal
from django.db import models
from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.utils import timezone
from simple_history.models import HistoricalRecords

from apps.core.models import TimeStampedModel


# ---------------------------------------------------------------------------
# 2.4  Settings & Rate Cards
# ---------------------------------------------------------------------------

class FinanceSettings(TimeStampedModel):
    """
    Singleton model holding store-wide finance preferences.
    One row only – enforced via save() override (pk=1).
    """
    REVENUE_RECOGNITION_CHOICES = (
        ('delivered', 'Recognised on Delivery (recommended for COD)'),
        ('placed', 'Recognised on Placement'),
    )

    base_currency = models.CharField(max_length=10, default='PKR')
    revenue_recognition = models.CharField(
        max_length=20, choices=REVENUE_RECOGNITION_CHOICES, default='delivered',
        help_text='When should an order count as revenue?'
    )
    include_shipping_fee_in_revenue = models.BooleanField(
        default=True, help_text='Count the shipping fee charged to the customer as income?'
    )
    include_cod_fee_in_revenue = models.BooleanField(
        default=False, help_text='Count the COD fee charged to the customer as income?'
    )
    default_packaging_cost_per_order = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('60.00'),
        help_text='Per-order packaging cost when no variant-level figure exists'
    )
    default_cod_fee_percent = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('2.00'),
        help_text='% of COD amount charged by courier as handling fee (if no rate card)'
    )
    sales_tax_percent = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('0.00'),
        help_text='Sales tax / GST rate %. 0 = not applicable.'
    )
    sales_tax_included_in_prices = models.BooleanField(
        default=False, help_text='Are prices tax-inclusive? If yes, tax is extracted from price.'
    )
    payment_gateway_fee_percent = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('2.50'),
        help_text='Fee % on non-COD (online) payments'
    )
    usd_to_base_default_rate = models.DecimalField(
        max_digits=14, decimal_places=4, default=Decimal('278.00'),
        help_text='Fallback USD → PKR rate when no ExchangeRate entry exists'
    )
    fiscal_month_start_day = models.PositiveSmallIntegerField(
        default=1, help_text='Day of month the fiscal month starts (1–28)'
    )
    min_margin_percent_alert = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('15.00'),
        help_text='Warn when product margin falls below this %'
    )
    ad_cost_allocation_method = models.CharField(
        max_length=20,
        choices=(('order_count', 'By Order Count'), ('revenue', 'By Revenue Share')),
        default='order_count',
        help_text='How to allocate period ad spend to individual orders'
    )
    count_packaging_for_returns = models.BooleanField(
        default=True,
        help_text='Count packaging cost for returned parcels? (they used packaging even if returned)'
    )
    delivery_success_trailing_days = models.PositiveSmallIntegerField(
        default=60,
        help_text='Days of history to use when estimating delivery success rate for in-transit orders'
    )
    settlement_overdue_days = models.PositiveSmallIntegerField(
        default=14, help_text='Alert when courier COD settlement is overdue beyond this many days'
    )
    income_tax_percent = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('0.00'),
        help_text='Income tax provision % applied to net profit before tax'
    )
    meta_ad_account_id = models.CharField(max_length=100, blank=True)
    meta_ads_access_token_env_key = models.CharField(
        max_length=100, default='META_ADS_ACCESS_TOKEN',
        help_text='Name of the environment variable holding the Meta Ads token (never stored plain text here)'
    )

    history = HistoricalRecords()

    class Meta:
        verbose_name = 'Finance Settings'
        verbose_name_plural = 'Finance Settings'

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)
        cache.delete('finance_settings_instance')

    @classmethod
    def get_settings(cls):
        cached = cache.get('finance_settings_instance')
        if cached:
            return cached
        instance, _ = cls.objects.get_or_create(pk=1)
        cache.set('finance_settings_instance', instance, timeout=3600)
        return instance

    def __str__(self):
        return 'Finance Settings'


class ExchangeRate(TimeStampedModel):
    """Daily exchange rate for converting ad spend currencies to base (PKR)."""
    date = models.DateField(db_index=True)
    from_currency = models.CharField(max_length=10)
    to_currency = models.CharField(max_length=10)
    rate = models.DecimalField(max_digits=14, decimal_places=6)

    class Meta:
        unique_together = ('date', 'from_currency', 'to_currency')
        ordering = ['-date']

    def __str__(self):
        return f"{self.date} | {self.from_currency}/{self.to_currency} = {self.rate}"


class CourierRate(TimeStampedModel):
    """
    Rate card used to estimate courier charges before the actual statement arrives.
    When a real CourierCharge is imported, OrderFinancials.is_estimated becomes False.
    """
    COURIER_CHOICES = (
        ('tcs', 'TCS'),
        ('leopards', 'Leopards Courier'),
        ('postex', 'PostEx'),
        ('trax', 'Trax'),
        ('mp', 'M&P Courier'),
        ('other', 'Other'),
    )
    courier = models.CharField(max_length=30, choices=COURIER_CHOICES)
    city_or_zone = models.CharField(max_length=100, blank=True, help_text='City name or zone label; blank = default')
    weight_from = models.DecimalField(max_digits=8, decimal_places=3, default=Decimal('0'))
    weight_to = models.DecimalField(max_digits=8, decimal_places=3, default=Decimal('5'))
    forward_charge = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('250.00'))
    return_charge = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('150.00'))
    cod_fee_percent = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('2.00'))
    fuel_percent = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))
    effective_from = models.DateField(default=timezone.now)

    class Meta:
        ordering = ['-effective_from', 'courier', 'city_or_zone']

    def __str__(self):
        return f"{self.courier} | {self.city_or_zone or 'Default'} | from {self.effective_from}"


# ---------------------------------------------------------------------------
# 2.1  Product cost per variant (with history)
# ---------------------------------------------------------------------------

class VariantCost(TimeStampedModel):
    """
    Cost of a specific ProductVariant (size/colour combination).
    Supports history: latest effective_from ≤ order date applies.
    Changing this NEVER rewrites old OrderItem snapshots.
    """
    variant = models.ForeignKey(
        'catalog.ProductVariant',
        on_delete=models.CASCADE,
        related_name='costs'
    )
    unit_cost = models.DecimalField(
        max_digits=14, decimal_places=2,
        help_text='Purchase price or manufacturing cost per unit (PKR)'
    )
    packaging_cost = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0.00'),
        help_text='Per-unit packaging: poly bag, box, tag (PKR)'
    )
    other_unit_cost = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0.00'),
        help_text='Stitching, printing, labels, etc. (PKR); optional'
    )
    effective_from = models.DateField(
        default=timezone.now,
        help_text='Cost history: the most recent record with effective_from ≤ order date applies'
    )
    note = models.TextField(blank=True)

    history = HistoricalRecords()

    class Meta:
        ordering = ['-effective_from']
        indexes = [
            models.Index(fields=['variant', 'effective_from']),
        ]

    def __str__(self):
        return f"{self.variant} | cost {self.unit_cost} from {self.effective_from}"


# ---------------------------------------------------------------------------
# 2.3  Ad Spend
# ---------------------------------------------------------------------------

class AdSpendEntry(TimeStampedModel):
    """
    Ad spend from Meta, Google, TikTok, or manual entry.
    Idempotent: deduplicated by external_id per source.
    """
    PLATFORM_CHOICES = (
        ('meta', 'Meta (Facebook/Instagram)'),
        ('google', 'Google Ads'),
        ('tiktok', 'TikTok Ads'),
        ('other', 'Other'),
    )
    SOURCE_CHOICES = (
        ('api', 'API (automated pull)'),
        ('csv', 'CSV Import'),
        ('manual', 'Manual Entry'),
    )

    date = models.DateField(db_index=True)
    platform = models.CharField(max_length=20, choices=PLATFORM_CHOICES, default='meta')
    account = models.CharField(max_length=150, blank=True)
    campaign = models.CharField(max_length=255, blank=True, db_index=True)
    campaign_id = models.CharField(max_length=100, blank=True, db_index=True)
    adset = models.CharField(max_length=255, blank=True)
    adset_id = models.CharField(max_length=100, blank=True)

    spend = models.DecimalField(max_digits=14, decimal_places=2, help_text='In the ad platform\'s currency')
    currency = models.CharField(max_length=10, default='PKR')
    exchange_rate_to_base = models.DecimalField(
        max_digits=14, decimal_places=6, default=Decimal('1.000000'),
        help_text='Rate used to convert spend → spend_base'
    )
    spend_base = models.DecimalField(
        max_digits=14, decimal_places=2,
        help_text='Spend in base currency (PKR)'
    )

    impressions = models.BigIntegerField(default=0)
    clicks = models.BigIntegerField(default=0)
    purchases_reported = models.IntegerField(default=0, help_text='Purchases attributed by the platform')
    purchase_value_reported = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0.00'),
        help_text='Revenue attributed by the platform (for Platform ROAS)'
    )

    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default='manual')
    external_id = models.CharField(
        max_length=255, blank=True, db_index=True,
        help_text='Unique ID from the platform (for deduplication)'
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-date', 'platform', 'campaign']
        indexes = [
            models.Index(fields=['date', 'platform']),
            models.Index(fields=['date', 'campaign_id']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['source', 'external_id'],
                condition=~models.Q(external_id=''),
                name='unique_adspend_external_id'
            )
        ]

    def save(self, *args, **kwargs):
        # Auto-compute spend_base if not set
        if not self.spend_base:
            self.spend_base = (self.spend * self.exchange_rate_to_base).quantize(Decimal('0.01'))
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.date} | {self.platform} | {self.campaign or 'All Campaigns'} | Rs {self.spend_base:,.0f}"


# ---------------------------------------------------------------------------
# 2.3  Courier Charges & Settlements
# ---------------------------------------------------------------------------

class CourierSettlement(TimeStampedModel):
    """COD cash remittance statement from a courier company."""
    COURIER_CHOICES = CourierRate.COURIER_CHOICES
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('received', 'Received'),
        ('disputed', 'Disputed'),
    )

    courier = models.CharField(max_length=30, choices=COURIER_CHOICES)
    statement_number = models.CharField(max_length=100, unique=True)
    statement_date = models.DateField()
    cod_collected = models.DecimalField(max_digits=14, decimal_places=2, help_text='Total COD courier collected from customers')
    charges_deducted = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'), help_text='Courier fees deducted from settlement')
    net_paid_to_us = models.DecimalField(max_digits=14, decimal_places=2, help_text='Actual amount transferred to us')
    paid_on = models.DateField(null=True, blank=True)
    reference = models.CharField(max_length=200, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    attachment = models.FileField(upload_to='finance/settlements/', blank=True, null=True)
    notes = models.TextField(blank=True)

    history = HistoricalRecords()

    class Meta:
        ordering = ['-statement_date']

    def __str__(self):
        return f"{self.courier} | {self.statement_number} | Rs {self.net_paid_to_us:,.0f}"


class CourierCharge(TimeStampedModel):
    """
    Actual per-parcel charge from a courier statement.
    Imported from CSV or entered manually.
    Linked to Order by tracking_number; unmatched rows flagged for review.
    """
    COURIER_CHOICES = CourierRate.COURIER_CHOICES
    SOURCE_CHOICES = (
        ('csv', 'CSV Import'),
        ('manual', 'Manual Entry'),
        ('api', 'API'),
    )

    order = models.OneToOneField(
        'orders.Order', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='courier_charge'
    )
    courier = models.CharField(max_length=30, choices=COURIER_CHOICES)
    tracking_number = models.CharField(max_length=100, db_index=True)

    forward_charge = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    cod_fee = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'), help_text='COD handling commission')
    return_charge = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    fuel_surcharge = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    weight_charge = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    tax_on_fee = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    other_charge = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))

    charged_on = models.DateField(null=True, blank=True)
    settlement = models.ForeignKey(
        CourierSettlement, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='charges'
    )
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default='manual')
    is_unmatched = models.BooleanField(
        default=False,
        help_text='True when we could not match this charge to an order'
    )
    notes = models.TextField(blank=True)

    history = HistoricalRecords()

    class Meta:
        ordering = ['-charged_on', 'courier']
        indexes = [
            models.Index(fields=['tracking_number']),
            models.Index(fields=['order']),
        ]

    @property
    def total_charge(self):
        return (
            self.forward_charge + self.cod_fee + self.return_charge +
            self.fuel_surcharge + self.weight_charge + self.tax_on_fee + self.other_charge
        )

    def __str__(self):
        order_ref = self.order.order_number if self.order else 'Unmatched'
        return f"{self.courier} | {self.tracking_number} | Rs {self.total_charge:,.0f} ({order_ref})"


# ---------------------------------------------------------------------------
# 2.3  Returns
# ---------------------------------------------------------------------------

class ReturnRecord(TimeStampedModel):
    """
    Customer return, RTO, exchange or refused-at-door event.
    Each item in the return is tracked with its condition.
    """
    RETURN_TYPE_CHOICES = (
        ('customer_return', 'Customer Return'),
        ('courier_rto', 'Courier RTO (Return to Origin)'),
        ('refused_at_door', 'Refused at Door'),
        ('exchange', 'Exchange'),
        ('failed_delivery', 'Failed Delivery'),
    )

    order = models.ForeignKey('orders.Order', on_delete=models.CASCADE, related_name='return_records')
    return_type = models.CharField(max_length=30, choices=RETURN_TYPE_CHOICES)
    reason = models.TextField(blank=True)
    received_on = models.DateField(null=True, blank=True)
    restocked = models.BooleanField(default=False)
    refund_amount = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    extra_shipping_cost = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0.00'),
        help_text='Extra shipping for exchanges (second shipment cost)'
    )
    loss_amount = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0.00'),
        help_text='Auto-computed: cost of damaged/lost items + unrec. refunds + extra shipping'
    )
    notes = models.TextField(blank=True)

    history = HistoricalRecords()

    class Meta:
        ordering = ['-received_on', '-created_at']

    def __str__(self):
        return f"Return #{self.pk} | {self.order.order_number} | {self.return_type}"


class ReturnItem(TimeStampedModel):
    """Individual item within a ReturnRecord."""
    CONDITION_CHOICES = (
        ('sellable', 'Sellable (can be restocked)'),
        ('damaged', 'Damaged (write-off)'),
        ('lost', 'Lost in Transit'),
    )

    return_record = models.ForeignKey(ReturnRecord, on_delete=models.CASCADE, related_name='items')
    variant = models.ForeignKey('catalog.ProductVariant', on_delete=models.SET_NULL, null=True, blank=True)
    product_name = models.CharField(max_length=255)  # snapshot
    quantity = models.PositiveIntegerField(default=1)
    condition = models.CharField(max_length=20, choices=CONDITION_CHOICES, default='sellable')
    unit_cost_at_return = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0.00'),
        help_text='Cost snapshot used for the write-off calculation'
    )

    def __str__(self):
        return f"{self.quantity}x {self.product_name} ({self.condition})"


# ---------------------------------------------------------------------------
# 2.3  Operating Expenses
# ---------------------------------------------------------------------------

class ExpenseCategory(TimeStampedModel):
    """Predefined expense categories for the P&L statement."""
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    sort_order = models.PositiveIntegerField(default=0)
    is_marketing = models.BooleanField(
        default=False,
        help_text='Count toward Marketing Efficiency Ratio (MER)?'
    )

    class Meta:
        ordering = ['sort_order', 'name']
        verbose_name_plural = 'Expense Categories'

    def __str__(self):
        return self.name


class OperatingExpense(TimeStampedModel):
    """
    A business overhead cost (salaries, rent, tools, etc.).
    Recurring expenses are spread daily across the period when querying the dashboard.
    """
    RECURRENCE_CHOICES = (
        ('', 'One-time'),
        ('monthly', 'Monthly'),
        ('weekly', 'Weekly'),
        ('yearly', 'Yearly'),
    )

    date = models.DateField(db_index=True, help_text='Expense incurred date (or start date for recurring)')
    category = models.ForeignKey(ExpenseCategory, on_delete=models.PROTECT, related_name='expenses')
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    description = models.CharField(max_length=500)
    is_recurring = models.BooleanField(default=False)
    recurrence = models.CharField(max_length=20, choices=RECURRENCE_CHOICES, blank=True)
    attachment = models.FileField(upload_to='finance/expenses/', blank=True, null=True)
    notes = models.TextField(blank=True)

    history = HistoricalRecords()

    class Meta:
        ordering = ['-date']
        indexes = [
            models.Index(fields=['date', 'category']),
        ]

    def __str__(self):
        return f"{self.date} | {self.category.name} | Rs {self.amount:,.0f}"


class OtherIncome(TimeStampedModel):
    """Wholesale, referral payments, or other non-order income."""
    date = models.DateField(db_index=True)
    description = models.CharField(max_length=500)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-date']

    def __str__(self):
        return f"{self.date} | {self.description} | Rs {self.amount:,.0f}"


# ---------------------------------------------------------------------------
# 2.2  Per-order financials (materialised)
# ---------------------------------------------------------------------------

class OrderFinancials(TimeStampedModel):
    """
    Pre-computed financial summary for one Order.
    Recalculated via Celery whenever the order, its items, return records,
    or courier charges change. Reading from this table is always fast.
    """
    order = models.OneToOneField(
        'orders.Order', on_delete=models.CASCADE, related_name='financials'
    )

    # --- Revenue ---
    gross_sales = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'),
        help_text='Sum of unit_price × qty for all items (before discounts)')
    discount_total = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    refund_total = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'),
        help_text='Refunds given on this order (partial returns, price adjustments)')
    shipping_charged = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'),
        help_text='Shipping fee paid by the customer')
    cod_fee_charged = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'),
        help_text='COD fee paid by the customer')
    net_revenue = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'),
        help_text='Recognised revenue (see finance guide). 0 if not delivered.')

    # --- Costs ---
    product_cost = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'),
        help_text='Sum(qty × unit_cost_snapshot) for items that were actually sold')
    packaging_cost = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))

    # Courier
    courier_forward_charge = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    courier_cod_fee = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    courier_return_charge = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    courier_other_charge = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'),
        help_text='Fuel, weight, insurance, tax on courier fees')
    total_courier_cost = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))

    payment_gateway_fee = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'),
        help_text='For non-COD payments')
    sales_tax = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'),
        help_text='Sales tax / GST extracted or charged')
    return_loss = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'),
        help_text='Write-off cost of damaged/lost returned goods')

    # Allocated ad spend (optional per-order share)
    ad_cost_allocated = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'),
        help_text='Allocated share of period ad spend (for per-order profit view)')

    # --- Profit levels ---
    gross_profit = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    contribution_profit_before_ads = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    contribution_profit = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'),
        help_text='Contribution profit after allocated ad spend')

    # --- Flags ---
    is_estimated = models.BooleanField(
        default=True,
        help_text='True when any courier charge is from the rate card (not an actual statement)'
    )
    cost_missing = models.BooleanField(
        default=False,
        help_text='True when one or more items have no VariantCost → profit is overstated'
    )
    calculated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Order Financials'
        verbose_name_plural = 'Order Financials'
        indexes = [
            models.Index(fields=['order']),
            models.Index(fields=['is_estimated']),
            models.Index(fields=['cost_missing']),
        ]

    def __str__(self):
        return f"Financials for {self.order.order_number}"


# ---------------------------------------------------------------------------
# Per-item cost snapshots (added to OrderItem via migration)
# ---------------------------------------------------------------------------

class OrderItemCostSnapshot(TimeStampedModel):
    """
    Cost snapshot taken at order placement for each OrderItem.
    Stored separately so we never touch the original OrderItem.
    """
    order_item = models.OneToOneField(
        'orders.OrderItem', on_delete=models.CASCADE,
        related_name='cost_snapshot'
    )
    unit_cost_snapshot = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    packaging_cost_snapshot = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    other_cost_snapshot = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    cost_missing = models.BooleanField(
        default=False,
        help_text='True when no VariantCost record was found at order time'
    )

    def total_unit_cost(self):
        return self.unit_cost_snapshot + self.packaging_cost_snapshot + self.other_cost_snapshot

    def __str__(self):
        return f"Cost snapshot for item #{self.order_item_id}"


# ---------------------------------------------------------------------------
# Daily financial summary (pre-aggregated for dashboard speed)
# ---------------------------------------------------------------------------

class DailyFinancialSummary(models.Model):
    """
    One row per calendar date.
    Rebuilt nightly by a Celery beat task and on demand.
    The dashboard reads from this table; never from raw orders for range queries.
    """
    date = models.DateField(unique=True, db_index=True)

    # Order counts
    orders_placed = models.IntegerField(default=0)
    orders_confirmed = models.IntegerField(default=0)
    orders_dispatched = models.IntegerField(default=0)
    orders_delivered = models.IntegerField(default=0)
    orders_returned = models.IntegerField(default=0)
    orders_cancelled = models.IntegerField(default=0)

    # Revenue
    gross_sales = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    discount_total = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    refund_total = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    shipping_income = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    cod_fee_income = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    net_revenue = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))

    # COGS
    product_cost = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    packaging_cost = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    gross_profit = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))

    # Courier & fulfilment
    courier_forward = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    courier_cod_fee = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    courier_return = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    courier_other = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    total_courier_cost = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))

    # Losses & fees
    return_loss = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    payment_gateway_fee = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    sales_tax = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))

    # Advertising
    ad_spend = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))

    # Operating expenses (spread from OperatingExpense records)
    operating_expenses = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))

    # Profit
    contribution_profit_before_ads = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    contribution_profit = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    net_profit = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))

    # Quality flags
    has_missing_costs = models.BooleanField(default=False)
    has_estimated_charges = models.BooleanField(default=False)
    has_missing_ad_spend = models.BooleanField(default=False)

    rebuilt_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date']
        verbose_name = 'Daily Financial Summary'
        verbose_name_plural = 'Daily Financial Summaries'

    def __str__(self):
        return f"Summary {self.date} | Net Revenue Rs {self.net_revenue:,.0f} | Net Profit Rs {self.net_profit:,.0f}"


# ---------------------------------------------------------------------------
# Monthly Close
# ---------------------------------------------------------------------------

class MonthClose(TimeStampedModel):
    """
    Locks a calendar month to prevent silent changes to past financials.
    Reopening requires the Owner permission and is audit-logged.
    """
    STATUS_CHOICES = (
        ('open', 'Open'),
        ('closed', 'Closed'),
        ('reopened', 'Reopened'),
    )

    year = models.PositiveSmallIntegerField()
    month = models.PositiveSmallIntegerField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='closed_months'
    )
    closed_at = models.DateTimeField(null=True, blank=True)
    reopened_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='reopened_months'
    )
    reopened_at = models.DateTimeField(null=True, blank=True)
    reopen_reason = models.TextField(blank=True)

    # Snapshot of key figures at close time
    net_revenue_snapshot = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    net_profit_snapshot = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))

    history = HistoricalRecords()

    class Meta:
        unique_together = ('year', 'month')
        ordering = ['-year', '-month']

    def __str__(self):
        return f"{self.year}-{self.month:02d} [{self.status}]"
