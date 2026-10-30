from django.contrib import admin
from .models import Page, ContactMessage

@admin.register(Page)
class PageAdmin(admin.ModelAdmin):
    list_display = ('title', 'slug', 'show_in_header', 'show_in_footer', 'sort_order')
    list_editable = ('show_in_header', 'show_in_footer', 'sort_order')
    prepopulated_fields = {'slug': ('title',)}
    search_fields = ('title', 'content')


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone', 'email', 'subject', 'is_resolved', 'created_at')
    list_filter = ('is_resolved', 'created_at')
    search_fields = ('name', 'phone', 'email', 'message')
    list_editable = ('is_resolved',)
