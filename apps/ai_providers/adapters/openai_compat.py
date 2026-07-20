"""OpenAI-mos AI provayderlar uchun adapter (OpenAI, Groq, DeepSeek va h.k.)"""
import logging
import requests
from .base import BaseAIAdapter, AIResponse

logger = logging.getLogger('apps.ai_providers.adapters')


class OpenAICompatAdapter(BaseAIAdapter):
    """OpenAI /chat/completions API'siga mos har qanday provayder uchun adapter"""

    def generate_reply(self, system_prompt: str, user_message: str,
                       context: list[dict] | None = None) -> AIResponse:
        messages = [{'role': 'system', 'content': system_prompt}]
        if context:
            for msg in context:
                messages.append(msg)
        messages.append({'role': 'user', 'content': user_message})

        base = (self.base_url or 'https://api.openai.com/v1').rstrip('/')
        try:
            resp = requests.post(
                f'{base}/chat/completions',
                headers={
                    'Authorization': f'Bearer {self.api_key}',
                    'Content-Type': 'application/json',
                },
                json={
                    'model': self.model,
                    'messages': messages,
                    'max_tokens': self.extra_config.get('max_tokens', 1000),
                    'temperature': self.extra_config.get('temperature', 0.7),
                },
                timeout=30,
            )
            if resp.status_code >= 400:
                return AIResponse(
                    text='', error=f'API xato {resp.status_code}: {resp.text[:200]}'
                )

            data = resp.json()
            choice = (data.get('choices') or [{}])[0]
            text = (choice.get('message') or {}).get('content', '') or ''
            usage = data.get('usage', {}) or {}
            tokens = (usage.get('total_tokens') or
                      usage.get('completion_tokens', 0))

            return AIResponse(
                text=text.strip(),
                tokens_used=tokens or 0,
                model_used=data.get('model', self.model),
            )
        except requests.exceptions.Timeout:
            return AIResponse(text='', error='AI so\'rovi vaqt tugadi (timeout)')
        except requests.exceptions.ConnectionError:
            return AIResponse(text='', error='AI provayderga ulanishda xato')
        except Exception as e:
            logger.exception('OpenAICompatAdapter xato')
            return AIResponse(text='', error=str(e)[:300])

    def validate_credential(self) -> bool:
        base = (self.base_url or 'https://api.openai.com/v1').rstrip('/')
        try:
            resp = requests.get(
                f'{base}/models',
                headers={'Authorization': f'Bearer {self.api_key}'},
                timeout=10,
            )
            return resp.status_code == 200
        except Exception:
            return False
