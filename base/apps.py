import atexit

from django.apps import AppConfig

from helper_thread_pool import shutdown_thread_pool


class BaseConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'base'

    # def ready(self):
    #     atexit.register(shutdown_thread_pool)

