import csv
from django.contrib import admin
from django.http import HttpResponse
from django.urls import path, reverse
from django.utils.html import format_html, mark_safe
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from .models import Order, OrderItem, OrderStatusHistory
from .services import OrderService

class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ('product_name', 'variant_sku', 'size_name', 'color_name', 'unit_price', 'quantity', 'line_total', 'item_preview')
    fields = ('item_preview', 'product_name', 'variant_sku', 'size_name', 'color_name', 'unit_price', 'quantity', 'line_total')

    def item_preview(self, obj):
        if obj.image_url:
            return format_html('<img src="{}" style="width: 45px; height: 45px; object-fit: cover; border-radius: 4px;" />', obj.image_url)
        return "-"
    item_preview.short_description = "Image"

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class OrderStatusHistoryInline(admin.TabularInline):
    model = OrderStatusHistory
    extra = 0
    readonly_fields = ('from_status', 'to_status', 'changed_by', 'note', 'notify_customer', 'created_at')
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        'order_number', 'customer_name', 'customer_phone', 'shipping_city',
        'status_badge', 'payment_status_badge', 'grand_total_formatted',
        'courier_display', 'placed_at', 'action_buttons'
    )
    list_filter = ('status', 'payment_status', 'shipping_city', 'courier', 'placed_at')
    search_fields = ('order_number', 'customer_name', 'customer_phone', 'customer_email', 'shipping_address_line1', 'tracking_number')
    date_hierarchy = 'placed_at'
    inlines = [OrderItemInline, OrderStatusHistoryInline]
    actions = [
        'print_bulk_shipping_labels', 'export_to_courier_csv',
        'mark_as_confirmed', 'mark_as_packed', 'mark_as_dispatched',
        'recalculate_financials_action', 'apply_courier_rate_action'
    ]

    fieldsets = (
        ('Order Overview & Pipeline', {
            'fields': (
                'order_number', 'status', 'status_actions_display', 'placed_at',
                'user', 'customer_note', 'admin_note'
            )
        }),
        ('Customer Contact (Snapshot)', {
            'fields': ('customer_name', 'customer_phone', 'customer_email')
        }),
        ('Shipping Address (Editable upon customer request)', {
            'description': 'Customer phoned to correct their address? You can update the delivery details below.',
            'fields': (
                'shipping_full_name', 'shipping_phone', 'shipping_address_line1',
                'shipping_address_line2', 'shipping_landmark', 'shipping_city',
                'shipping_province', 'shipping_postal_code', 'shipping_country'
            )
        }),
        ('Courier & Fulfillment Tracking', {
            'fields': ('courier', 'tracking_number', 'tracking_url')
        }),
        ('Financials & Payment (Read-Only Snapshots)', {
            'fields': (
                'payment_method', 'payment_status', 'subtotal', 'discount_total',
                'coupon_code', 'shipping_fee', 'cod_fee', 'grand_total'
            )
        }),
        ('Marketing Attribution & Audit', {
            'classes': ('collapse',),
            'fields': ('utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 'utm_term', 'fbp', 'fbc', 'ip_address', 'user_agent')
        }),
    )

    readonly_fields = (
        'order_number', 'placed_at', 'status_actions_display',
        'payment_method', 'subtotal', 'discount_total', 'coupon_code',
        'shipping_fee', 'cod_fee', 'grand_total',
        'utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 'utm_term', 'fbp', 'fbc', 'ip_address', 'user_agent'
    )

    def status_badge(self, obj):
        colors = {
            'pending': '#F59E0B',     # Amber
            'confirmed': '#3B82F6',   # Blue
            'processing': '#6366F1',  # Indigo
            'packed': '#8B5CF6',      # Purple
            'dispatched': '#06B6D4',  # Cyan
            'delivered': '#10B981',   # Emerald
            'on_hold': '#64748B',     # Slate
            'cancelled': '#EF4444',   # Red
            'returned': '#DC2626',    # Dark Red
            'refunded': '#9CA3AF',    # Gray
        }
        bg = colors.get(obj.status, '#64748B')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 4px 10px; border-radius: 9999px; font-weight: 600; font-size: 11px; text-transform: uppercase;">{}</span>',
            bg, obj.get_status_display()
        )
    status_badge.short_description = "Status"

    def payment_status_badge(self, obj):
        color = '#10B981' if obj.payment_status == 'paid' else ('#EF4444' if obj.payment_status == 'refunded' else '#F59E0B')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 4px; font-weight: 600; font-size: 11px;">{}</span>',
            color, obj.get_payment_status_display()
        )
    payment_status_badge.short_description = "Payment"

    def grand_total_formatted(self, obj):
        # format_html wraps args as SafeString; numeric format codes fail on SafeString.
        # Pre-format the number to a plain string, then pass it in.
        formatted = '{:,.0f}'.format(float(obj.grand_total))
        return format_html('<strong>Rs. {}</strong>', formatted)
    grand_total_formatted.short_description = "Total"

    def courier_display(self, obj):
        if obj.tracking_number:
            url = obj.tracking_url or OrderService.get_courier_tracking_url(obj.courier, obj.tracking_number)
            if url:
                return format_html('<a href="{}" target="_blank" style="color: #2563EB; font-weight: 500;">{} #{}</a>', url, obj.courier or 'Courier', obj.tracking_number)
            return f"{obj.courier}: {obj.tracking_number}"
        return "-"
    courier_display.short_description = "Tracking"

    def action_buttons(self, obj):
        invoice_url = reverse('orders:admin_invoice', args=[obj.order_number])
        return format_html(
            '<a href="{}" target="_blank" class="button" style="background:#1E293B; color:white; padding:4px 8px; border-radius:4px; font-size:11px; text-decoration:none;">📄 Invoice</a>',
            invoice_url
        )
    action_buttons.short_description = "Print"

    def status_actions_display(self, obj):
        if not obj.pk:
            return "-"
        transitions = [
            ('confirmed', 'Verify & Confirm', '#3B82F6'),
            ('processing', 'Send to Processing', '#6366F1'),
            ('packed', 'Mark as Packed', '#8B5CF6'),
            ('dispatched', 'Mark Dispatched', '#06B6D4'),
            ('delivered', 'Mark Delivered & Paid', '#10B981'),
            ('cancelled', 'Cancel Order', '#EF4444'),
        ]
        buttons = []
        for st, label, bg in transitions:
            if st != obj.status:
                url = reverse('orders:admin_change_status', args=[obj.order_number, st])
                buttons.append(
                    f'<a href="{url}" style="background-color: {bg}; color: white; padding: 6px 12px; border-radius: 6px; text-decoration: none; font-size: 12px; margin-right: 6px; display: inline-block;">{label}</a>'
                )
        return format_html(" ".join(buttons))
    status_actions_display.short_description = "Quick Status Actions"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('<str:order_number>/status/<str:new_status>/', self.admin_site.admin_view(self.change_status_view), name='orders_order_change_status'),
            path('<str:order_number>/recalculate-financials/', self.admin_site.admin_view(self.recalculate_financials_view), name='orders_order_recalculate_financials'),
        ]
        return custom_urls + urls

    def recalculate_financials_view(self, request, order_number):
        if not request.user.has_perm('finance.view_dashboard'):
            messages.error(request, "Permission denied: finance.view_dashboard required.")
            return redirect('admin:orders_order_changelist')
        order = get_object_or_404(Order, order_number=order_number)
        try:
            from apps.finance.services import OrderFinancialsService
            OrderFinancialsService.calculate(order)
            messages.success(request, f"Financials recalculated for order #{order_number}.")
        except Exception as e:
            messages.error(request, f"Error recalculating financials: {e}")
        return redirect('admin:orders_order_change', order.pk)

    def finance_summary_panel(self, obj):
        if not obj or not obj.pk:
            return "-"
        try:
            fin = obj.financials
        except Exception:
            try:
                from apps.finance.services import OrderFinancialsService
                fin = OrderFinancialsService.calculate(obj)
            except Exception:
                fin = None
        if not fin:
            return format_html('<span style="color:#94A3B8;">No financials recorded yet.</span>')

        recalc_url = reverse('admin:orders_order_recalculate_financials', args=[obj.order_number])
        badge_bg = '#F59E0B' if fin.is_estimated else '#10B981'
        badge_text = '⚠️ ESTIMATED' if fin.is_estimated else '✓ ACTUAL CHARGES'
        missing_cost_warning = ''
        if fin.cost_missing:
            missing_cost_warning = '<div style="background:rgba(239,68,68,0.2); color:#EF4444; border:1px solid #EF4444; border-radius:4px; padding:6px 10px; margin-bottom:10px; font-size:12px;">⚠️ One or more items in this order have missing cost snapshots. Product cost may be understated!</div>'

        profit_color = '#10B981' if fin.contribution_profit > 0 else '#EF4444'

        return format_html(
            '''
            <div style="background:#0F172A; border:1px solid #334155; border-radius:8px; padding:16px; color:#E2E8F0; font-family:system-ui,sans-serif; max-width:850px;">
                {warning}
                <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid #334155; padding-bottom:10px; margin-bottom:14px;">
                    <div style="display:flex; align-items:center; gap:8px;">
                        <span style="font-weight:700; font-size:14px; color:#fff;">📊 Unit Economics & Contribution Profit</span>
                        <span style="background:{badge_bg}; color:#000; font-weight:700; font-size:10px; padding:2px 8px; border-radius:9999px;">{badge_text}</span>
                    </div>
                    <a href="{recalc_url}" style="background:#6366F1; color:#fff; padding:5px 12px; border-radius:6px; font-size:11px; text-decoration:none; font-weight:600;">⚡ Recalculate</a>
                </div>
                <div style="display:grid; grid-template-columns:repeat(4, 1fr); gap:12px; margin-bottom:14px;">
                    <div style="background:#1E293B; padding:10px; border-radius:6px;">
                        <div style="font-size:11px; color:#94A3B8; text-transform:uppercase;">Net Revenue</div>
                        <div style="font-size:16px; font-weight:700; color:#fff;">Rs. {net_rev:,.2f}</div>
                    </div>
                    <div style="background:#1E293B; padding:10px; border-radius:6px;">
                        <div style="font-size:11px; color:#94A3B8; text-transform:uppercase;">COGS (Product)</div>
                        <div style="font-size:16px; font-weight:700; color:#F87171;">-Rs. {cogs:,.2f}</div>
                    </div>
                    <div style="background:#1E293B; padding:10px; border-radius:6px;">
                        <div style="font-size:11px; color:#94A3B8; text-transform:uppercase;">Courier Cost</div>
                        <div style="font-size:16px; font-weight:700; color:#F87171;">-Rs. {courier:,.2f}</div>
                    </div>
                    <div style="background:#1E293B; padding:10px; border-radius:6px; border:1px solid {profit_color};">
                        <div style="font-size:11px; color:#94A3B8; text-transform:uppercase;">Contribution Profit</div>
                        <div style="font-size:16px; font-weight:700; color:{profit_color};">Rs. {contrib:,.2f}</div>
                    </div>
                </div>
                <div style="background:#1E293B; border-radius:6px; padding:10px 14px; font-size:12px; line-height:1.8;">
                    <div style="display:flex; justify-content:space-between; border-bottom:1px solid #334155; padding:4px 0;">
                        <span style="color:#94A3B8;">Gross Sales:</span>
                        <span>Rs. {gross:,.2f}</span>
                    </div>
                    <div style="display:flex; justify-content:space-between; border-bottom:1px solid #334155; padding:4px 0;">
                        <span style="color:#94A3B8;">Packaging Expense:</span>
                        <span style="color:#F87171;">-Rs. {pkg:,.2f}</span>
                    </div>
                    <div style="display:flex; justify-content:space-between; border-bottom:1px solid #334155; padding:4px 0;">
                        <span style="color:#94A3B8;">Courier Breakdown (Fwd / COD / Return / Other):</span>
                        <span>Rs. {fwd:,.2f} / Rs. {cod:,.2f} / Rs. {ret:,.2f} / Rs. {oth:,.2f}</span>
                    </div>
                    <div style="display:flex; justify-content:space-between; border-bottom:1px solid #334155; padding:4px 0;">
                        <span style="color:#94A3B8;">Return & Damage Loss:</span>
                        <span style="color:#F87171;">-Rs. {ret_loss:,.2f}</span>
                    </div>
                    <div style="display:flex; justify-content:space-between; border-bottom:1px solid #334155; padding:4px 0;">
                        <span style="color:#94A3B8;">Ad Spend Allocated:</span>
                        <span style="color:#F87171;">-Rs. {ad_cost:,.2f}</span>
                    </div>
                    <div style="display:flex; justify-content:space-between; padding:4px 0; font-weight:700;">
                        <span style="color:#fff;">Gross Profit: Rs. {gp:,.2f}</span>
                        <span style="color:{profit_color};">Contribution Profit (after ads): Rs. {contrib:,.2f}</span>
                    </div>
                </div>
            </div>
            ''',
            warning=mark_safe(missing_cost_warning),
            badge_bg=badge_bg,
            badge_text=badge_text,
            recalc_url=recalc_url,
            net_rev=fin.net_revenue,
            cogs=fin.product_cost,
            courier=fin.total_courier_cost,
            contrib=fin.contribution_profit,
            profit_color=profit_color,
            gross=fin.gross_sales,
            pkg=fin.packaging_cost,
            fwd=fin.courier_forward_charge,
            cod=fin.courier_cod_fee,
            ret=fin.courier_return_charge,
            oth=fin.courier_other_charge,
            ret_loss=fin.return_loss,
            ad_cost=fin.ad_cost_allocated,
            gp=fin.gross_profit,
        )
    finance_summary_panel.short_description = "Financial Breakdown"

    def change_status_view(self, request, order_number, new_status):
        order = get_object_or_404(Order, order_number=order_number)
        try:
            OrderService.update_status(
                order=order,
                new_status=new_status,
                user=request.user,
                note=f"Status updated via Admin quick action by {request.user.username}."
            )
            messages.success(request, f"Order {order_number} transitioned to {new_status.title()}.")
        except Exception as e:
            messages.error(request, f"Error: {e}")
        return redirect('admin:orders_order_change', order.pk)

    # Bulk Admin Actions
    def print_bulk_shipping_labels(self, request, queryset):
        """Opens a multi-label printable dispatch sheet for all selected orders with 1-click."""
        order_ids = ",".join(str(o.id) for o in queryset)
        url = reverse('orders:admin_bulk_invoices') + f"?ids={order_ids}"
        return redirect(url)
    print_bulk_shipping_labels.short_description = "🖨️ Print Selected Shipping Labels / Invoices (Bulk)"

    def export_to_courier_csv(self, request, queryset):
        """Exports selected orders in courier booking CSV format (TCS / Trax / Leopards / PostEx)."""
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="courier_booking_orders.csv"'
        writer = csv.writer(response)
        writer.writerow([
            'Order Number', 'Consignee Name', 'Consignee Phone', 'Consignee Address',
            'Destination City', 'Pieces', 'Weight (KG)', 'COD Amount', 'Product Description',
            'Special Instructions'
        ])
        for o in queryset:
            writer.writerow([
                o.order_number,
                o.shipping_full_name,
                o.shipping_phone,
                o.full_shipping_address,
                o.shipping_city,
                o.total_items_count,
                1.5,
                float(o.grand_total) if o.payment_method == 'COD' and o.payment_status != 'paid' else 0,
                f"Bedding & Home Textile - {o.total_items_count} items",
                o.customer_note or 'Handle with care. Bedding luxury items.'
            ])
        return response
    export_to_courier_csv.short_description = "Export for Courier Booking (CSV)"

    def mark_as_confirmed(self, request, queryset):
        for o in queryset:
            try:
                OrderService.update_status(o, 'confirmed', user=request.user, note="Bulk confirmed by admin.")
            except Exception:
                pass
        messages.success(request, f"Marked {queryset.count()} orders as Confirmed.")
    mark_as_confirmed.short_description = "Mark selected as Confirmed"

    def mark_as_packed(self, request, queryset):
        for o in queryset:
            try:
                OrderService.update_status(o, 'packed', user=request.user, note="Bulk packed by admin.")
            except Exception:
                pass
        messages.success(request, f"Marked {queryset.count()} orders as Packed.")
    mark_as_packed.short_description = "Mark selected as Packed"

    def mark_as_dispatched(self, request, queryset):
        for o in queryset:
            try:
                OrderService.update_status(o, 'dispatched', user=request.user, note="Bulk dispatched by admin.")
            except Exception:
                pass
        messages.success(request, f"Marked {queryset.count()} orders as Dispatched.")
    mark_as_dispatched.short_description = "Mark selected as Dispatched"

    def recalculate_financials_action(self, request, queryset):
        """Bulk recalculate OrderFinancials for all selected orders."""
        if not request.user.has_perm('finance.view_dashboard'):
            messages.error(request, "Permission denied: finance.view_dashboard required.")
            return
        from apps.finance.services import OrderFinancialsService
        success = 0
        for o in queryset:
            try:
                OrderFinancialsService.calculate(o)
                success += 1
            except Exception:
                pass
        messages.success(request, f"Recalculated financials for {success} of {queryset.count()} orders.")
    recalculate_financials_action.short_description = "⚡ Recalculate Financials for Selected Orders"

    def apply_courier_rate_action(self, request, queryset):
        """Apply rate card courier charges to selected orders that lack actual courier statements."""
        if not request.user.has_perm('finance.view_dashboard'):
            messages.error(request, "Permission denied: finance.view_dashboard required.")
            return
        from apps.finance.services import OrderFinancialsService
        count = 0
        for o in queryset:
            OrderFinancialsService.calculate(o)
            count += 1
        messages.success(request, f"Applied rate-card estimation and recalculated {count} orders.")
    apply_courier_rate_action.short_description = "🚚 Apply Courier Rate Card to Selected Orders"

    def get_fieldsets(self, request, obj=None):
        fieldsets = list(super().get_fieldsets(request, obj))
        if request.user.has_perm('finance.view_dashboard') and obj:
            # Insert Finance panel after Financials & Payment
            finance_fieldset = (
                '📊 Profitability & Cost Analysis (Finance Only)', {
                    'fields': ('finance_summary_panel',),
                    'classes': ('wide',)
                }
            )
            # Find index after Financials & Payment
            insert_idx = len(fieldsets)
            for idx, (title, opts) in enumerate(fieldsets):
                if 'Financials' in title:
                    insert_idx = idx + 1
                    break
            fieldsets.insert(insert_idx, finance_fieldset)
        return fieldsets

    def get_readonly_fields(self, request, obj=None):
        ro = list(super().get_readonly_fields(request, obj))
        if 'finance_summary_panel' not in ro:
            ro.append('finance_summary_panel')
        return ro
