"""
Telegram botni avtomatik sozlash uchun management command.

Ishlatish:
    python manage.py setup_telegram_bot <bot_token> [--username admin]

Bot token berilmagan bo'lsa, TELEGRAM_BOT_TOKEN env o'zgaruvchisidan oladi.
"""
import os
import requests
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User
from django.conf import settings
from apps.social.models import SocialPlatform, SocialAccount
from apps.agents.models import AgentConfig

TELEGRAM_API = 'https://api.telegram.org/bot'


class Command(BaseCommand):
    help = "Telegram botni sozlash: SocialAccount + AgentConfig yaratadi va webhook'ni o'rnatadi"

    def add_arguments(self, parser):
        parser.add_argument('bot_token', nargs='?', type=str,
                          help='Telegram bot tokeni')
        parser.add_argument('--username', type=str, default='admin',
                          help='Bot egasi foydalanuvchi nomi (standart: admin)')
        parser.add_argument('--base-url', type=str,
                          help='Webhook uchun asosiy URL (masalan: https://example.com). '
                               'Berilmasa, localhost ishlatiladi.')

    def handle(self, *args, **options):
        bot_token = options['bot_token'] or os.environ.get('TELEGRAM_BOT_TOKEN')
        if not bot_token:
            raise CommandError(
                "Bot token kerak. Berish usullari:\n"
                "  1. Argument sifatida: python manage.py setup_telegram_bot TOKEN\n"
                "  2. .env faylga TELEGRAM_BOT_TOKEN qo'shib"
            )

        # Bot ma'lumotlarini tekshirish
        self.stdout.write("Bot ma'lumotlarini tekshirish...")
        try:
            resp = requests.get(f'{TELEGRAM_API}{bot_token}/getMe', timeout=10)
            if not resp.json().get('ok'):
                raise CommandError("Bot token yaroqsiz!")
            bot_info = resp.json()['result']
            bot_username = bot_info.get('username', 'unknown_bot')
            bot_name = bot_info.get('first_name', bot_username)
            self.stdout.write(self.style.SUCCESS(f"Bot topildi: @{bot_username} ({bot_name})"))
        except requests.exceptions.ConnectionError:
            raise CommandError("Telegram API ga ulanishda xato. Internetni tekshiring.")

        # Foydalanuvchini topish/yaratish
        username = options['username']
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            user = User.objects.create_user(
                username=username,
                password='admin123',
                is_staff=True,
                is_superuser=True,
            )
            self.stdout.write(self.style.WARNING(
                f"Foydalanuvchi '{username}' yaratildi (parol: admin123). "
                f"Iltimos, parolni o'zgartiring!"
            ))

        # Telegram platformasini topish
        try:
            platform = SocialPlatform.objects.get(slug='telegram')
        except SocialPlatform.DoesNotExist:
            self.stdout.write("SocialPlatform 'telegram' topilmadi, fixture yuklanmoqda...")
            from django.core.management import call_command
            call_command('loaddata', 'initial_platforms')
            platform = SocialPlatform.objects.get(slug='telegram')

        # SocialAccount yaratish
        account, created = SocialAccount.objects.get_or_create(
            user=user,
            platform=platform,
            external_id=bot_username,
            defaults={
                'display_name': bot_name,
                'access_token': bot_token,
                'status': 'active',
                'is_connected': False,
            }
        )

        if created:
            self.stdout.write(self.style.SUCCESS(f"SocialAccount yaratildi: {account}"))
        else:
            # Token yangilangan bo'lsa
            account.access_token = bot_token
            account.status = 'active'
            account.save()
            self.stdout.write(self.style.WARNING(f"SocialAccount yangilandi: {account}"))

        # AgentConfig yaratish (agar mavjud bo'lmasa)
        config, config_created = AgentConfig.objects.get_or_create(
            social_account=account,
            defaults={
                'system_prompt': (
                    "Siz foydalanuvchilarga yordam beruvchi AI yordamchisiz. "
                    "Savollarga aniq, foydali va do'stona javob bering. "
                    "O'zbek tilida javob berishga harakat qiling."
                ),
                'is_enabled': True,
            }
        )
        if config_created:
            self.stdout.write(self.style.SUCCESS("AgentConfig yaratildi"))
        else:
            self.stdout.write(self.style.WARNING("AgentConfig mavjud edi"))

        # Webhook o'rnatish
        base_url = options.get('base_url')
        if not base_url:
            base_url = getattr(settings, 'SITE_URL', 'http://localhost:8000')

        webhook_url = f'{base_url.rstrip("/")}/social/telegram/webhook/{account.id}/'
        self.stdout.write(f"Webhook o'rnatilmoqda: {webhook_url}")

        try:
            resp = requests.post(
                f'{TELEGRAM_API}{bot_token}/setWebhook',
                json={'url': webhook_url},
                timeout=15,
            )
            data = resp.json()
            if data.get('ok'):
                account.is_connected = True
                account.save(update_fields=['is_connected'])
                self.stdout.write(self.style.SUCCESS(
                    f"\n✅ Bot tayyor! Webhook o'rnatildi.\n"
                    f"   Bot: @{bot_username}\n"
                    f"   Webhook: {webhook_url}\n"
                    f"   Admin: http://localhost:8000/admin/\n"
                ))
            else:
                self.stdout.write(self.style.ERROR(
                    f"Webhook xatosi: {data.get('description', '')}"
                ))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Webhook sozlashda xato: {e}"))
