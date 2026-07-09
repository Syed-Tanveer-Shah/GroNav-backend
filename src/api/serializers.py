from rest_framework import serializers
from ..core.models import ContactMessage
from django.db.models import Avg, Count
from datetime import date
from ..services.products.models import (
    Product, StoreLocation, ProductLocation, Store, Category, ShoppingList, ShoppingListItem,
    Order, OrderItem, StoreAnalytics, SellerVerification
)

class ContactMessageSerializer(serializers.ModelSerializer):
    """Serializer for Contact Message API."""
    class Meta:
        model = ContactMessage
        fields = '__all__'

class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = '__all__'

class ProductSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    store_name = serializers.CharField(source='store.name', read_only=True)
    discounted_price = serializers.SerializerMethodField()
    avg_rating = serializers.SerializerMethodField()
    review_count = serializers.SerializerMethodField()
    total_views = serializers.SerializerMethodField()
    is_low_stock = serializers.SerializerMethodField()
    is_expiring_soon = serializers.SerializerMethodField()
    discount_active = serializers.SerializerMethodField()
    image = serializers.FileField(required=False, allow_null=True)

    class Meta:
        model = Product
        fields = [
            'id',
            'name',
            'store',
            'store_name',
            'category',
            'category_name',
            'price',
            'stock',
            'image',
            'discount_percentage',
            'discount_active',
            'featured_product',
            'expiry_date',
            'stock_alert_threshold',
            'description',
            'created_at',
            'updated_at',
            'discounted_price',
            'avg_rating',
            'review_count',
            'total_views',
            'is_low_stock',
            'is_expiring_soon',
        ]
        read_only_fields = ('created_at', 'updated_at', 'discounted_price', 'store')
        
    def get_discounted_price(self, obj):
        """Return the discounted price for a single product, if applicable."""
        if isinstance(obj, Product):
            return obj.get_discounted_price()
        return None

    def get_avg_rating(self, obj):
        avg_rating = getattr(obj, 'avg_rating', None)
        if avg_rating is not None:
            return round(float(avg_rating), 1)
        from django.db.models import Avg
        result = obj.productrating_set.aggregate(Avg('rating'))['rating__avg']
        return round(result, 1) if result else 0

    def get_review_count(self, obj):
        review_count = getattr(obj, 'review_count', None)
        if review_count is not None:
            return review_count
        return obj.productrating_set.count()

    def get_total_views(self, obj):
        total_views = getattr(obj, 'total_views', None)
        if total_views is not None:
            return total_views
        return obj.productview_set.count()

    def get_is_low_stock(self, obj):
        return getattr(obj, 'stock', 0) <= getattr(obj, 'stock_alert_threshold', 5)

    def get_is_expiring_soon(self, obj):
        if hasattr(obj, 'expiry_date') and obj.expiry_date:
            delta = obj.expiry_date - date.today()
            return 0 <= delta.days <= 7
        return False

    def get_discount_active(self, obj):
        return bool(obj.discount_percentage and float(obj.discount_percentage) > 0)

class StoreSerializer(serializers.ModelSerializer):
    avg_rating = serializers.SerializerMethodField()
    is_verified = serializers.SerializerMethodField()
    logo = serializers.ImageField(required=False, allow_null=True)
    logo_url = serializers.SerializerMethodField()
    seller_type = serializers.SerializerMethodField()

    def get_logo_url(self, obj):
        if obj.logo:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.logo.url)
            return obj.logo.url
        return None

    def get_seller_type(self, obj):
        try:
            # Try SellerStore junction model
            ss = obj.sellerstore_set.first()
            if ss and ss.seller:
                return ss.seller.seller_type
        except:
            pass
        try:
            # Try direct seller relation
            if hasattr(obj, 'seller') and obj.seller:
                return obj.seller.seller_type
        except:
            pass
        return None  # return None instead of defaulting to 'physical'

    class Meta:
        model = Store
        # Explicit field list — keeps all data the frontend uses while
        # avoiding accidental exposure of internal-only fields.
        fields = [
            'id',
            'name',
            'description',
            'address',
            'city',
            'phone',
            'email',
            'website',
            'status',
            'logo',
            'logo_url',
            'seller_type',
            'avg_rating',
            'is_verified',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['seller']

    def get_avg_rating(self, obj):
        return obj.storerating_set.aggregate(Avg('rating'))['rating__avg'] or 0

    def get_is_verified(self, obj):
        seller_store = getattr(obj, 'sellerstore_set', None)
        if seller_store and seller_store.exists():
            verification = getattr(seller_store.first().seller, 'sellerverification', None)
            return verification.is_verified if verification else False
        return False

class StoreLocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = StoreLocation
        fields = '__all__'

class ProductLocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductLocation
        fields = ['product', 'store_location', 'aisle_number', 'section']

# ✅ New Serializer for Shopping List
class ShoppingListItemSerializer(serializers.ModelSerializer):
    """Serializer for individual shopping list items."""
    product = ProductSerializer(read_only=True)  # Include full product details

    class Meta:
        model = ShoppingListItem
        fields = ["product", "quantity"]

class ShoppingListSerializer(serializers.ModelSerializer):
    """Serializer for shopping list with all items."""
    items = ShoppingListItemSerializer(source="shoppinglistitem_set", many=True, read_only=True)

    class Meta:
        model = ShoppingList
        fields = ["id", "user", "created_at", "items"]

class OrderItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    class Meta:
        model = OrderItem
        fields = '__all__'

class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    buyer_name = serializers.CharField(source='buyer.get_full_name', read_only=True)
    class Meta:
        model = Order
        # Exclude the raw buyer FK to avoid exposing user PK / internal data;
        # buyer_name (above) provides the human-readable identifier instead.
        fields = [
            'id',
            'buyer_name',
            'items',
            'total_price',
            'status',
            'payment_method',
            'delivery_address',
            'created_at',
            'updated_at',
        ]

class StoreAnalyticsSerializer(serializers.ModelSerializer):
    class Meta:
        model = StoreAnalytics
        fields = '__all__'

class SellerVerificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = SellerVerification
        fields = '__all__'
