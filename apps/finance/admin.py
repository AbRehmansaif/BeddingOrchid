"""
Finance Admin
=============
Registers all finance models with sensible list views, filters, search and date hierarchy.
Dashboard view at /admin/finance/dashboard/.
"""

import csv
import json
import datetime
from decimal import Decimal
from django.contrib import admin
from django.urls import path, reverse
from django.utils.html import format_html, mark_safe
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db.models import Sum, DecimalField, F
from django.db.models.functions import Coalesce
from django.core.cache import cache
from django.http import HttpResponse, JsonResponse, HttpResponseForbidden
from django.utils import timezone

from .models import (
    FinanceSettings, VariantCost, AdSpendEntry, CourierCharge,
    CourierSettlement, ReturnRecord, ReturnItem, OperatingExpense,
    ExpenseCategory, OtherIncome, OrderFinancials, OrderItemCostSnapshot,
    DailyFinancialSummary, MonthClose, CourierRate, ExchangeRate,
)

ZERO = Decimal('0.00')


def finance_required(view_func):
    """Decorator: require finance.view_dashboard permission."""
    def wrapper(request, *args, **kwargs):
        if not request.user.has_perm('finance.view_dashboard'):
            return HttpResponseForbidden(
                "<h2>Access Denied</h2><p>You need the <strong>finance.view_dashboard</strong> permission.</p>"
            )
        return view_func(request, *args, **kwargs)
    return wrapper


# ---------------------------------------------------------------------------
# Finance Settings (Singleton)
# ---------------------------------------------------------------------------

@admin.register(FinanceSettings)
class FinanceSettingsAdmin(admin.ModelAdmin):
    fieldsets = (
        ('💰 Currency & Revenue', {
            'fields': ('base_currency', 'revenue_recognition', 'include_shipping_fee_in_revenue', 'include_cod_fee_in_revenue')
        }),
        ('📦 Cost Defaults', {
            'fields': ('default_packaging_cost_per_order', 'default_cod_fee_percent', 'payment_gateway_fee_percent')
        }),
        ('🏛️ Tax', {
            'fields': ('sales_tax_percent', 'sales_tax_included_in_prices', 'income_tax_percent')
        }),
        ('📈 Ad Spend & Allocation', {
            'fields': ('ad_cost_allocation_method', 'usd_to_base_default_rate')
        }),
        ('🚚 Operations', {
            'fields': ('min_margin_percent_alert', 'settlement_overdue_days',
                      'delivery_success_trailing_days', 'count_packaging_for_returns',
                      'fiscal_month_start_day')
        }),
        ('🔗 Meta Ads API', {
            'description': 'API token is read from the environment variable named in the field below — never stored in the database.',
            'fields': ('meta_ad_account_id', 'meta_ads_access_token_env_key'),
            'classes': ('collapse',),
        }),
    )

    def has_add_permission(self, request):
        return not FinanceSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if not request.user.has_perm('finance.view_dashboard'):
            return qs.none()
        return qs


# ---------------------------------------------------------------------------
# Variant Costs
# ---------------------------------------------------------------------------

@admin.register(VariantCost)
class VariantCostAdmin(admin.ModelAdmin):
    list_display = ('variant', 'unit_cost', 'packaging_cost', 'other_unit_cost', 'total_unit_cost', 'effective_from', 'note')
    list_filter = ('effective_from',)
    search_fields = ('variant__sku', 'variant__product__name', 'note')
    date_hierarchy = 'effective_from'
    ordering = ['-effective_from']

    def total_unit_cost(self, obj):
        total = obj.unit_cost + obj.packaging_cost + obj.other_unit_cost
        return format_html('<strong>Rs {:,.0f}</strong>', total)
    total_unit_cost.short_description = 'Total Unit Cost'

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if not request.user.has_perm('finance.view_dashboard'):
            return qs.none()
        return qs


# ---------------------------------------------------------------------------
# Ad Spend
# ---------------------------------------------------------------------------

@admin.register(AdSpendEntry)
class AdSpendEntryAdmin(admin.ModelAdmin):
    list_display = ('date', 'platform_badge', 'campaign', 'spend_base_display', 'impressions', 'clicks', 'platform_purchases', 'platform_roas_display', 'source')
    list_filter = ('platform', 'source', 'date')
    search_fields = ('campaign', 'account', 'adset')
    date_hierarchy = 'date'
    ordering = ['-date', 'platform']

    def platform_badge(self, obj):
        colors = {'meta': '#1877F2', 'google': '#4285F4', 'tiktok': '#000000', 'other': '#64748B'}
        bg = colors.get(obj.platform, '#64748B')
        return format_html(
            '<span style="background:{};color:white;padding:2px 8px;border-radius:4px;font-size:11px;font-weight:600;">{}</span>',
            bg, obj.get_platform_display()
        )
    platform_badge.short_description = 'Platform'

    def spend_base_display(self, obj):
        return format_html('<strong>Rs {:,.0f}</strong>', obj.spend_base)
    spend_base_display.short_description = 'Spend (PKR)'

    def platform_purchases(self, obj):
        return obj.purchases_reported
    platform_purchases.short_description = 'Platform Purchases'

    def platform_roas_display(self, obj):
        if obj.spend_base and obj.spend_base > 0:
            roas = obj.purchase_value_reported / obj.spend_base
            color = '#10B981' if roas >= 2 else '#EF4444'
            return format_html('<span style="color:{};">{:.2f}x</span>', color, roas)
        return '-'
    platform_roas_display.short_description = 'Platform ROAS'

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if not request.user.has_perm('finance.view_dashboard'):
            return qs.none()
        return qs


# ---------------------------------------------------------------------------
# Courier Charges & Settlements
# ---------------------------------------------------------------------------

class CourierChargeInline(admin.TabularInline):
    model = CourierCharge
    extra = 0
    readonly_fields = ('total_charge_display',)
    fields = ('tracking_number', 'forward_charge', 'cod_fee', 'return_charge', 'fuel_surcharge', 'tax_on_fee', 'total_charge_display', 'source')

    def total_charge_display(self, obj):
        return format_html('<strong>Rs {:,.0f}</strong>', obj.total_charge)
    total_charge_display.short_description = 'Total'


@admin.register(CourierSettlement)
class CourierSettlementAdmin(admin.ModelAdmin):
    list_display = ('statement_number', 'courier', 'statement_date', 'cod_collected_display', 'charges_deducted_display', 'net_paid_display', 'status_badge', 'paid_on')
    list_filter = ('courier', 'status', 'statement_date')
    search_fields = ('statement_number', 'reference')
    date_hierarchy = 'statement_date'
    inlines = [CourierChargeInline]

    def cod_collected_display(self, obj):
        return format_html('Rs {:,.0f}', obj.cod_collected)
    cod_collected_display.short_description = 'COD Collected'

    def charges_deducted_display(self, obj):
        return format_html('Rs {:,.0f}', obj.charges_deducted)
    charges_deducted_display.short_description = 'Deducted'

    def net_paid_display(self, obj):
        return format_html('<strong>Rs {:,.0f}</strong>', obj.net_paid_to_us)
    net_paid_display.short_description = 'Net Paid'

    def status_badge(self, obj):
        colors = {'pending': '#F59E0B', 'received': '#10B981', 'disputed': '#EF4444'}
        color = colors.get(obj.status, '#64748B')
        return format_html(
            '<span style="background:{};color:white;padding:3px 8px;border-radius:4px;font-size:11px;font-weight:600;">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Status'

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if not request.user.has_perm('finance.view_dashboard'):
            return qs.none()
        return qs


@admin.register(CourierCharge)
class CourierChargeAdmin(admin.ModelAdmin):
    list_display = ('order_link', 'courier', 'tracking_number', 'forward_charge', 'cod_fee', 'return_charge', 'total_charge_display', 'is_unmatched_badge', 'charged_on')
    list_filter = ('courier', 'source', 'is_unmatched', 'charged_on')
    search_fields = ('tracking_number', 'order__order_number')
    date_hierarchy = 'charged_on'
    actions = ['match_to_orders']

    def order_link(self, obj):
        if obj.order:
            url = reverse('admin:orders_order_change', args=[obj.order.pk])
            return format_html('<a href="{}">{}</a>', url, obj.order.order_number)
        return format_html('<span style="color:#EF4444;">⚠ Unmatched</span>')
    order_link.short_description = 'Order'

    def total_charge_display(self, obj):
        return format_html('<strong>Rs {:,.0f}</strong>', obj.total_charge)
    total_charge_display.short_description = 'Total'

    def is_unmatched_badge(self, obj):
        if obj.is_unmatched:
            return format_html('<span style="background:#EF4444;color:white;padding:2px 6px;border-radius:4px;font-size:11px;">UNMATCHED</span>')
        return format_html('<span style="color:#10B981;">✓</span>')
    is_unmatched_badge.short_description = 'Match'

    def match_to_orders(self, request, queryset):
        """Try to match unmatched charges to orders by tracking number."""
        from apps.orders.models import Order
        matched = 0
        for charge in queryset.filter(is_unmatched=True):
            try:
                order = Order.objects.get(tracking_number=charge.tracking_number)
                charge.order = order
                charge.is_unmatched = False
                charge.save()
                matched += 1
            except Order.DoesNotExist:
                pass
        messages.success(request, f"Matched {matched} charge(s) to orders.")
    match_to_orders.short_description = "Match selected to orders by tracking number"

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if not request.user.has_perm('finance.view_dashboard'):
            return qs.none()
        return qs


# ---------------------------------------------------------------------------
# Returns
# ---------------------------------------------------------------------------

class ReturnItemInline(admin.TabularInline):
    model = ReturnItem
    extra = 1
    fields = ('product_name', 'variant', 'quantity', 'condition', 'unit_cost_at_return')


@admin.register(ReturnRecord)
class ReturnRecordAdmin(admin.ModelAdmin):
    list_display = ('order_link', 'return_type_badge', 'loss_amount_display', 'refund_amount', 'received_on', 'restocked')
    list_filter = ('return_type', 'restocked', 'received_on')
    search_fields = ('order__order_number', 'reason')
    date_hierarchy = 'received_on'
    inlines = [ReturnItemInline]

    def order_link(self, obj):
        url = reverse('admin:orders_order_change', args=[obj.order.pk])
        return format_html('<a href="{}">{}</a>', url, obj.order.order_number)
    order_link.short_description = 'Order'

    def return_type_badge(self, obj):
        colors = {
            'customer_return': '#F59E0B',
            'courier_rto': '#EF4444',
            'refused_at_door': '#DC2626',
            'exchange': '#3B82F6',
            'failed_delivery': '#9CA3AF',
        }
        color = colors.get(obj.return_type, '#64748B')
        return format_html(
            '<span style="background:{};color:white;padding:3px 8px;border-radius:4px;font-size:11px;font-weight:600;">{}</span>',
            color, obj.get_return_type_display()
        )
    return_type_badge.short_description = 'Type'

    def loss_amount_display(self, obj):
        if obj.loss_amount > 0:
            return format_html('<span style="color:#EF4444;font-weight:600;">Rs {:,.0f}</span>', obj.loss_amount)
        return 'Rs 0'
    loss_amount_display.short_description = 'Loss Amount'


# ---------------------------------------------------------------------------
# Operating Expenses
# ---------------------------------------------------------------------------

@admin.register(ExpenseCategory)
class ExpenseCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_marketing', 'sort_order')
    list_editable = ('sort_order',)


@admin.register(OperatingExpense)
class OperatingExpenseAdmin(admin.ModelAdmin):
    list_display = ('date', 'category', 'amount_display', 'description', 'is_recurring', 'recurrence', 'attachment_link')
    list_filter = ('category', 'is_recurring', 'date')
    search_fields = ('description', 'notes')
    date_hierarchy = 'date'

    def amount_display(self, obj):
        return format_html('Rs {:,.0f}', obj.amount)
    amount_display.short_description = 'Amount'

    def attachment_link(self, obj):
        if obj.attachment:
            return format_html('<a href="{}" target="_blank">📎 View</a>', obj.attachment.url)
        return '-'
    attachment_link.short_description = 'Receipt'

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if not request.user.has_perm('finance.view_dashboard'):
            return qs.none()
        return qs


@admin.register(OtherIncome)
class OtherIncomeAdmin(admin.ModelAdmin):
    list_display = ('date', 'description', 'amount')
    date_hierarchy = 'date'


# ---------------------------------------------------------------------------
# Order Financials (read-only)
# ---------------------------------------------------------------------------

@admin.register(OrderFinancials)
class OrderFinancialsAdmin(admin.ModelAdmin):
    list_display = ('order_link', 'net_revenue_display', 'gross_profit_display', 'contribution_profit_display', 'total_courier_display', 'is_estimated_badge', 'cost_missing_badge', 'calculated_at')
    list_filter = ('is_estimated', 'cost_missing')
    search_fields = ('order__order_number', 'order__customer_name')
    date_hierarchy = 'calculated_at'
    readonly_fields = [f.name for f in OrderFinancials._meta.fields]
    actions = ['recalculate_selected']

    def order_link(self, obj):
        url = reverse('admin:orders_order_change', args=[obj.order.pk])
        return format_html('<a href="{}">{}</a>', url, obj.order.order_number)
    order_link.short_description = 'Order'

    def net_revenue_display(self, obj):
        return format_html('Rs {:,.0f}', obj.net_revenue)
    net_revenue_display.short_description = 'Net Revenue'

    def gross_profit_display(self, obj):
        color = '#10B981' if obj.gross_profit >= 0 else '#EF4444'
        return format_html('<span style="color:{};">Rs {:,.0f}</span>', color, obj.gross_profit)
    gross_profit_display.short_description = 'Gross Profit'

    def contribution_profit_display(self, obj):
        color = '#10B981' if obj.contribution_profit_before_ads >= 0 else '#EF4444'
        return format_html('<span style="color:{};">Rs {:,.0f}</span>', color, obj.contribution_profit_before_ads)
    contribution_profit_display.short_description = 'Contribution Profit'

    def total_courier_display(self, obj):
        return format_html('Rs {:,.0f}', obj.total_courier_cost)
    total_courier_display.short_description = 'Courier Cost'

    def is_estimated_badge(self, obj):
        if obj.is_estimated:
            return format_html('<span style="background:#F59E0B;color:white;padding:2px 6px;border-radius:4px;font-size:11px;">EST</span>')
        return format_html('<span style="color:#10B981;">✓</span>')
    is_estimated_badge.short_description = 'Courier'

    def cost_missing_badge(self, obj):
        if obj.cost_missing:
            return format_html('<span style="background:#EF4444;color:white;padding:2px 6px;border-radius:4px;font-size:11px;">MISSING</span>')
        return format_html('<span style="color:#10B981;">✓</span>')
    cost_missing_badge.short_description = 'Cost'

    def recalculate_selected(self, request, queryset):
        from apps.finance.tasks import recalculate_order_financials
        count = 0
        for fin in queryset:
            recalculate_order_financials.delay(fin.order_id)
            count += 1
        messages.success(request, f"Queued recalculation for {count} orders.")
    recalculate_selected.short_description = "Recalculate financials for selected orders"

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if not request.user.has_perm('finance.view_dashboard'):
            return qs.none()
        return qs


# ---------------------------------------------------------------------------
# Other model registrations
# ---------------------------------------------------------------------------

@admin.register(CourierRate)
class CourierRateAdmin(admin.ModelAdmin):
    list_display = ('courier', 'city_or_zone', 'forward_charge', 'return_charge', 'cod_fee_percent', 'fuel_percent', 'effective_from')
    list_filter = ('courier',)
    date_hierarchy = 'effective_from'


@admin.register(ExchangeRate)
class ExchangeRateAdmin(admin.ModelAdmin):
    list_display = ('date', 'from_currency', 'to_currency', 'rate')
    date_hierarchy = 'date'


@admin.register(DailyFinancialSummary)
class DailyFinancialSummaryAdmin(admin.ModelAdmin):
    list_display = ('date', 'net_revenue_d', 'gross_profit_d', 'ad_spend_d', 'net_profit_d', 'orders_delivered', 'has_missing_costs', 'has_estimated_charges')
    list_filter = ('has_missing_costs', 'has_estimated_charges', 'has_missing_ad_spend')
    date_hierarchy = 'date'
    actions = ['rebuild_selected']
    readonly_fields = [f.name for f in DailyFinancialSummary._meta.fields]

    def net_revenue_d(self, obj):
        return format_html('Rs {:,.0f}', obj.net_revenue)
    net_revenue_d.short_description = 'Revenue'

    def gross_profit_d(self, obj):
        return format_html('Rs {:,.0f}', obj.gross_profit)
    gross_profit_d.short_description = 'Gross Profit'

    def ad_spend_d(self, obj):
        return format_html('Rs {:,.0f}', obj.ad_spend)
    ad_spend_d.short_description = 'Ad Spend'

    def net_profit_d(self, obj):
        color = '#10B981' if obj.net_profit >= 0 else '#EF4444'
        return format_html('<span style="color:{};">Rs {:,.0f}</span>', color, obj.net_profit)
    net_profit_d.short_description = 'Net Profit'

    def rebuild_selected(self, request, queryset):
        from apps.finance.tasks import rebuild_daily_summary
        for row in queryset:
            rebuild_daily_summary.delay(row.date.isoformat(), row.date.isoformat())
        messages.success(request, f"Queued rebuild for {queryset.count()} day(s).")
    rebuild_selected.short_description = "Rebuild selected daily summaries"

    def has_add_permission(self, request):
        return False

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if not request.user.has_perm('finance.view_dashboard'):
            return qs.none()
        return qs


@admin.register(MonthClose)
class MonthCloseAdmin(admin.ModelAdmin):
    list_display = ('period', 'status_badge', 'net_revenue_snapshot', 'net_profit_snapshot', 'closed_by', 'closed_at')
    list_filter = ('status',)
    readonly_fields = ('closed_by', 'closed_at', 'reopened_by', 'reopened_at', 'net_revenue_snapshot', 'net_profit_snapshot')
    actions = ['close_month', 'reopen_month']

    def period(self, obj):
        return f"{obj.year}-{obj.month:02d}"
    period.short_description = 'Month'

    def status_badge(self, obj):
        colors = {'open': '#10B981', 'closed': '#1E293B', 'reopened': '#F59E0B'}
        color = colors.get(obj.status, '#64748B')
        return format_html(
            '<span style="background:{};color:white;padding:3px 8px;border-radius:4px;font-size:11px;font-weight:600;">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Status'

    def close_month(self, request, queryset):
        for mc in queryset.filter(status='open'):
            mc.status = 'closed'
            mc.closed_by = request.user
            mc.closed_at = timezone.now()
            mc.save()
        messages.success(request, "Selected months closed.")
    close_month.short_description = "Close selected months"

    def reopen_month(self, request, queryset):
        if not request.user.has_perm('finance.can_reopen_month'):
            messages.error(request, "You need the 'can_reopen_month' permission.")
            return
        for mc in queryset.filter(status='closed'):
            mc.status = 'reopened'
            mc.reopened_by = request.user
            mc.reopened_at = timezone.now()
            mc.save()
        messages.success(request, "Selected months reopened.")
    reopen_month.short_description = "Reopen selected months (Owner only)"

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if not request.user.has_perm('finance.view_dashboard'):
            return qs.none()
        return qs


# ---------------------------------------------------------------------------
# Custom Admin Views (Dashboard, Finance Guide, Breakeven Calculator)
# ---------------------------------------------------------------------------

class FinanceAdminSite(admin.ModelAdmin):
    """Mixin to inject custom URLs into admin."""
    pass


def get_date_range_from_request(request):
    """Parse date range from GET params with sensible defaults."""
    preset = request.GET.get('preset', '30d')
    today = timezone.now().date()

    if preset == 'today':
        return today, today
    elif preset == 'yesterday':
        d = today - datetime.timedelta(days=1)
        return d, d
    elif preset == '7d':
        return today - datetime.timedelta(days=6), today
    elif preset == 'this_month':
        return today.replace(day=1), today
    elif preset == 'last_month':
        first_this = today.replace(day=1)
        last_month_end = first_this - datetime.timedelta(days=1)
        return last_month_end.replace(day=1), last_month_end
    elif preset == 'custom':
        try:
            df = datetime.date.fromisoformat(request.GET.get('date_from', ''))
            dt = datetime.date.fromisoformat(request.GET.get('date_to', ''))
            return df, dt
        except Exception:
            pass

    # Default: 30 days
    return today - datetime.timedelta(days=29), today


# Register our custom admin views by monkey-patching the admin site
_original_get_urls = admin.site.__class__.get_urls


def _finance_get_urls(self):
    from django.urls import path
    original = _original_get_urls(self)
    custom = [
        path('finance/dashboard/', self.admin_view(finance_dashboard_view), name='finance_dashboard'),
        path('finance/dashboard/api/', self.admin_view(finance_dashboard_api), name='finance_dashboard_api'),
        path('finance/dashboard/export-csv/', self.admin_view(finance_export_csv_view), name='finance_export_csv'),
        path('finance/dashboard/export-excel/', self.admin_view(finance_export_excel_view), name='finance_export_excel'),
        path('finance/dashboard/report/', self.admin_view(finance_report_view), name='finance_report'),
        path('finance/guide/', self.admin_view(finance_guide_view), name='finance_guide'),
        path('finance/breakeven/', self.admin_view(finance_breakeven_view), name='finance_breakeven'),
        path('finance/returns/receive/', self.admin_view(finance_returns_receive_view), name='finance_returns_receive'),
        path('finance/courier/import/', self.admin_view(finance_courier_import_view), name='finance_courier_import'),
        path('finance/adspend/import/', self.admin_view(finance_adspend_import_view), name='finance_adspend_import'),
    ]
    return custom + original


admin.site.__class__.get_urls = _finance_get_urls


@finance_required
def finance_dashboard_view(request):
    """Main dashboard page."""
    from apps.finance.services.dashboard import DashboardService

    date_from, date_to = get_date_range_from_request(request)
    preset = request.GET.get('preset', '30d')

    # Try cache first (short TTL)
    cache_key = f'finance_dashboard_{date_from}_{date_to}'
    summary = cache.get(cache_key)
    if not summary:
        summary = DashboardService.get_summary(date_from, date_to)
        cache.set(cache_key, summary, timeout=300)  # 5 min cache

    alerts = DashboardService.get_alerts(date_from, date_to)
    by_courier = list(DashboardService.get_by_courier(date_from, date_to))
    by_city = list(DashboardService.get_by_city(date_from, date_to))[:10]
    by_campaign = list(DashboardService.get_by_campaign(date_from, date_to))
    daily_trend = DashboardService.get_daily_trend(date_from, date_to)
    cash = DashboardService.get_cash_view(date_from, date_to)

    # Compute previous period for comparison
    delta = (date_to - date_from).days + 1
    prev_from = date_from - datetime.timedelta(days=delta)
    prev_to = date_from - datetime.timedelta(days=1)
    prev_summary = DashboardService.get_summary(prev_from, prev_to)

    def pct_change(current, prev):
        if not prev or prev == 0:
            return None
        return float(((current - prev) / abs(prev)) * 100)

    changes = {
        'net_revenue': pct_change(summary['net_revenue'], prev_summary['net_revenue']),
        'gross_profit': pct_change(summary['gross_profit'], prev_summary['gross_profit']),
        'net_profit': pct_change(summary['net_profit'], prev_summary['net_profit']),
        'ad_spend': pct_change(summary['ad_spend'], prev_summary['ad_spend']),
        'total_courier_cost': pct_change(summary['total_courier_cost'], prev_summary['total_courier_cost']),
    }

    context = {
        **admin.site.each_context(request),
        'title': '💰 Profit & Finance Dashboard',
        'summary': summary,
        'prev_summary': prev_summary,
        'changes': changes,
        'alerts': alerts,
        'by_courier': by_courier,
        'by_city': by_city,
        'by_campaign': by_campaign,
        'daily_trend_json': json.dumps([
            {
                'date': str(r['date']),
                'net_revenue': float(r['net_revenue']),
                'ad_spend': float(r['ad_spend']),
                'net_profit': float(r['net_profit']),
                'orders_delivered': r['orders_delivered'],
            }
            for r in daily_trend
        ], default=str),
        'cash': cash,
        'date_from': date_from,
        'date_to': date_to,
        'preset': preset,
    }
    return render(request, 'admin/finance/dashboard.html', context)


@finance_required
def finance_dashboard_api(request):
    """JSON API for dashboard data (HTMX/fetch refresh)."""
    from apps.finance.services.dashboard import DashboardService

    date_from, date_to = get_date_range_from_request(request)
    summary = DashboardService.get_summary(date_from, date_to)

    # Convert Decimal to float for JSON
    return JsonResponse({k: float(v) if isinstance(v, Decimal) else v for k, v in summary.items()})


@finance_required
def finance_guide_view(request):
    """Finance Guide page with all definitions and formulas."""
    context = {
        **admin.site.each_context(request),
        'title': '📖 Finance Guide — Definitions & Formulas',
    }
    return render(request, 'admin/finance/guide.html', context)


@finance_required
def finance_breakeven_view(request):
    """Break-even Calculator."""
    result = None
    if request.method == 'POST':
        try:
            price = Decimal(request.POST['price'])
            cost = Decimal(request.POST['cost'])
            courier_charge = Decimal(request.POST['courier_charge'])
            return_rate = Decimal(request.POST['return_rate']) / 100
            ad_cpa = Decimal(request.POST['ad_cpa'])
            cod_fee_pct = Decimal(request.POST.get('cod_fee_pct', '2')) / 100
            packaging = Decimal(request.POST.get('packaging', '60'))

            courier_return = Decimal(request.POST.get('courier_return', '150'))
            effective_courier = courier_charge + (return_rate * courier_return)
            effective_cogs = cost + packaging

            net_revenue = price
            contribution = net_revenue - effective_cogs - effective_courier - (price * cod_fee_pct)
            contribution_after_ads = contribution - ad_cpa
            margin_pct = (contribution / price * 100) if price else Decimal('0')

            break_even_roas = (Decimal('1') / (contribution / price)) if contribution > 0 else None

            result = {
                'price': price,
                'cogs': effective_cogs,
                'courier': effective_courier,
                'cod_fee': price * cod_fee_pct,
                'contribution_before_ads': contribution,
                'ad_cpa': ad_cpa,
                'contribution_after_ads': contribution_after_ads,
                'margin_pct': margin_pct,
                'break_even_roas': break_even_roas,
                'is_profitable': contribution_after_ads > 0,
            }
        except Exception as e:
            messages.error(request, f"Calculation error: {e}")

    context = {
        **admin.site.each_context(request),
        'title': '🧮 Break-even Calculator',
        'result': result,
    }
    return render(request, 'admin/finance/breakeven.html', context)


@finance_required
def finance_returns_receive_view(request):
    """Barcode/scan-friendly Returns & RTO receiving station."""
    from apps.orders.models import Order
    from apps.finance.models import ReturnRecord, ReturnItem, CourierCharge, FinanceSettings
    from apps.finance.services import OrderFinancialsService

    query = request.GET.get('q', '').strip()
    order = None
    default_return_charge = Decimal('150.00')

    if query:
        order = (
            Order.objects.filter(tracking_number__iexact=query).first()
            or Order.objects.filter(order_number__iexact=query).first()
        )
        if order:
            try:
                cc = order.courier_charge
                if cc.return_charge > 0:
                    default_return_charge = cc.return_charge
            except Exception:
                pass

    if request.method == 'POST':
        order_id = request.POST.get('order_id')
        order = get_object_or_404(Order, pk=order_id)
        reason = request.POST.get('reason', 'refused')
        ret_charge = Decimal(request.POST.get('return_charge', '150.00') or '0')
        refund_amount = Decimal(request.POST.get('refund_amount', '0.00') or '0')

        ret_record, _ = ReturnRecord.objects.get_or_create(
            order=order,
            defaults={
                'return_type': 'rto' if reason == 'refused' else 'customer_return',
                'reason': reason,
                'refund_amount': refund_amount,
            }
        )

        total_damage_loss = ZERO
        all_returned = True
        total_items_returned = 0

        for item in order.items.all():
            qty_returned = int(request.POST.get(f'qty_{item.id}', 0) or 0)
            if qty_returned <= 0:
                all_returned = False
                continue

            total_items_returned += qty_returned
            condition = request.POST.get(f'condition_{item.id}', 'sellable')
            restock = bool(request.POST.get(f'restock_{item.id}'))

            unit_cost = ZERO
            try:
                if hasattr(item, 'cost_snapshot'):
                    unit_cost = item.cost_snapshot.unit_cost_snapshot
            except Exception:
                pass

            if condition in ('damaged', 'lost'):
                total_damage_loss += Decimal(qty_returned) * unit_cost

            if restock and condition == 'sellable' and item.variant:
                item.variant.stock_quantity = F('stock_quantity') + qty_returned
                item.variant.save(update_fields=['stock_quantity'])

            ReturnItem.objects.create(
                return_record=ret_record,
                variant=item.variant,
                product_name=item.product_name,
                quantity=qty_returned,
                condition=condition,
                unit_cost_at_return=unit_cost,
            )

        ret_record.loss_amount = total_damage_loss
        ret_record.save(update_fields=['loss_amount'])

        # Update courier return charge
        cc = getattr(order, 'courier_charge', None)
        if cc:
            cc.return_charge = ret_charge
            cc.save(update_fields=['return_charge'])
        else:
            CourierCharge.objects.create(
                order=order,
                courier=order.courier or 'TCS',
                tracking_number=order.tracking_number or f"RET-{order.order_number}",
                return_charge=ret_charge,
            )

        if all_returned or reason == 'refused':
            order.status = 'returned'
        else:
            order.status = 'partially_returned' if hasattr(order, 'status') else 'returned'
        order.save(update_fields=['status'])

        OrderFinancialsService.calculate(order)

        messages.success(request, f"✓ Processed return for Order #{order.order_number}. Logged {total_items_returned} items (Damage Loss: Rs. {total_damage_loss:,.2f}).")
        return redirect('admin:finance_returns_receive')

    today = timezone.localdate()
    recent_returns = ReturnRecord.objects.filter(created_at__date=today).select_related('order').prefetch_related('items')[:15]

    context = {
        **admin.site.each_context(request),
        'title': '📦 Receive Returns & RTO Station',
        'query': query,
        'order': order,
        'default_return_charge': default_return_charge,
        'recent_returns': recent_returns,
    }
    return render(request, 'admin/finance/receive_returns.html', context)


@finance_required
def finance_courier_import_view(request):
    """Import courier statement CSV."""
    from apps.finance.importers.courier_statement import CourierStatementImporter
    result = None

    if request.method == 'POST' and request.FILES.get('csv_file'):
        courier = request.POST.get('courier', 'tcs')
        update_status = bool(request.POST.get('update_order_status'))
        file_obj = request.FILES['csv_file']
        content = file_obj.read()

        importer = CourierStatementImporter(courier_name=courier, file_content=content, update_order_status=update_status)
        result = importer.parse_and_process()

        if result.get('errors'):
            for err in result['errors'][:5]:
                messages.warning(request, err)
        messages.success(
            request,
            f"Statement processed: {result.get('matched', 0)} matched orders, {result.get('created', 0)} charges created, Rs. {result.get('total_cod_collected', 0):,.2f} COD collected."
        )

    context = {
        **admin.site.each_context(request),
        'title': '🚚 Import Courier Statement',
        'result': result,
    }
    return render(request, 'admin/finance/import_courier.html', context)


@finance_required
def finance_adspend_import_view(request):
    """Import Ad Spend CSV."""
    from apps.finance.importers.ad_spend_csv import AdSpendCSVImporter
    result = None

    if request.method == 'POST' and request.FILES.get('csv_file'):
        platform = request.POST.get('platform', 'meta')
        currency = request.POST.get('currency', 'USD')
        file_obj = request.FILES['csv_file']
        content = file_obj.read()

        importer = AdSpendCSVImporter(platform=platform, default_currency=currency)
        result = importer.process(content)

        if result.get('errors'):
            for err in result['errors'][:5]:
                messages.warning(request, err)
        messages.success(
            request,
            f"Ad spend imported: {result.get('created', 0)} created, {result.get('updated', 0)} updated. Spend: Rs. {result.get('total_spend_base', 0):,.2f} across {result.get('dates_count', 0)} days."
        )

    context = {
        **admin.site.each_context(request),
        'title': '📈 Import Ad Spend CSV',
        'result': result,
    }
    return render(request, 'admin/finance/import_adspend.html', context)


@finance_required
def finance_export_csv_view(request):
    """Export P&L and key metrics as CSV."""
    from apps.finance.services.dashboard import DashboardService
    date_from, date_to = get_date_range_from_request(request)
    summary = DashboardService.get_summary(date_from, date_to)

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="finance_pnl_{date_from}_{date_to}.csv"'
    writer = csv.writer(response)

    writer.writerow(['Financial Metric / Line Item', 'Amount (PKR)'])
    writer.writerow(['Reporting Period', f'{date_from} to {date_to}'])
    writer.writerow([])
    writer.writerow(['Gross Sales', summary['gross_sales']])
    writer.writerow(['Discounts', summary['discount_total']])
    writer.writerow(['Customer Refunds', summary['refund_total']])
    writer.writerow(['Shipping & COD Fees Collected', summary['shipping_income'] + summary['cod_fee_income']])
    writer.writerow(['NET REVENUE', summary['net_revenue']])
    writer.writerow([])
    writer.writerow(['Cost of Goods Sold (COGS)', summary['product_cost']])
    writer.writerow(['Packaging Materials', summary['packaging_cost']])
    writer.writerow(['GROSS PROFIT', summary['gross_profit']])
    writer.writerow(['Gross Margin %', f"{summary['gross_margin_pct']}%"])
    writer.writerow([])
    writer.writerow(['Courier Forward Freight', summary['courier_forward']])
    writer.writerow(['Courier COD Fees', summary['courier_cod_fee']])
    writer.writerow(['Courier Return Charges', summary['courier_return']])
    writer.writerow(['Courier Other / Fuel / Tax', summary['courier_other']])
    writer.writerow(['Total Courier Expenses', summary['total_courier_cost']])
    writer.writerow(['Return Damage & Lost Write-offs', summary['return_loss']])
    writer.writerow(['Payment Gateway Fees', summary['payment_gateway_fee']])
    writer.writerow(['CONTRIBUTION PROFIT (BEFORE ADS)', summary['contribution_profit_before_ads']])
    writer.writerow([])
    writer.writerow(['Advertising Spend', summary['ad_spend']])
    writer.writerow(['CONTRIBUTION PROFIT (AFTER ADS)', summary['contribution_profit']])
    writer.writerow(['Operating Expenses (Overheads)', summary['operating_expenses']])
    writer.writerow(['TRUE NET PROFIT', summary['net_profit']])
    writer.writerow(['Net Margin %', f"{summary['net_margin_pct']}%"])
    writer.writerow([])
    writer.writerow(['Delivered Orders', summary['orders_delivered']])
    writer.writerow(['Dispatched Orders', summary['orders_dispatched']])
    writer.writerow(['Delivery Success Rate', f"{summary['delivery_success_rate']}%"])
    writer.writerow(['RTO Rate', f"{summary['rto_rate']}%"])
    writer.writerow(['Profit per Delivered Order', summary['profit_per_delivered_order']])
    writer.writerow(['Real CPA', summary['real_cpa']])
    writer.writerow(['Real ROAS', summary['real_roas']])
    writer.writerow(['Platform ROAS', summary['platform_roas']])

    return response


@finance_required
def finance_export_excel_view(request):
    """Excel export (returns CSV with excel content disposition)."""
    response = finance_export_csv_view(request)
    date_from, date_to = get_date_range_from_request(request)
    response['Content-Type'] = 'application/vnd.ms-excel'
    response['Content-Disposition'] = f'attachment; filename="finance_pnl_{date_from}_{date_to}.xls"'
    return response


@finance_required
def finance_report_view(request):
    """Executive printable statement."""
    from apps.finance.services.dashboard import DashboardService
    date_from, date_to = get_date_range_from_request(request)
    summary = DashboardService.get_summary(date_from, date_to)

    context = {
        'summary': summary,
        'date_from': date_from,
        'date_to': date_to,
    }
    return render(request, 'admin/finance/report.html', context)
