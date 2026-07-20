"""AI provayder router — to'g'ri adapterni tanlab, javob qaytaradi"""
import logging
from .adapters.base import AIResponse
from .adapters.openai_compat import OpenAICompatAdapter
from .models import AIProvider, AIProviderCredential

logger = logging.getLogger('apps.ai_providers.router')

# Oddiy adapter registry — keyinchalik dinamik yuklashga o'tkaziladi
_ADAPTER_MAP: dict[str, type] = {}


def register_adapter(slug: str, adapter_class: type):
    """Adapter'ni ro'yxatdan o'tkazish (plugin arxitektura uchun)"""
    _ADAPTER_MAP[slug] = adapter_class


# Standart adapterlarni ro'yxatdan o'tkazish
register_adapter('openai', OpenAICompatAdapter)
register_adapter('openrouter', OpenAICompatAdapter)
register_adapter('groq', OpenAICompatAdapter)
register_adapter('deepseek', OpenAICompatAdapter)
register_adapter('mistral', OpenAICompatAdapter)
register_adapter('cerebras', OpenAICompatAdapter)
register_adapter('github_models', OpenAICompatAdapter)
register_adapter('dashscope', OpenAICompatAdapter)


def get_adapter(credential: AIProviderCredential) -> OpenAICompatAdapter | None:
    """AIProviderCredential asosida to'g'ri adapterni yaratish"""
    slug = credential.provider.slug
    adapter_class = _ADAPTER_MAP.get(slug)

    if not adapter_class:
        # Noma'lum provayder — OpenAI-mos deb taxmin qilamiz
        adapter_class = OpenAICompatAdapter
        logger.warning("Noma'lum provayder '%s', OpenAI-mos adapter ishlatiladi", slug)

    base_url = credential.base_url_override or credential.provider.default_base_url
    return adapter_class(
        api_key=credential.api_key,
        model=credential.model_name,
        base_url=base_url,
        extra_config=credential.extra_config,
    )


def generate_with_credential(credential: AIProviderCredential,
                              system_prompt: str,
                              user_message: str,
                              context: list[dict] | None = None) -> AIResponse:
    """Bitta credential orqali AI javob olish"""
    adapter = get_adapter(credential)
    if not adapter:
        return AIResponse(text='', error='Adapter topilmadi')
    return adapter.generate_reply(system_prompt, user_message, context)


def generate_with_free_keys(system_prompt: str,
                             user_message: str) -> AIResponse:
    """Mavjud FreeApiKey'lar orqali tekin AI javob olish (apps/api/chat.py dan foydalanadi)"""
    try:
        from apps.api.chat import try_free_keys
        schema = {
            'type': 'object',
            'properties': {
                'response': {'type': 'string'},
            },
            'required': ['response'],
        }
        result = try_free_keys(system_prompt, [{'role': 'user', 'content': user_message}], schema)
        if result and 'response' in result:
            return AIResponse(
                text=result['response'],
                tokens_used=0,
                model_used=(result.get('_ai_meta') or {}).get('model', 'free'),
            )
        return AIResponse(text='', error='Tekin kalitlar ishlamadi')
    except Exception as e:
        logger.exception('Free keys generate xato')
        return AIResponse(text='', error=str(e)[:300])
