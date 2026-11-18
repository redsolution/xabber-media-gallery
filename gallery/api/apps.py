from django.apps import AppConfig


class ApiConfig(AppConfig):
    name = 'gallery.api'

    def ready(self):
        super(ApiConfig, self).ready()
        import gallery.api.signals