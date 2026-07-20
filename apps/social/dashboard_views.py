"""
Dashboard views — botlarni boshqarish uchun asosiy interfeys.
Hammasi bazadan, hech qanday env/konfig talab qilinmaydi.
"""
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

logger = logging.getLogger('apps.social.dashboard')

TELEGRAM_API = 'https://api.telegram.org/bot'


@login_required
def dashboard(request):
    """Asosiy dashboard — botlar ro'yxati va statistika"""
    platforms = SocialPlatform.objects.filter(is_active=True)
    accounts = SocialAccount.objects.filter(user=request.user).select_related('platform')
    
    stats = {
        'total_bots': accounts.count(),
        'active_bots': accounts.filter(status='active').count(),
        'connected_bots': accounts.filter(is_connected=True).count(),
    }
    
    return render(request, 'social/dashboard.html', {
        'platforms': platforms,
        'accounts': accounts,
        'stats': stats,
    })


@login_required
def add_bot(request):
    """Yangi Telegram bot qo'shish — token orqali avtomatik sozlash"""
    if request.method == 'POST':
        bot_token = request.POST.get('bot_token', '').strip()
        
        if not bot_token:
            messages.error(request, "Bot tokeni kerak!")
            return redirect('dashboard')
        
        # Bot ma'lumotlarini Telegram'dan olish
        try:
            resp = requests.get(f'{TELEGRAM_API}{bot_token}/getMe', timeout=10)
            data = resp.json()
            if not data.get('ok'):
                messages.error(request, f"Token yaroqsiz: {data.get('description', '')}")
                return redirect('dashboard')
            
            bot_info = data['result']
            bot_username = bot_info.get('username', '')
            bot_name = bot_info.get('first_name', bot_username)
        except requests.exceptions.ConnectionError:
            messages.error(request, "Telegram API ga ulanishda xato!")
            return redirect('dashboard')
        
        # Platformani olish
        try:
            platform = SocialPlatform.objects.get(slug='telegram')
        except SocialPlatform.DoesNotExist:
            messages.error(request, "Telegram platformasi topilmadi!")
            return redirect('dashboard')
        
        # Botni bazaga saqlash
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
            # Avtomatik AgentConfig yaratish
            AgentConfig.objects.get_or_create(
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
            
            # Webhook'ni avtomatik o'rnatish
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
                    messages.success(request, f"@{bot_username} muvaffaqiyatli qo'shildi va webhook o'rnatildi!")
                else:
                    messages.warning(request, f"Bot qo'shildi, lekin webhook xatosi: {wh_data.get('description', '')}")
            except Exception as e:
                messages.warning(request, f"Bot qo'shildi, lekin webhook xatosi: {e}")
        else:
            # Mavjud bot — tokenni yangilash
            account.access_token = bot_token
            account.status = 'active'
            account.save()
            messages.info(request, f"@{bot_username} yangilandi")
        
        return redirect('dashboard')
    
    return redirect('dashboard')


@login_required
def bot_settings(request, account_id):
    """Bitta bot uchun sozlamalar sahifasi"""
    account = get_object_or_404(SocialAccount, id=account_id, user=request.user)
    config, _ = AgentConfig.objects.get_or_create(social_account=account)
    logs = ConversationLog.objects.filter(social_account=account)[:50]
    
    return render(request, 'social/bot_settings.html', {
        'account': account,
        'config': config,
        'logs': logs,
    })


@login_required
@require_POST
def update_agent_config(request, account_id):
    """AgentConfig sozlamalarini saqlash"""
    account = get_object_or_404(SocialAccount, id=account_id, user=request.user)
    config, _ = AgentConfig.objects.get_or_create(social_account=account)
    
    config.system_prompt = request.POST.get('system_prompt', config.system_prompt)
    config.tone = request.POST.get('tone', config.tone)
    config.language_mode = request.POST.get('language_mode', config.language_mode)
    config.max_response_length = int(request.POST.get('max_response_length', config.max_response_length))
    config.is_enabled = request.POST.get('is_enabled') == 'on'
    config.fallback_to_human = request.POST.get('fallback_to_human') == 'on'
    config.save()
    
    messages.success(request, "Sozlamalar saqlandi!")
    return redirect('bot_settings', account_id=account.id)


@login_required
@require_POST
def delete_bot(request, account_id):
    """Botni o'chirish"""
    account = get_object_or_404(SocialAccount, id=account_id, user=request.user)
    name = account.display_name
    account.delete()
    messages.success(request, f"{name} o'chirildi")
    return redirect('dashboard')


@login_required
@require_POST
def reconnect_webhook(request, account_id):
    """Bot webhook'ni qayta ulash"""
    account = get_object_or_404(SocialAccount, id=account_id, user=request.user)
    
    if not account.access_token:
        messages.error(request, "Bot tokeni topilmadi!")
        return redirect('bot_settings', account_id=account.id)
    
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
    
    return redirect('bot_settings', account_id=account.id)


@login_required
@require_POST
def toggle_bot_status(request, account_id):
    """Bot faolligini o'zgartirish (active/paused)"""
    account = get_object_or_404(SocialAccount, id=account_id, user=request.user)
    account.status = 'paused' if account.status == 'active' else 'active'
    account.save(update_fields=['status'])
    
    config = AgentConfig.objects.filter(social_account=account).first()
    if config:
        config.is_enabled = account.status == 'active'
        config.save(update_fields=['is_enabled'])
    
    status_text = "faollashtirildi" if account.status == 'active' else "to'xtatildi"
    messages.success(request, f"{account.display_name} {status_text}")
    return redirect('dashboard')
