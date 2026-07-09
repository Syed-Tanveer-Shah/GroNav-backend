from django.apps import AppConfig

class ApiConfig(AppConfig):
    name = 'src.api'
    
    def ready(self):
        import src.api.signals
