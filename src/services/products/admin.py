from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from .models import (
    Category, Product, ShoppingList, ShoppingListItem, 
    StoreLocation, ProductLocation, Store, Order, OrderItem
)
from .seller_models import Seller

# CHANGE 5 — Admin site branding
admin.site.site_header = "CartGo Admin Panel"
admin.site.site_title = "CartGo"
admin.site.index_title = "CartGo Administration"

# Products and Categories hidden from sidebar as requested
# @admin.register(Product)
# class ProductAdmin(admin.ModelAdmin): ...
# @admin.register(Category)
# class CategoryAdmin(admin.ModelAdmin): ...

# CHANGE 3 — Add Sellers section
@admin.register(Seller)
class SellerAdmin(admin.ModelAdmin):
    list_display = [
        'store_name',
        'owner_name',
        'seller_type',
        'city',
        'phone',
        'get_email',
        'created_at'
    ]
    search_fields = ['store_name', 'owner_name', 'user__email', 'phone']
    list_filter = ['seller_type', 'city']
    readonly_fields = [
        'store_name',
        'owner_name',
        'seller_type',
        'city',
        'phone',
        'created_at',
        'get_email',
        'get_store_info'
    ]

    def get_email(self, obj):
        return obj.user.email if obj.user else '-'
    get_email.short_description = 'Email'

    def get_store_info(self, obj):
        try:
            # Try to get linked public store or internal seller store
            store = getattr(obj, 'store', None) or getattr(obj, 'seller_store', None)
            if store:
                return f"{store.name} — {store.city} — {store.phone}"
        except:
            pass
        return 'No store linked'
    get_store_info.short_description = 'Store Info'

    def has_add_permission(self, request):
        return False

    fieldsets = (
        ('Personal Info', {
            'fields': ('get_email', 'owner_name', 'phone', 'city')
        }),
        ('Store Info', {
            'fields': ('store_name', 'seller_type', 'get_store_info')
        }),
        ('Registration Date', {
            'fields': ('created_at',)
        }),
    )

# NEW — Buyers section (Proxy Model)
class BuyerProxy(User):
    class Meta:
        proxy = True
        verbose_name = 'Buyer'
        verbose_name_plural = 'Buyers'

@admin.register(BuyerProxy)
class BuyerAdmin(admin.ModelAdmin):
    list_display = [
        'email',
        'first_name',
        'last_name',
        'date_joined',
        'is_active',
    ]
    search_fields = ['email', 'first_name', 'last_name']
    list_filter = ['is_active', 'date_joined']

    def get_queryset(self, request):
        # Show ONLY users who do NOT have a seller account
        return super().get_queryset(request).filter(seller__isnull=True)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return True

try:
    admin.site.unregister(User)
except Exception:
    pass

# CHANGE 1 — Restore all hidden items
@admin.register(Store)
class StoreAdmin(admin.ModelAdmin):
    list_display = ('name', 'address', 'phone', 'status')
    search_fields = ('name', 'address', 'phone')
    list_filter = ('status',)

@admin.register(ShoppingList)
class ShoppingListAdmin(admin.ModelAdmin):
    list_display = ('user', 'created_at')
    search_fields = ('user__username',)

@admin.register(ShoppingListItem)
class ShoppingListItemAdmin(admin.ModelAdmin):
    list_display = ('shopping_list', 'product', 'quantity')

@admin.register(StoreLocation)
class StoreLocationAdmin(admin.ModelAdmin):
    list_display = ('name',)

@admin.register(ProductLocation)
class ProductLocationAdmin(admin.ModelAdmin):
    list_display = ('product', 'store_location', 'aisle_number', 'section')

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'buyer', 'store', 'status', 'total_price', 'created_at')
    list_filter = ('status',)

@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ('order', 'product', 'quantity', 'price')