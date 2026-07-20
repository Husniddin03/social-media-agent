"""Markaziy dispetcher — kiruvchi xabarni AgentConfig bo'yicha AI'ga yo'naltiradi"""
import logging
import time
from django.utils import timezone as tz

from apps.social.models import SocialAccount
from apps.agents.models import AgentConfig, ConversationLog, UsageStats
from apps.ai_providers.router import generate_with_credential, generate_with_free_keys

logger = logging.getLogger('apps.agents.dispatcher')


def handle_incoming(social_account: SocialAccount,
                    external_user_id: str,
                    external_user_name: str,
                    message_text: str) -> dict:
    """
    Kiruvchi xabarni qayta ishlash.
    
    1. SocialAccount ga tegishli AgentConfig ni topadi
    2. Agar AgentConfig AI credentialga ega bo'lsa, shu credential orqali javob oladi
    3. Agar credential bo'lmasa, FreeApiKey (tekin kalitlar) orqali javob oladi
    4. Javobni Telegram'ga yuborish uchun qaytaradi
    5. ConversationLog ga yozadi
    
    Returns:
        {'success': True, 'response_text': '...'} yoki {'success': False, 'error': '...'}
    """
    start_time = time.time()
    
    try:
        # AgentConfig ni topish
        agent_config = AgentConfig.objects.filter(
            social_account=social_account,
            is_enabled=True,
        ).select_related('ai_credential', 'ai_credential__provider').first()
        
        if not agent_config:
            logger.info("AgentConfig topilmadi: %s", social_account.display_name)
            return _log_and_return(
                social_account, external_user_id, external_user_name,
                message_text, '', 0, 'failed',
                "Agent sozlamalari topilmadi. Iltimos, avval agentingizni sozlang.",
                start_time,
            )
        
        # AI javob olish
        system_prompt = agent_config.system_prompt
        
        ai_response = None
        
        # 1) Foydalanuvchining shaxsiy AI kaliti orqali
        if agent_config.ai_credential and agent_config.ai_credential.is_valid:
            try:
                ai_response = generate_with_credential(
                    agent_config.ai_credential,
                    system_prompt,
                    message_text,
                )
            except Exception as e:
                logger.warning("Shaxsiy kalit xatosi: %s", e)
        
        # 2) Free API keys orqali (zaxira)
        if not ai_response or not ai_response.text:
            try:
                ai_response = generate_with_free_keys(system_prompt, message_text)
            except Exception as e:
                logger.warning("Free keys xatosi: %s", e)
        
        # 3) Hech narsa ishlamadi
        if not ai_response or not ai_response.text:
            error_msg = ai_response.error if ai_response else "AI javob bera olmadi"
            if agent_config.fallback_to_human:
                fallback_msg = "Kechirasiz, hozir operator bilan bog'lanmoqdamiz. Birozdan so'ng javob beramiz."
                return _log_and_return(
                    social_account, external_user_id, external_user_name,
                    message_text, '', 0, 'escalated',
                    fallback_msg, start_time,
                )
            return _log_and_return(
                social_account, external_user_id, external_user_name,
                message_text, '', 0, 'failed',
                f"Xatolik yuz berdi: {error_msg}",
                start_time,
            )
        
        # Javobni log'ga yozish
        elapsed = int((time.time() - start_time) * 1000)
        return _log_and_return(
            social_account, external_user_id, external_user_name,
            message_text, ai_response.text, ai_response.tokens_used, 'sent',
            ai_response.text, start_time, elapsed,
        )
        
    except Exception as e:
        logger.exception("Dispatcher xatosi")
        elapsed = int((time.time() - start_time) * 1000)
        return _log_and_return(
            social_account, external_user_id, external_user_name,
            message_text, '', 0, 'failed',
            "Texnik xatolik yuz berdi. Iltimos, keyinroq urinib ko'ring.",
            start_time, elapsed,
        )


def _log_and_return(social_account, ext_user_id, ext_user_name,
                    incoming, response_text, tokens, status,
                    return_text, start_time, elapsed=0):
    """ConversationLog ga yozish va natijani qaytarish"""
    # Failed/escalated holatda ai_response bo'sh, error_message esa foydalanuvchiga ko'rsatiladigan matn
    error_msg = return_text if status in ('failed', 'escalated') else ''
    ai_resp = response_text if status == 'sent' else ''
    
    log_entry = ConversationLog.objects.create(
        social_account=social_account,
        external_user_id=ext_user_id,
        external_user_name=ext_user_name or ext_user_id,
        incoming_message=incoming,
        ai_response=ai_resp,
        tokens_used=tokens,
        response_time_ms=elapsed or int((time.time() - start_time) * 1000),
        status=status,
        error_message=error_msg,
    )
    
    # UsageStats ni yangilash (kunlik)
    today = tz.now().date()
    stats, _ = UsageStats.objects.get_or_create(
        social_account=social_account,
        date=today,
    )
    stats.messages_count += 1
    stats.tokens_used += tokens
    stats.save(update_fields=['messages_count', 'tokens_used'])
    
    if status in ('failed', 'escalated'):
        return {'success': False, 'response_text': return_text, 'log_id': log_entry.id}
    
    return {'success': True, 'response_text': response_text, 'log_id': log_entry.id}
