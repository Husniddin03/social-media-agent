import json
import logging
import requests
import asyncio

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.conf import settings

from apps.social.models import SocialPlatform, SocialAccount
from apps.agents.models import AgentConfig, ConversationLog
from apps.ai_providers.models import AIProvider, AIProviderCredential

logger = logging.getLogger('apps.base')
TELEGRAM_API = 'https://api.telegram.org/bot'

# Telethon'ni lazy import qilamiz (chat accountlar uchun)
try:
    from telethon import TelegramClient
    from telethon.sessions import StringSession
    HAS_TELETHON = True
except ImportError:
    TelegramClient = None
    StringSession = None
    HAS_TELETHON = False


def index(request):
    return render(request, 'base/index.html')


def telegram(request):
    """Telegram hub - Chatlar va Botlar"""
    bots = SocialAccount.objects.filter(
        user=request.user if request.user.is_authenticated else None,
        platform__slug='telegram', account_type='bot',
    ) if request.user.is_authenticated else []
    chats = SocialAccount.objects.filter(
        user=request.user if request.user.is_authenticated else None,
        platform__slug='telegram', account_type='user',
    ) if request.user.is_authenticated else []
    return render(request, 'base/telegram.html', {'bots': bots, 'chats': chats})


# ===== BOT views =====

@login_required
def bot_list(request):
    accounts = SocialAccount.objects.filter(user=request.user, platform__slug='telegram', account_type='bot')
    return render(request, 'base/bot_list.html', {'accounts': accounts})

@login_required
@require_POST
def bot_add(request):
    bot_token = request.POST.get('bot_token', '').strip()
    if not bot_token:
        messages.error(request, "Bot tokeni kerak!")
        return redirect('base:bot_list')
    try:
        resp = requests.get(f'{TELEGRAM_API}{bot_token}/getMe', timeout=10)
        data = resp.json()
        if not data.get('ok'):
            messages.error(request, f"Token yaroqsiz: {data.get('description', '')}")
            return redirect('base:bot_list')
        bot_info = data['result']
        bot_username = bot_info.get('username', '')
        bot_name = bot_info.get('first_name', bot_username)
    except requests.exceptions.ConnectionError:
        messages.error(request, "Telegram API ga ulanishda xato!")
        return redirect('base:bot_list')
    platform = SocialPlatform.objects.get(slug='telegram')
    account, created = SocialAccount.objects.get_or_create(
        user=request.user, platform=platform, account_type='bot',
        external_id=bot_username,
        defaults={'display_name': bot_name, 'access_token': bot_token, 'status': 'active'},
    )
    if created:
        AgentConfig.objects.get_or_create(social_account=account, defaults={'is_enabled': True})
        webhook_url = request.build_absolute_uri(f'/social/telegram/webhook/{account.id}/')
        try:
            wh_resp = requests.post(f'{TELEGRAM_API}{bot_token}/setWebhook', json={'url': webhook_url}, timeout=15)
            if wh_resp.json().get('ok'):
                account.is_connected = True
                account.save(update_fields=['is_connected'])
                messages.success(request, f"@{bot_username} qo'shildi va webhook o'rnatildi!")
            else:
                messages.warning(request, f"Bot qo'shildi, lekin webhook xatosi")
        except Exception as e:
            messages.warning(request, f"Bot qo'shildi, webhook xatosi: {e}")
    else:
        account.access_token = bot_token
        account.status = 'active'
        account.save()
        messages.info(request, f"@{bot_username} yangilandi")
    return redirect('base:bot_list')


@login_required
def bot_settings(request, account_id):
    account = get_object_or_404(SocialAccount, id=account_id, user=request.user)
    config, _ = AgentConfig.objects.get_or_create(social_account=account)
    logs = ConversationLog.objects.filter(social_account=account)[:50]
    credentials = AIProviderCredential.objects.filter(user=request.user).select_related('provider')
    return render(request, 'base/bot_settings.html', {'account': account, 'config': config, 'logs': logs, 'credentials': credentials})

@login_required
@require_POST
def bot_settings_save(request, account_id):
    account = get_object_or_404(SocialAccount, id=account_id, user=request.user)
    config, _ = AgentConfig.objects.get_or_create(social_account=account)
    credential_id = request.POST.get('ai_credential')
    config.ai_credential_id = int(credential_id) if credential_id else None
    config.system_prompt = request.POST.get('system_prompt', config.system_prompt)
    config.tone = request.POST.get('tone', config.tone)
    config.language_mode = request.POST.get('language_mode', config.language_mode)
    config.max_response_length = int(request.POST.get('max_response_length', 1000))
    config.is_enabled = request.POST.get('is_enabled') == 'on'
    config.fallback_to_human = request.POST.get('fallback_to_human') == 'on'
    config.save()
    messages.success(request, "Sozlamalar saqlandi!")
    return redirect('base:bot_settings', account_id=account.id)

@login_required
@require_POST
def bot_delete(request, account_id):
    account = get_object_or_404(SocialAccount, id=account_id, user=request.user)
    account.delete()
    messages.success(request, "Bot o'chirildi")
    return redirect('base:bot_list')

@login_required
@require_POST
def bot_toggle(request, account_id):
    account = get_object_or_404(SocialAccount, id=account_id, user=request.user)
    account.status = 'paused' if account.status == 'active' else 'active'
    account.save(update_fields=['status'])
    return redirect('base:bot_list')

@login_required
@require_POST
def bot_reconnect(request, account_id):
    account = get_object_or_404(SocialAccount, id=account_id, user=request.user)
    if not account.access_token:
        messages.error(request, "Bot tokeni topilmadi!")
        return redirect('base:bot_settings', account_id=account.id)
    webhook_url = request.build_absolute_uri(f'/social/telegram/webhook/{account.id}/')
    try:
        resp = requests.post(f'{TELEGRAM_API}{account.access_token}/setWebhook', json={'url': webhook_url}, timeout=15)
        if resp.json().get('ok'):
            account.is_connected = True; account.save(update_fields=['is_connected'])
            messages.success(request, "Webhook qayta o'rnatildi!")
        else:
            messages.error(request, "Webhook xatosi")
    except Exception as e:
        messages.error(request, f"Xato: {e}")
    return redirect('base:bot_settings', account_id=account.id)


# ===== Asinxron Telethon operatsiyalari uchun yordamchi =====

def run_async(coro):
    """asyncio.run() o'rniga — loop.new_event_loop() bilan xavfsiz ishlatish"""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ===== CHAT (User Account) views =====

@login_required
def chat_list(request):
    """Chat accounts ro'yxati"""
    accounts = SocialAccount.objects.filter(user=request.user, platform__slug='telegram', account_type='user')
    return render(request, 'base/chat_list.html', {'accounts': accounts})


@login_required
def chat_add(request):
    """Chat account qo'shish formasi"""
    if request.method == 'POST':
        phone = request.POST.get('phone', '').strip()
        api_id = request.POST.get('api_id', '').strip()
        api_hash = request.POST.get('api_hash', '').strip()
        if not all([phone, api_id, api_hash]):
            messages.error(request, "Barcha maydonlarni to'ldiring!")
            return redirect('base:chat_list')
        
        if not HAS_TELETHON:
            messages.error(request, "Telethon kutubxonasi o'rnatilmagan!")
            return redirect('base:chat_list')
        
        # SocialAccount yaratish (pending status)
        platform = SocialPlatform.objects.get(slug='telegram')
        
        # Agar shu telefonga pending account bo'lsa, eski accountni o'chirib yangisini yaratamiz
        SocialAccount.objects.filter(
            user=request.user, platform=platform, account_type='user',
            external_id=phone, status='pending'
        ).delete()
        
        account = SocialAccount.objects.create(
            user=request.user,
            platform=platform,
            account_type='user',
            display_name=phone,
            external_id=phone,
            phone=phone,
            api_id=api_id,
            api_hash=api_hash,
            status='pending',
        )
        AgentConfig.objects.get_or_create(social_account=account, defaults={'is_enabled': True})
        
        # Telegram auth code yuborish
        try:
            async def send_code():
                client = TelegramClient(StringSession(), int(api_id), api_hash)
                try:
                    await client.connect()
                    if not await client.is_user_authorized():
                        result = await client.send_code_request(phone)
                        account.auth_code_hash = result.phone_code_hash
                        session_str = StringSession.save(client.session)
                        account.session_data = session_str
                        account.save(update_fields=['auth_code_hash', 'session_data'])
                        return True
                    else:
                        account.status = 'active'
                        account.is_connected = True
                        account.display_name = f"User {phone[-4:]}"
                        account.save()
                        return False
                finally:
                    try:
                        await client.disconnect()
                    except:
                        pass
            
            need_verify = run_async(send_code())
            if need_verify:
                messages.success(request, f"{phone} ga kod yuborildi! Telegram'dan kelgan kodni kiriting.")
                return render(request, 'base/chat_verify.html', {'account': account})
            else:
                messages.success(request, "Account allaqachon ulangan!")
        except Exception as e:
            logger.exception("Auth code xatosi")
            messages.error(request, f"Xatolik: Telefon raqam yoki API ma'lumotlarini tekshiring")
        return redirect('base:chat_list')
    return redirect('base:chat_list')


@login_required
def chat_verify(request, account_id):
    """Auth code ni tasdiqlash - GET (form) va POST (process)"""
    account = get_object_or_404(SocialAccount, id=account_id, user=request.user, account_type='user')
    
    # GET so'rov - formani ko'rsatish
    if request.method == 'GET':
        return render(request, 'base/chat_verify.html', {'account': account})
    
    # POST so'rov - kodni tekshirish
    code = request.POST.get('code', '').strip()
    password = request.POST.get('password', '').strip()
    
    if not code:
        return render(request, 'base/chat_verify.html', {
            'account': account, 'error': "Iltimos, Telegram'dan kelgan kodni kiriting!"
        })
    
    try:
        async def verify_code():
            session_str = account.session_data or ''
            session = StringSession(session_str) if session_str else StringSession()
            client = TelegramClient(session, int(account.api_id), account.api_hash)
            try:
                await client.connect()
                
                # phone_code_hash ni eksplitsit uzatamiz (StringSession dan o'qilmasligi mumkin)
                kwargs = {'phone': account.phone, 'code': code}
                if account.auth_code_hash:
                    kwargs['phone_code_hash'] = account.auth_code_hash
                if password:
                    kwargs['password'] = password
                
                await client.sign_in(**kwargs)
                
                account.session_data = StringSession.save(client.session)
                account.status = 'active'
                account.is_connected = True
                
                me = await client.get_me()
                account.display_name = f"{me.first_name or ''} {me.last_name or ''}".strip() or account.phone
                account.external_id = str(me.id)
                account.save()
                return 'success'
            finally:
                try:
                    await client.disconnect()
                except:
                    pass
        
        status = run_async(verify_code())
        if status == 'success':
            messages.success(request, f"{account.display_name} muvaffaqiyatli ulandi! ✅")
            return redirect('base:chat_list')
    except Exception as e:
        error_msg = str(e)
        if 'PHONE_CODE_INVALID' in error_msg:
            return render(request, 'base/chat_verify.html', {
                'account': account, 'error': "Kod noto'g'ri! Qaytadan urinib ko'ring."
            })
        elif 'SESSION_PASSWORD_NEEDED' in error_msg:
            return render(request, 'base/chat_verify.html', {
                'account': account, 'need_password': True
            })
        else:
            logger.exception("Verify xatosi")
            return render(request, 'base/chat_verify.html', {
                'account': account, 'error': f"Xatolik: {error_msg[:150]}"
            })
    
    return redirect('base:chat_list')


@login_required
def chat_settings(request, account_id):
    account = get_object_or_404(SocialAccount, id=account_id, user=request.user, account_type='user')
    config, _ = AgentConfig.objects.get_or_create(social_account=account)
    logs = ConversationLog.objects.filter(social_account=account)[:50]
    credentials = AIProviderCredential.objects.filter(user=request.user).select_related('provider')
    return render(request, 'base/chat_settings.html', {'account': account, 'config': config, 'logs': logs, 'credentials': credentials})


@login_required
@require_POST
def chat_settings_save(request, account_id):
    return bot_settings_save(request, account_id)


@login_required
@require_POST
def chat_delete(request, account_id):
    account = get_object_or_404(SocialAccount, id=account_id, user=request.user, account_type='user')
    account.delete()
    messages.success(request, "Chat account o'chirildi")
    return redirect('base:chat_list')


@login_required
@require_POST
def chat_toggle(request, account_id):
    account = get_object_or_404(SocialAccount, id=account_id, user=request.user, account_type='user')
    account.status = 'paused' if account.status == 'active' else 'active'
    account.save(update_fields=['status'])
    return redirect('base:chat_list')


# ===== API Keys =====

@login_required
def api_keys(request):
    providers = AIProvider.objects.filter(is_active=True)
    credentials = AIProviderCredential.objects.filter(user=request.user).select_related('provider')
    return render(request, 'base/api_keys.html', {'providers': providers, 'credentials': credentials})

@login_required
@require_POST
def api_key_add(request):
    provider_id = request.POST.get('provider')
    label = request.POST.get('label', '').strip()
    api_key = request.POST.get('api_key', '').strip()
    model_name = request.POST.get('model_name', '').strip()
    if not all([provider_id, label, api_key, model_name]):
        messages.error(request, "Barcha maydonlarni to'ldiring!")
        return redirect('base:api_keys')
    AIProviderCredential.objects.create(user=request.user, provider_id=int(provider_id), label=label, api_key=api_key, model_name=model_name, base_url_override=request.POST.get('base_url', ''), is_valid=True)
    messages.success(request, "API kalit qo'shildi!")
    return redirect('base:api_keys')

@login_required
@require_POST
def api_key_delete(request, credential_id):
    get_object_or_404(AIProviderCredential, id=credential_id, user=request.user).delete()
    messages.success(request, "API kalit o'chirildi")
    return redirect('base:api_keys')

@login_required
@require_POST
def api_key_validate(request, credential_id):
    from apps.ai_providers.router import get_adapter
    credential = get_object_or_404(AIProviderCredential, id=credential_id, user=request.user)
    adapter = get_adapter(credential)
    credential.is_valid = adapter.validate_credential() if adapter else False
    credential.save(update_fields=['is_valid'])
    messages.info(request, f"{credential.label}: {'ishlaydi ✅' if credential.is_valid else 'ishlamaydi ❌'}")
    return redirect('base:api_keys')
