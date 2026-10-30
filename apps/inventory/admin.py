from django.contrib import admin
from .models import StockMovement

@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'variant', 'quantity_change', 'balance_after', 'reason', 'order_ref', 'user')
    list_filter = ('reason', 'created_at')
    search_fields = ('variant__sku', 'variant__product__name', 'order_ref')
    readonly_fields = ('created_at', 'variant', 'quantity_change', 'balance_after', 'reason', 'order_ref', 'user', 'note')

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
