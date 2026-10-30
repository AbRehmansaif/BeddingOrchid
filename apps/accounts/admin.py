from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, Address, Wishlist, WishlistItem

class AddressInline(admin.StackedInline):
    model = Address
    extra = 0
    fields = ('label', 'full_name', 'phone', 'address_line1', 'city', 'province', 'is_default')

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('username', 'full_name', 'phone', 'email', 'is_staff', 'is_active', 'date_joined')
    list_filter = ('is_staff', 'is_superuser', 'is_active', 'is_phone_verified')
    search_fields = ('username', 'full_name', 'phone', 'email')
    ordering = ('-date_joined',)
    inlines = [AddressInline]

    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Personal info', {'fields': ('full_name', 'first_name', 'last_name', 'email', 'phone')}),
        ('Verification & Marketing', {'fields': ('is_phone_verified', 'marketing_opt_in')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )

@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'phone', 'city', 'label', 'is_default', 'user')
    search_fields = ('full_name', 'phone', 'city', 'address_line1', 'user__email', 'user__phone')
    list_filter = ('city', 'province', 'is_default', 'label')

@admin.register(Wishlist)
class WishlistAdmin(admin.ModelAdmin):
    list_display = ('user', 'created_at')
    search_fields = ('user__email', 'user__phone', 'user__full_name')
