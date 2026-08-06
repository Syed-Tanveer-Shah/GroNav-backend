import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from django.contrib.auth.models import User

u = User.objects.filter(username='admin').first()
if u:
    u.set_password('Admin@123')
    u.is_superuser = True
    u.is_staff = True
    u.save()
    print("EXISTING_ADMIN_PASSWORD_UPDATED")
else:
    User.objects.create_superuser('admin', 'admin@gronav.com', 'Admin@123')
    print("NEW_ADMIN_CREATED")
