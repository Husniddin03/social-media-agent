import json
import logging
import requests

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib import messages

from apps.social.models import SocialPlatform, SocialAccount
from apps.agents.models import AgentConfig, ConversationLog
from apps.ai_providers.models import AIProvider, AIProviderCredential

logger = logging.getLogger('apps.base')
TELEGRAM_API = 'https://api.telegram.org/bot'


def index(request):
    """Asosiy dashboard"""
    return render(request, 'base/index.html')


def telegram(request):
    """Telegram hub - Chatlar va Botlar"""
    accounts = SocialAccount.objects.filter(
        user=request.user if request.user.is_authenticated else None,
        platform__slug='telegram'
    ).select_related('platform') if request.user.is_authenticated else []
    
    return render(request, 'base/telegram.html', {
        'accounts': accounts,
    })


@login_required
def bot_list(request):
    """Botlar ro'yxati + qo'shish"""
    accounts = SocialAccount.objects.filter(
        user=request.user,
        platform__slug='telegram',
    ).select_related('platform')
    
    return render(request, 'base/bot_list.html', {
        'accounts': accounts,
    })


@login_required
@require_POST
def bot_add(request):
    """Yangi bot qo'shish (token orqali)"""
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

    try:
        platform = SocialPlatform.objects.get(slug='telegram')
    except SocialPlatform.DoesNotExist:
        messages.error(request, "Telegram platformasi topilmadi!")
        return redirect('base:bot_list')

    account, created = SocialAccount.objects.get_or_create(
        user=request.user,
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
        AgentConfig.objects.get_or_create(
            social_account=account,
            defaults={
                'system_prompt': (
                    "Siz foydalanuvchilarga yordam beruvchi AI yordamchisiz. "
                    "Savollarga aniq, foydali va do'stona javob bering."
                ),
                'is_enabled': True,
            }
        )
        webhook_url = request.build_absolute_uri(f'/social/telegram/webhook/{account.id}/')
        try:
            wh_resp = requests.post(
                f'{TELEGRAM_API}{bot_token}/setWebhook',
                json={'url': webhook_url},
                timeout=15,
            )
            wh_data = wh_resp.json()
            if wh_data.get('ok'):
                account.is_connected = True
                account.save(update_fields=['is_connected'])
                messages.success(request, f"@{bot_username} qo'shildi va webhook o'rnatildi!")
            else:
                messages.warning(request, f"Bot qo'shildi, webhook xatosi: {wh_data.get('description', '')}")
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
    """Bot sozlamalari"""
    account = get_object_or_404(SocialAccount, id=account_id, user=request.user)
    config, _ = AgentConfig.objects.get_or_create(social_account=account)
    logs = ConversationLog.objects.filter(social_account=account)[:50]
    credentials = AIProviderCredential.objects.filter(user=request.user).select_related('provider')
    
    return render(request, 'base/bot_settings.html', {
        'account': account,
        'config': config,
        'logs': logs,
        'credentials': credentials,
    })


@login_required
@require_POST
def bot_settings_save(request, account_id):
    """AgentConfig sozlamalarini saqlash"""
    account = get_object_or_404(SocialAccount, id=account_id, user=request.user)
    config, _ = AgentConfig.objects.get_or_create(social_account=account)
    
    credential_id = request.POST.get('ai_credential')
    if credential_id:
        config.ai_credential_id = int(credential_id)
    else:
        config.ai_credential = None
    
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
    name = account.display_name
    account.delete()
    messages.success(request, f"{name} o'chirildi")
    return redirect('base:bot_list')


@login_required
@require_POST
def bot_toggle(request, account_id):
    account = get_object_or_404(SocialAccount, id=account_id, user=request.user)
    account.status = 'paused' if account.status == 'active' else 'active'
    account.save(update_fields=['status'])
    config = AgentConfig.objects.filter(social_account=account).first()
    if config:
        config.is_enabled = account.status == 'active'
        config.save(update_fields=['is_enabled'])
    messages.success(request, f"{account.display_name} {'faollashtirildi' if account.status == 'active' else 'toxtatildi'}")
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
        resp = requests.post(
            f'{TELEGRAM_API}{account.access_token}/setWebhook',
            json={'url': webhook_url},
            timeout=15,
        )
        data = resp.json()
        if data.get('ok'):
            account.is_connected = True
            account.save(update_fields=['is_connected'])
            messages.success(request, "Webhook qayta o'rnatildi!")
        else:
            messages.error(request, f"Xato: {data.get('description', '')}")
    except Exception as e:
        messages.error(request, f"Xato: {e}")
    return redirect('base:bot_settings', account_id=account.id)


@login_required
def api_keys(request):
    """API kalitlarini boshqarish"""
    providers = AIProvider.objects.filter(is_active=True)
    credentials = AIProviderCredential.objects.filter(user=request.user).select_related('provider')
    return render(request, 'base/api_keys.html', {
        'providers': providers,
        'credentials': credentials,
    })


@login_required
@require_POST
def api_key_add(request):
    """Yangi API kalit qo'shish"""
    provider_id = request.POST.get('provider')
    label = request.POST.get('label', '').strip()
    api_key = request.POST.get('api_key', '').strip()
    model_name = request.POST.get('model_name', '').strip()
    
    if not all([provider_id, label, api_key, model_name]):
        messages.error(request, "Barcha maydonlarni to'ldiring!")
        return redirect('base:api_keys')
    
    AIProviderCredential.objects.create(
        user=request.user,
        provider_id=int(provider_id),
        label=label,
        api_key=api_key,
        model_name=model_name,
        base_url_override=request.POST.get('base_url', ''),
        is_valid=True,
    )
    messages.success(request, "API kalit qo'shildi!")
    return redirect('base:api_keys')


@login_required
@require_POST
def api_key_delete(request, credential_id):
    credential = get_object_or_404(AIProviderCredential, id=credential_id, user=request.user)
    credential.delete()
    messages.success(request, "API kalit o'chirildi")
    return redirect('base:api_keys')


@login_required
@require_POST
def api_key_validate(request, credential_id):
    """API kalitni tekshirish"""
    from apps.ai_providers.router import get_adapter
    credential = get_object_or_404(AIProviderCredential, id=credential_id, user=request.user)
    adapter = get_adapter(credential)
    if adapter:
        credential.is_valid = adapter.validate_credential()
    else:
        credential.is_valid = False
    credential.save(update_fields=['is_valid'])
    status = "ishlaydi ✅" if credential.is_valid else "ishlamaydi ❌"
    messages.info(request, f"{credential.label}: {status}")
    return redirect('base:api_keys')
