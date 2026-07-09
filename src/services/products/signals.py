from django.db.models.signals import post_migrate
from django.dispatch import receiver
from .models import Category

@receiver(post_migrate)
def create_default_categories(sender, **kwargs):
    default_categories = ['Spices','Meat','Toys','Cereal','Electronics','Sweets','Biscuits','Choclates','Crisps','Fruits','Bakery','Flowers','Clothes','Frozen','Dairy']
    for name in default_categories:
        Category.objects.get_or_create(name=name)
