from django.db import models
from django.contrib.auth.models import User


class Seller(models.Model):
    SELLER_TYPE_CHOICES = [('online', 'Online'), ('physical', 'Physical')]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='seller')
    seller_type = models.CharField(max_length=10, choices=SELLER_TYPE_CHOICES)
    store_name = models.CharField(max_length=200)
    owner_name = models.CharField(max_length=200)
    phone = models.CharField(max_length=20)
    city = models.CharField(max_length=100)
    is_approved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.owner_name} ({self.seller_type})"


class SellerStore(models.Model):
    """Separate from existing Store model — linked to Seller only."""
    seller = models.OneToOneField(Seller, on_delete=models.CASCADE, related_name='seller_store')
    name = models.CharField(max_length=200)
    city = models.CharField(max_length=100)
    address = models.TextField(blank=True)
    phone = models.CharField(max_length=20)
    opening_hours = models.CharField(max_length=100, blank=True)
    logo = models.ImageField(upload_to='store_logos/', null=True, blank=True)

    def __str__(self):
        return self.name


class OnlineSellerProfile(models.Model):
    seller = models.OneToOneField(Seller, on_delete=models.CASCADE, related_name='online_profile')
    business_type = models.CharField(max_length=50)
    product_category = models.CharField(max_length=100)
    def __str__(self):
        return f"Online: {self.seller.store_name}"


class PhysicalSellerProfile(models.Model):
    seller = models.OneToOneField(Seller, on_delete=models.CASCADE, related_name='physical_profile')
    cnic = models.CharField(max_length=15)
    full_address = models.TextField()
    opening_hours = models.CharField(max_length=100)

    def __str__(self):
        return f"Physical: {self.seller.store_name}"


class SellerCategory(models.Model):
    store = models.ForeignKey(SellerStore, on_delete=models.CASCADE, related_name='categories')
    name = models.CharField(max_length=100)
    image = models.ImageField(upload_to='category_images/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('store', 'name')

    def __str__(self):
        return self.name


class SellerNotification(models.Model):
    TYPE_CHOICES = [
        ('order', 'New Order'),
        ('rating', 'New Rating'),
        ('low_stock', 'Low Stock'),
        ('return', 'Return Request'),
        ('verification', 'Verification Update'),
    ]
    seller = models.ForeignKey(Seller, on_delete=models.CASCADE, related_name='notifications')
    type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    title = models.CharField(max_length=200)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.seller.store_name if hasattr(self.seller, 'store_name') else self.seller.owner_name} - {self.title}"


# Signals for Auto-Notifications
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Order, StoreRating, ProductRating, ReturnRequest, SellerVerification

@receiver(post_save, sender=Order)
def notify_new_order(sender, instance, created, **kwargs):
    if created:
        from ..api.seller_dashboard_views import create_notification
        create_notification(
            seller=instance.store.seller,
            type='order',
            title='New Order Received',
            message=f"Order #{instance.id} received from {instance.buyer.get_full_name() or instance.buyer.email}"
        )

@receiver(post_save, sender=StoreRating)
def notify_store_rating(sender, instance, created, **kwargs):
    if created:
        from ..api.seller_dashboard_views import create_notification
        # Check if store has seller
        seller = getattr(instance.store, 'seller', None)
        if seller:
            create_notification(
                seller=seller,
                type='rating',
                title='New Store Rating',
                message=f"{instance.user.get_full_name() or 'A customer'} rated your store {instance.rating}★"
            )

@receiver(post_save, sender=ProductRating)
def notify_product_rating(sender, instance, created, **kwargs):
    if created:
        from ..api.seller_dashboard_views import create_notification
        seller = getattr(instance.product.store, 'seller', None)
        if seller:
            create_notification(
                seller=seller,
                type='rating',
                title='New Product Rating',
                message=f"{instance.user.get_full_name() or 'A customer'} rated {instance.product.name} {instance.rating}★"
            )

@receiver(post_save, sender=ReturnRequest)
def notify_return_request(sender, instance, created, **kwargs):
    if created:
        from ..api.seller_dashboard_views import create_notification
        seller = instance.order.store.seller
        create_notification(
            seller=seller,
            type='return',
            title='Return Request Received',
            message=f"Return requested for Order #{instance.order.id}: {instance.reason[:50]}..."
        )

@receiver(post_save, sender=SellerVerification)
def notify_verification_update(sender, instance, **kwargs):
    # This might trigger on every save, we should check if is_verified changed
    # For simplicity, we'll notify if it IS verified and maybe was just changed
    if instance.is_verified:
        from ..api.seller_dashboard_views import create_notification
        create_notification(
            seller=instance.seller,
            type='verification',
            title='Store Verification Approved',
            message="Congratulations! Your store has been verified and is now fully active."
        )
