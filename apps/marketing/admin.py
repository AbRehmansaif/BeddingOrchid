from django.contrib import admin
from .models import MetaEventLog

@admin.register(MetaEventLog)
class MetaEventLogAdmin(admin.ModelAdmin):
    list_display = ('event_name', 'event_id', 'is_success', 'response_status', 'created_at')
    list_filter = ('is_success', 'event_name', 'created_at')
    search_fields = ('event_id', 'event_name', 'response_body')
    readonly_fields = ('event_name', 'event_id', 'payload', 'response_status', 'response_body', 'is_success', 'created_at')

    def has_add_permission(self, request):
        return False
