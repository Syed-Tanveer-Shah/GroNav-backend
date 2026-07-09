from django.db import models
from django.contrib.auth.models import User
from src.services.products.models import Product, Store
from src.services.products.seller_models import SellerNotification

class CustomerOrder(models.Model):
    ORDER_STATUS_CHOICES = [
        ('received', 'Received'),
        ('packed', 'Packed'),
        ('out_for_delivery', 'Out for Delivery'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled')
    ]
    
    PAYMENT_METHOD_CHOICES = [
        ('stripe', 'Stripe'),
        ('COD', 'COD')
    ]
    
    PAYMENT_STATUS_CHOICES = [
        ('paid', 'Paid'),
        ('pending', 'Pending')
    ]

    order_id = models.AutoField(primary_key=True)
    customer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='customer_orders')
    seller = models.ForeignKey(User, on_delete=models.CASCADE, related_name='seller_orders', null=True, blank=True)
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='store_customer_orders', null=True, blank=True)
    
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='orders')
    product_name = models.CharField(max_length=255)
    quantity = models.IntegerField(default=1)
    price_per_item = models.DecimalField(max_digits=10, decimal_places=2)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    delivery_fee = models.DecimalField(max_digits=10, decimal_places=2, default=140.00)
    platform_fee = models.DecimalField(max_digits=10, decimal_places=2, default=10.00)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES, default='COD')
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='pending')
    order_status = models.CharField(max_length=20, choices=ORDER_STATUS_CHOICES, default='received')
    delivery_address = models.TextField()
    customer_name = models.CharField(max_length=255)
    customer_phone = models.CharField(max_length=50)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Order #{self.order_id} - {self.product_name}"
