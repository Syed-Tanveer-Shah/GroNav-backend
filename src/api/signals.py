from django.db.models.signals import post_save
from django.contrib.auth.models import User
from django.dispatch import receiver
from threading import Thread

@receiver(post_save, sender=User)
def send_welcome_email_on_registration(sender, instance, created, **kwargs):
    if created:
        print(f"=== NEW USER CREATED: {instance.email} ===")
        try:
            from .email_service import send_welcome_email
            Thread(target=send_welcome_email, args=(instance,)).start()
            print(f"Welcome email triggered for: {instance.email}")
        except Exception as e:
            print(f"Welcome email error: {e}")
