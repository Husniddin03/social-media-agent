from django.apps import AppConfig


class BotConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.telegram.bot'
    verbose_name = 'Telegram Bot'
