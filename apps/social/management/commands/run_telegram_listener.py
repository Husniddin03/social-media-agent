"""
Telegram user account'lardan kiruvchi xabarlarni tinglash.
Ishlatish: python manage.py run_telegram_listener

Bu command HAR DOIM ishlab turishi kerak (background worker).
Render'da: python manage.py run_telegram_listener &
"""
import base64
import logging
import pickle
import time

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.social.models import SocialAccount
from apps.agents.models import AgentConfig, ConversationLog, UsageStats
from apps.agents.dispatcher import handle_incoming

logger = logging.getLogger('apps.telegram.listener')


class Command(BaseCommand):
    help = "Telegram user account'lardan kiruvchi xabarlarni tinglaydi"

    def handle(self, *args, **options):
        self.stdout.write("🤖 Telegram listener ishga tushdi...")
        
        while True:
            accounts = SocialAccount.objects.filter(
                platform__slug='telegram',
                account_type='user',
                status='active',
                is_connected=True,
            )
            
            if not accounts.exists():
                self.stdout.write("Faol account topilmadi, 10s kutiladi...")
                time.sleep(10)
                continue
            
            for account in accounts:
                if not account.session_data:
                    continue
                    
                try:
                    self._listen_account(account)
                except Exception as e:
                    logger.exception(f"Listener xatosi: {account.display_name}")
                    account.status = 'error'
                    account.save(update_fields=['status'])
            
            self.stdout.write(f"{accounts.count()} ta account tekshirildi, 5s kutiladi...")
            time.sleep(5)
    
    def _listen_account(self, account):
        """Bitta account uchun xabarlarni tinglash"""
        from telethon import TelegramClient
        from telethon.events import NewMessage
        from telethon.tl.types import Message
        
        session_data = pickle.loads(base64.b64decode(account.session_data))
        
        client = TelegramClient(f'listener_{account.id}', int(account.api_id), account.api_hash)
        client.session.save(session_data)
        client.start()
        
        agent_config = AgentConfig.objects.filter(
            social_account=account, is_enabled=True
        ).first()
        
        if not agent_config:
            client.disconnect()
            return
        
        @client.on(NewMessage(incoming=True))
        async def handler(event):
            message = event.message
            if not message.text:
                return
            
            # O'z xabarlarimizni filter (bot/self messages)
            if message.out:
                return
            
            sender = await message.get_sender()
            sender_id = str(sender.id) if sender else 'unknown'
            sender_name = f"{sender.first_name or ''} {sender.last_name or ''}".strip() or sender_id
            
            # Dispatcher'ga yuborish
            result = handle_incoming(
                social_account=account,
                external_user_id=sender_id,
                external_user_name=sender_name,
                message_text=message.text,
            )
            
            # Javobni yuborish
            response_text = result.get('response_text', '')
            if response_text:
                await client.send_message(sender_id, response_text)
        
        self.stdout.write(f"  👂 {account.display_name} tinglanmoqda...")
        client.run_until_disconnected()
