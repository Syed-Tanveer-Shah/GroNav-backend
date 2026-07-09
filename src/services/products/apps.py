from django.apps import AppConfig


class CoreConfig(AppConfig):
    name = 'src.services.products'
    verbose_name = 'Products'
    verbose_plural = 'Products'
    default_auto_config = 'django.db.models.BigAutoField'

    def ready(self):
        import src.services.products.signals
