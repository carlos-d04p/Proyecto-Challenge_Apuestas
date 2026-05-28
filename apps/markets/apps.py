from django.apps import AppConfig

class MarketsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.markets'

    def ready(self):
        # Importamos las señales al arrancar la app para que Django las escuche
        import apps.markets.signals