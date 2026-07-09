from django.core.management.base import BaseCommand
from src.services.products.models import Store, Product, Category, CompetitorPrice
from django.db.models import Avg, Min

class Command(BaseCommand):
    help = 'Calculates market average and lowest prices per category and updates CompetitorPrice'

    def handle(self, *args, **kwargs):
        categories = Category.objects.all()
        stores = Store.objects.filter(is_open=True)

        for store in stores:
            for category in categories:
                # My store's average price for this category
                my_avg = Product.objects.filter(store=store, category=category).aggregate(Avg('price'))['price__avg']
                
                # Market average for this category
                market_avg = Product.objects.filter(category=category).exclude(store=store).aggregate(Avg('price'))['price__avg']
                
                # Lowest market price
                lowest = Product.objects.filter(category=category).exclude(store=store).aggregate(Min('price'))['price__min']

                if my_avg and market_avg and lowest:
                    CompetitorPrice.objects.update_or_create(
                        store=store,
                        category=category,
                        defaults={
                            'my_avg_price': round(my_avg, 2),
                            'market_avg': round(market_avg, 2),
                            'lowest_price': round(lowest, 2)
                        }
                    )
        self.stdout.write(self.style.SUCCESS('Successfully updated competitor prices'))
