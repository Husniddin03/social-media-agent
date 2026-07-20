"""
Telegram user account'lardan kiruvchi xabarlarni tinglash.

Ishlatish: python manage.py run_telegram_listener

Bu command DOIMIY ishlab turishi kerak (background worker).
"""
import asyncio
import logging

from django.core.management.base import BaseCommand
from django.db import close_old_connections
from asgiref.sync import sync_to_async
from telethon import TelegramClient
from telethon.sessions import StringSession

from apps.social.models import SocialAccount
from apps.agents.models import AgentConfig
from apps.agents.dispatcher import handle_incoming

logger = logging.getLogger('apps.telegram.listener')


class Command(BaseCommand):
    help = "Telegram user account'lardan kiruvchi xabarlarni tinglaydi"

    def handle(self, *args, **options):
        self.stdout.write("🤖 Telegram listener ishga tushdi...")
        asyncio.run(self._run())

    async def _get_accounts(self):
        """Faol accountlarni olish"""
        return await sync_to_async(list)(
            SocialAccount.objects.filter(
                platform__slug='telegram', account_type='user',
                status='active', is_connected=True,
            ).exclude(session_data='')
        )

    async def _get_agent_config(self, account):
        """AgentConfig ni olish"""
        return await sync_to_async(
            AgentConfig.objects.filter(
                social_account=account, is_enabled=True
            ).select_related('ai_credential').first
        )()

    async def _run(self):
        """Asosiy listener loopi"""
        self.stdout.write("⏳ Accountlarni tekshirish...")
        
        while True:
            try:
                accounts = await self._get_accounts()
                
                if not accounts:
                    await asyncio.sleep(15)
                    continue
                
                clients = []
                for account in accounts:
                    try:
                        client = TelegramClient(
                            StringSession(account.session_data),
                            int(account.api_id), account.api_hash,
                        )
                        await client.start()
                        
                        config = await self._get_agent_config(account)
                        if config and config.is_enabled:
                            async def handler(event, a=account):
                                await self._handle_message(event, a)
                            client.add_event_handler(handler)
                        
                        clients.append(client)
                        self.stdout.write(f"  ✅ {account.display_name}")
                    except Exception as e:
                        logger.warning(f"{account.display_name}: {e}")
                
                if clients:
                    self.stdout.write(f"  📡 {len(clients)} ta account ulandi")
                    await asyncio.gather(*(c.run_until_disconnected() for c in clients))
                
            except Exception as e:
                logger.exception("Listener xatosi")
            finally:
                close_old_connections()
                await asyncio.sleep(5)

    async def _handle_message(self, event, account):
        """Xabar kelganda"""
        if not event.message.text or event.message.out:
            return
        
        try:
            sender = await event.get_sender()
            sender_id = str(sender.id) if sender else 'unknown'
            sender_name = f"{sender.first_name or ''} {sender.last_name or ''}".strip() or sender_id
            
            result = await sync_to_async(handle_incoming)(
                social_account=account,
                external_user_id=sender_id,
                external_user_name=sender_name,
                message_text=event.message.text,
            )
            
            response = result.get('response_text', '')
            if response:
                await event.client.send_message(sender_id, response)
        except Exception as e:
            logger.exception("Xabarni qayta ishlashda xato")
