import os
import django
import sys

# Add the project root to the python path
sys.path.append(os.getcwd())

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

try:
    from src.services.products.models import Store
    stores = Store.objects.all()
    print(f"Successfully connected to database.")
    print(f"Number of stores found: {len(stores)}")
    for store in stores:
        print(f" - {store.name} (Status: {store.status})")
except Exception as e:
    print(f"Error fetching stores: {e}")
