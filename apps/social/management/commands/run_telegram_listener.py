"""
Telegram user account'lardan kiruvchi xabarlarni tinglash (to'g'ri async).

Ishlatish: python manage.py run_telegram_listener

Bu command DOIMIY ishlab turishi kerak (background worker).
"""
import asyncio
import logging

from django.core.management.base import BaseCommand
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.events import NewMessage

from apps.social.models import SocialAccount
from apps.agents.models import AgentConfig
from apps.agents.dispatcher import handle_incoming

logger = logging.getLogger('apps.telegram.listener')


class Command(BaseCommand):
    help = "Telegram user account'lardan kiruvchi xabarlarni tinglaydi"

    def handle(self, *args, **options):
        self.stdout.write("🤖 Telegram listener ishga tushdi...")
        asyncio.run(self._run_listener())

    async def _run_listener(self):
        while True:
            accounts = SocialAccount.objects.filter(
                platform__slug='telegram', account_type='user',
                status='active', is_connected=True,
            )
            
            if not accounts.exists():
                await asyncio.sleep(10)
                continue
            
            # Har bir account uchun alohida client yaratish
            clients = []
            for account in accounts:
                if not account.session_data:
                    continue
                try:
                    client = TelegramClient(
                        StringSession(account.session_data),
                        int(account.api_id), account.api_hash,
                    )
                    await client.start()
                    
                    agent_config = await self._get_agent_config(account)
                    if agent_config:
                        async def handler(event, a=account):
                            await self._message_handler(event, a)
                        client.add_event_handler(handler)
                    clients.append(client)
                    self.stdout.write(f"  ✅ {account.display_name} ulandi")
                except Exception as e:
                    logger.warning(f"{account.display_name} ulanishda xato: {e}")
            
            if clients:
                self.stdout.write(f"  {len(clients)} ta account tinglanmoqda...")
                await asyncio.gather(*(c.run_until_disconnected() for c in clients))
            
            await asyncio.sleep(5)
    
    async def _get_agent_config(self, account):
        """Async'da AgentConfig ni olish"""
        from asgiref.sync import sync_to_async
        return await sync_to_async(
            AgentConfig.objects.filter(
                social_account=account, is_enabled=True
            ).first
        )()
    
    async def _message_handler(self, event, account):
        """Kiruvchi xabarni qayta ishlash"""
        message = event.message
        if not message.text or message.out:
            return
        
        sender = await message.get_sender()
        sender_id = str(sender.id) if sender else 'unknown'
        sender_name = f"{sender.first_name or ''} {sender.last_name or ''}".strip() or sender_id
        
        result = await self._dispatch_message(account, sender_id, sender_name, message.text)
        
        response_text = result.get('response_text', '')
        if response_text:
            await event.client.send_message(sender_id, response_text)
    
    async def _dispatch_message(self, account, user_id, user_name, text):
        """Dispatcher'ga sync chaqiruv"""
        from asgiref.sync import sync_to_async
        return await sync_to_async(handle_incoming)(
            social_account=account,
            external_user_id=user_id,
            external_user_name=user_name,
            message_text=text,
        )
