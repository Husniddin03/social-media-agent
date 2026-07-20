"""
Telegram bot webhook handler.
Telegram'dan kelgan update'larni qabul qiladi va agents dispatcher'ga yo'naltiradi.
"""
import json
import logging
import requests

from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from apps.social.models import SocialAccount
from apps.agents.dispatcher import handle_incoming

logger = logging.getLogger('apps.social.telegram')

TELEGRAM_API = 'https://api.telegram.org/bot'


def _send_message(bot_token: str, chat_id: int, text: str) -> bool:
    """Telegram'ga xabar yuborish"""
    try:
        resp = requests.post(
            f'{TELEGRAM_API}{bot_token}/sendMessage',
            json={
                'chat_id': chat_id,
                'text': text,
                'parse_mode': 'HTML',
            },
            timeout=15,
        )
        if not resp.ok:
            logger.warning("sendMessage xato %s: %s", resp.status_code, resp.text[:200])
        return resp.ok
    except Exception as e:
        logger.exception("sendMessage xatosi")
        return False


@csrf_exempt
@require_POST
def webhook(request, account_id):
    """
    Telegram webhook endpoint.
    
    Telegram'dan POST so'rov kelganda:
    1. SocialAccount ni account_id bo'yicha topadi
    2. Xabar matni va foydalanuvchi ma'lumotlarini ajratadi
    3. Dispatcher'ga yuboradi
    4. AI javobini Telegram'ga qaytaradi
    """
    try:
        update = json.loads(request.body)
    except json.JSONDecodeError:
        return HttpResponse(status=400)

    # SocialAccount ni topish
    try:
        social_account = SocialAccount.objects.get(
            id=account_id,
            platform__slug='telegram',
            status='active',
        )
    except SocialAccount.DoesNotExist:
        logger.warning("SocialAccount topilmadi: %s", account_id)
        return HttpResponse(status=404)

    bot_token = social_account.access_token
    if not bot_token:
        logger.error("Bot token topilmadi: %s", account_id)
        return HttpResponse(status=500)

    # Xabar ma'lumotlarini ajratish
    message = update.get('message') or update.get('edited_message') or {}
    
    # /start va boshqa command'larni ham qayta ishlaymiz
    text = message.get('text', '')
    if not text:
        # Rasm, sticker, video va h.k. — hozircha qo'llab-quvvatlanmaydi
        chat_id = (message.get('chat') or {}).get('id')
        if chat_id:
            _send_message(bot_token, chat_id, 
                         "Kechirasiz, hozircha faqat matnli xabarlarni qabul qila olaman.")
        return HttpResponse(status=200)

    chat = message.get('chat', {})
    chat_id = chat.get('id')
    from_user = message.get('from', {})
    user_id = str(from_user.get('id', ''))
    user_name = (from_user.get('first_name', '') or '') + ' ' + (from_user.get('last_name', '') or '')
    user_name = user_name.strip() or from_user.get('username', '') or user_id

    if not chat_id:
        return HttpResponse(status=200)

    # /start command
    if text.startswith('/start'):
        welcome = (
            "Assalomu alaykum! 👋\n\n"
            "Men AI yordamchi botman. Menga istalgan savolingizni yozishingiz mumkin, "
            "men esa AI yordamida javob beraman.\n\n"
            "Qanday yordam kerak?"
        )
        _send_message(bot_token, chat_id, welcome)
        return HttpResponse(status=200)

    # Dispatcher'ga yuborish
    result = handle_incoming(
        social_account=social_account,
        external_user_id=user_id,
        external_user_name=user_name,
        message_text=text,
    )

    # Javobni yuborish
    response_text = result.get('response_text', '')
    if response_text:
        _send_message(bot_token, chat_id, response_text)

    return HttpResponse(status=200)


def set_webhook(request):
    """
    Bot uchun webhook'ni Telegram'da ro'yxatdan o'tkazish.
    
    URL: /telegram/bot/set-webhook/
    
    SocialAccount da saqlangan bot token bo'yicha Telegram'ga webhook URL yuboradi.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'POST kerak'}, status=405)

    account_id = request.POST.get('account_id')
    if not account_id:
        return JsonResponse({'error': 'account_id kerak'}, status=400)

    try:
        social_account = SocialAccount.objects.get(
            id=account_id,
            platform__slug='telegram',
        )
    except SocialAccount.DoesNotExist:
        return JsonResponse({'error': 'SocialAccount topilmadi'}, status=404)

    bot_token = social_account.access_token
    if not bot_token:
        return JsonResponse({'error': 'Bot token topilmadi'}, status=400)

    webhook_url = request.build_absolute_uri(f'/social/telegram/webhook/{account_id}/')

    try:
        resp = requests.post(
            f'{TELEGRAM_API}{bot_token}/setWebhook',
            json={'url': webhook_url},
            timeout=15,
        )
        data = resp.json()
        if data.get('ok'):
            social_account.is_connected = True
            social_account.save(update_fields=['is_connected'])
            return JsonResponse({'ok': True, 'message': 'Webhook o\'rnatildi'})
        else:
            return JsonResponse({'ok': False, 'error': data.get('description', '')}, status=400)
    except Exception as e:
        logger.exception("setWebhook xatosi")
        return JsonResponse({'ok': False, 'error': str(e)}, status=500)


def webhook_info(request):
    """Bot webhook holatini ko'rish"""
    bot_token = request.GET.get('token', '')
    if not bot_token:
        return JsonResponse({'error': 'token kerak'}, status=400)

    try:
        resp = requests.get(f'{TELEGRAM_API}{bot_token}/getWebhookInfo', timeout=10)
        data = resp.json()
        return JsonResponse(data)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
