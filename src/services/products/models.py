from django.db import models
from django.contrib.auth.models import User
from django.conf import settings

# models.py
class Category(models.Model):
    name = models.CharField(max_length=255)
    image = models.ImageField(upload_to='category_images/', null=True, blank=True)

    def __str__(self):
        return self.name


class Store(models.Model):
    seller = models.OneToOneField('products.Seller', on_delete=models.CASCADE, related_name='store', null=True, blank=True)
    name = models.CharField(max_length=255, unique=True)
    address = models.TextField()
    city = models.CharField(max_length=100, blank=True, null=True)
    phone = models.CharField(max_length=20, unique=True)
    status = models.CharField(max_length=10, choices=[('Open', 'Open'), ('Closed', 'Closed')], default='Closed')
    schedule = models.JSONField(default=dict, blank=True)
    image = models.ImageField(upload_to='store_images/', blank=True, null=True)
    logo = models.ImageField(upload_to='store_logos/', null=True, blank=True)
    opening_hours = models.CharField(max_length=100, blank=True, null=True)
    is_open = models.BooleanField(default=True)
    response_time_minutes = models.IntegerField(default=0)
    on_time_delivery_score = models.FloatField(default=0.0)
    completion_score = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)

    def __str__(self):
        return self.name

class Product(models.Model):
    name = models.CharField(max_length=255)
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name="products", null=True, blank=True)
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name="products")
    price = models.DecimalField(max_digits=10, decimal_places=2)
    stock = models.IntegerField(default=0)
    expiry_date = models.DateField(null=True, blank=True)
    stock_alert_threshold = models.IntegerField(default=5)
    image = models.ImageField(upload_to='product_images/', blank=True, null=True)
    discount_percentage = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    discount_active = models.BooleanField(default=False)
    featured_product = models.BooleanField(default=False)
    brand = models.CharField(max_length=100, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    rating = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)

    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)

    def save(self, *args, **kwargs):
        if self.discount_percentage and float(self.discount_percentage) > 0:
            self.discount_active = True
        else:
            self.discount_active = False
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name
    
    def get_discounted_price(self):
        if self.discount_percentage and float(self.discount_percentage) > 0:
            discount_amount = (self.price * self.discount_percentage) / 100
            return self.price - discount_amount
        return self.price



class ShoppingList(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        null=True,  # ✅ Allow user to be NULL
        blank=True  # ✅ Allow empty user
    )
    created_at = models.DateTimeField(auto_now_add=True)


class ShoppingListItem(models.Model):
    """
    Stores individual products within a shopping list along with quantity.
    """
    shopping_list = models.ForeignKey(ShoppingList, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.IntegerField(default=1)

    def __str__(self):
        return f"{self.quantity} x {self.product.name} in {self.shopping_list}"


class StoreLocation(models.Model):
    """
    Represents different sections and aisles in the store.
    """
    name = models.CharField(max_length=100, unique=True)  # Example: Aisle 3, Dairy Section

    def __str__(self):
        return self.name


class ProductLocation(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="locations")
    store_location = models.ForeignKey(StoreLocation, on_delete=models.CASCADE)
    aisle_number = models.IntegerField()
    section = models.CharField(max_length=10, blank=True, null=True)  # Example: A, B, C
    latitude = models.FloatField()  # Needed for map navigation
    longitude = models.FloatField()  # Needed for map navigation

    def __str__(self):
        return f"{self.product.name} → {self.store_location.name} (Aisle {self.aisle_number}, Section {self.section})"

class StoreAnalytics(models.Model):
    store = models.ForeignKey(Store, on_delete=models.CASCADE)
    date = models.DateField(auto_now_add=True)
    visitors = models.IntegerField(default=0)
    hour = models.IntegerField(default=0)

class ProductView(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    viewed_at = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True)
    session_id = models.CharField(max_length=100, null=True)

class CustomerJourney(models.Model):
    session_id = models.CharField(max_length=100)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    store = models.ForeignKey(Store, on_delete=models.CASCADE)
    action = models.CharField(max_length=20, choices=[('view','View'),('cart','Cart'),('checkout','Checkout')])
    timestamp = models.DateTimeField(auto_now_add=True)

class HeatmapEvent(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, null=True, blank=True)
    store = models.ForeignKey(Store, on_delete=models.CASCADE, null=True, blank=True)
    session_id = models.CharField(max_length=100)
    scroll_depth = models.IntegerField()
    section = models.CharField(max_length=100)
    timestamp = models.DateTimeField(auto_now_add=True)

class StoreRating(models.Model):
    store = models.ForeignKey(Store, on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    rating = models.IntegerField(choices=[(i,str(i)) for i in range(1,6)])
    review = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        unique_together = ('store', 'user')

class ProductRating(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    rating = models.IntegerField(choices=[(i,str(i)) for i in range(1,6)])
    review = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        unique_together = ('product', 'user')

class Order(models.Model):
    STATUS = [('received','Received'),('packed','Packed'),('out_for_delivery','Out for Delivery'),('delivered','Delivered'),('cancelled','Cancelled')]
    buyer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    store = models.ForeignKey(Store, on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=STATUS, default='received')
    total_price = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    estimated_delivery = models.DateTimeField(null=True)
    delivery_address = models.TextField()

class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.IntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)

class ReturnRequest(models.Model):
    STATUS = [('pending','Pending'),('approved','Approved'),('rejected','Rejected')]
    order = models.ForeignKey(Order, on_delete=models.CASCADE)
    reason = models.TextField()
    status = models.CharField(max_length=10, choices=STATUS, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)

class SellerVerification(models.Model):
    seller = models.OneToOneField('products.Seller', on_delete=models.CASCADE)
    cnic_number = models.CharField(max_length=15)
    cnic_front = models.ImageField(upload_to='cnic/')
    cnic_back = models.ImageField(upload_to='cnic/')
    is_verified = models.BooleanField(default=False)
    submitted_at = models.DateTimeField(auto_now_add=True)

class DeliveryRadius(models.Model):
    store = models.OneToOneField(Store, on_delete=models.CASCADE)
    center_lat = models.FloatField()
    center_lng = models.FloatField()
    radius_km = models.FloatField(default=5.0)
    polygon_coords = models.JSONField(null=True, blank=True)

class CompetitorPrice(models.Model):
    store = models.ForeignKey(Store, on_delete=models.CASCADE)
    category = models.ForeignKey(Category, on_delete=models.CASCADE)
    my_avg_price = models.DecimalField(max_digits=10, decimal_places=2)
    market_avg = models.DecimalField(max_digits=10, decimal_places=2)
    lowest_price = models.DecimalField(max_digits=10, decimal_places=2)
    updated_at = models.DateTimeField(auto_now=True)
