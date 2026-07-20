"""Google Gemini adapter — native REST API orqali, google-genai kutubxonasisiz"""
import logging
import requests
from .base import BaseAIAdapter, AIResponse

logger = logging.getLogger('apps.ai_providers.adapters.gemini')

GEMINI_BASE = 'https://generativelanguage.googleapis.com/v1beta'


class GeminiAdapter(BaseAIAdapter):
    """Google Gemini AI adapter — requests orqali to'g'ridan-to'g'ri API chaqiradi"""

    def generate_reply(self, system_prompt: str, user_message: str,
                       context: list[dict] | None = None) -> AIResponse:
        model = self.model or 'gemini-2.0-flash'
        url = f'{GEMINI_BASE}/models/{model}:generateContent'

        # Gemini formatidagi content structure
        contents = []
        if context:
            for msg in context:
                role = 'user' if msg.get('role') == 'user' else 'model'
                contents.append({
                    'role': role,
                    'parts': [{'text': msg.get('content', '')}]
                })
        contents.append({
            'role': 'user',
            'parts': [{'text': user_message}]
        })

        body = {
            'contents': contents,
            'generationConfig': {
                'maxOutputTokens': self.extra_config.get('max_tokens', 1000),
                'temperature': self.extra_config.get('temperature', 0.7),
            }
        }

        if system_prompt:
            body['systemInstruction'] = {
                'parts': [{'text': system_prompt}]
            }

        try:
            resp = requests.post(
                url,
                params={'key': self.api_key},
                json=body,
                timeout=30,
            )
            if resp.status_code >= 400:
                return AIResponse(
                    text='', error=f'Gemini API xato {resp.status_code}: {resp.text[:200]}'
                )

            data = resp.json()
            candidates = data.get('candidates', []) or []
            if not candidates:
                block_reason = (data.get('promptFeedback') or {}).get('blockReason', 'noma\'lum')
                return AIResponse(text='', error=f'Javob bloklandi: {block_reason}')

            text = ''
            parts = (candidates[0].get('content', {}) or {}).get('parts', []) or []
            for part in parts:
                text += part.get('text', '')

            # Token hisobi
            usage = data.get('usageMetadata', {}) or {}
            tokens = (usage.get('totalTokenCount') or
                      usage.get('candidatesTokenCount', 0))

            return AIResponse(
                text=text.strip(),
                tokens_used=tokens or 0,
                model_used=model,
            )
        except requests.exceptions.Timeout:
            return AIResponse(text='', error='Gemini so\'rovi vaqt tugadi (timeout)')
        except requests.exceptions.ConnectionError:
            return AIResponse(text='', error='Gemini serveriga ulanishda xato')
        except Exception as e:
            logger.exception('GeminiAdapter xato')
            return AIResponse(text='', error=str(e)[:300])

    def validate_credential(self) -> bool:
        """Gemini API kalitini tekshirish — modellar ro'yxatini olish"""
        try:
            resp = requests.get(
                f'{GEMINI_BASE}/models',
                params={'key': self.api_key},
                timeout=10,
            )
            return resp.status_code == 200
        except Exception:
            return False
