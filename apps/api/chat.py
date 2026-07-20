"""
apps/api/chat.py — 2026-07-18 (foydalanuvchi so'rovi): tekin API
kalitlar orqali strukturali (JSON) AI javob olish.

instacore/chatplace_ai.py Anthropic'ni chaqirishdan OLDIN `try_free_keys()`ni
sinaydi (tejash uchun — tekin kalit ishlasa, pulli Anthropic/OpenRouter
chaqirilmaydi). Muvaffaqiyatsiz bo'lsa (yoki faol kalit yo'q) None qaytadi —
chaqiruvchi o'zining odatdagi Anthropic->OpenRouter->Gemini zanjiriga
o'zgarishsiz davom etadi.
"""
import json
import logging
import re

import requests

logger = logging.getLogger('apps.api')

_PROVIDER_BASE_URL = {
    'openrouter': 'https://openrouter.ai/api/v1',
    'groq': 'https://api.groq.com/openai/v1',
    'mistral': 'https://api.mistral.ai/v1',
    'cerebras': 'https://api.cerebras.ai/v1',
}
_TIMEOUT = 25


def _messages_from_history(msgs):
    """chatplace_ai.py Anthropic-uslub xabarlar ro'yxati (yoki bitta matn)ni
    OpenAI-mos {'role','content'} ro'yxatiga tekislaydi."""
    if isinstance(msgs, str):
        return [{'role': 'user', 'content': msgs}]
    out = []
    for m in (msgs or []):
        role = m.get('role', 'user')
        content = m.get('content')
        if isinstance(content, list):
            content = ' '.join(str(c.get('text', '')) for c in content if isinstance(c, dict))
        out.append({'role': role, 'content': str(content or '')})
    return out


def _strip_code_fence(text):
    text = text.strip()
    if text.startswith('```'):
        text = re.sub(r'^```[a-zA-Z]*\s*', '', text)
        text = re.sub(r'\s*```\s*$', '', text)
    return text


def _validate_against_schema(parsed, schema):
    """2026-07-18 (real bug — birinchi tekin-kalit sinovida aniqlandi):
    ba'zi zaif/kichik modellar 'JSON Schema'ga mos javob ber' deyilganda
    SXEMANING O'ZINI ('type'/'properties'/'required' kalitlari bilan)
    qaytarib yuboradi — bu `json.loads()` uchun to'g'ri dict, lekin MA'NOSIZ
    javob. Majburiy maydonlar to'g'ridan-to'g'ri natija ichida (sxema
    tuzilishi emas) borligini tekshiradi — bo'lmasa xato ko'taradi va
    navbatdagi kalit/model sinaladi."""
    if 'properties' in parsed or 'type' in parsed and 'required' in parsed:
        raise ValueError("model sxemaning o'zini qaytardi, haqiqiy javob emas")
    for field in schema.get('required', []):
        if field not in parsed:
            raise ValueError(f"majburiy maydon yo'q: {field}")


def _openai_compatible_call(base_url, key, model, sys_full, body_messages, max_tokens):
    resp = requests.post(
        f'{base_url}/chat/completions',
        headers={'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'},
        json={'model': model, 'messages': [{'role': 'system', 'content': sys_full}] + body_messages,
             'response_format': {'type': 'json_object'}, 'max_tokens': max_tokens},
        timeout=_TIMEOUT,
    )
    if resp.status_code >= 400:
        raise RuntimeError(f'{base_url} xato {resp.status_code}: {resp.text[:200]}')
    data = resp.json()
    text = _strip_code_fence((data.get('choices') or [{}])[0].get('message', {}).get('content', '') or '')
    return json.loads(text)


def _openai_compatible_structured(base_url, key, model, system, msgs, schema):
    """OpenRouter/Groq/Mistral/Cerebras/Cohere/GitHub Models — hammasi
    OpenAI-mos /chat/completions. Har birining `json_schema` strict-
    rejimini teng qo'llab-quvvatlashi ISHONCHSIZ (ba'zi model/provayderda
    rad etilishi mumkin) — shuning uchun kengroq mos keluvchi `json_object`
    rejimi + sxema-promptga yozilgan holda ishlatiladi (loyihada allaqachon
    o'rnatilgan naqsh: modelga qattiq ishonmaslik, har doim kod darajasida
    tekshirish).

    2026-07-18 (real hodisa — birinchi tekin-kalit jonli sinovida ~1/3
    holatda aniqlandi): ba'zi javoblar `max_tokens` chegarasida matn
    o'rtasida KESILIB qoladi (JSON tugallanmay qoladi, `json.loads()` xato
    beradi) — bir marta KENGROQ max_tokens bilan qayta urinish qo'shildi
    (Anthropic tomondagi haiku-fallback bilan bir xil "modelga ishonma,
    qayta urin" naqshi)."""
    schema_txt = json.dumps(schema, ensure_ascii=False)
    sys_full = (system or '') + (
        "\n\nJAVOBNI FAQAT quyidagi JSON Schema shakliga mos, boshqa HECH "
        f"NARSASIZ (izohsiz, ```siz) JSON obyekt sifatida qaytar:\n{schema_txt}"
    )
    body_messages = _messages_from_history(msgs)
    try:
        parsed = _openai_compatible_call(base_url, key, model, sys_full, body_messages, 600)
    except json.JSONDecodeError:
        parsed = _openai_compatible_call(base_url, key, model, sys_full, body_messages, 1200)
    if not isinstance(parsed, dict):
        raise ValueError('parsed natija dict emas')
    _validate_against_schema(parsed, schema)
    return parsed


def _gemini_structured(key, model, system, msgs, schema):
    from google import genai
    from google.genai import types
    prompt = "\n".join(
        f"{'Mijoz' if m['role'] == 'user' else 'Yordamchi'}: {m['content']}"
        for m in _messages_from_history(msgs)
    )
    client = genai.Client(api_key=key)
    cfg = types.GenerateContentConfig(
        system_instruction=system or None,
        response_mime_type='application/json',
        response_json_schema=schema,
    )
    resp = client.models.generate_content(model=model, contents=prompt, config=cfg)
    parsed = json.loads(resp.text)
    if not isinstance(parsed, dict):
        raise ValueError('parsed natija dict emas')
    _validate_against_schema(parsed, schema)
    return parsed


def generate_structured_via_free_key(provider, base_url, model, key, system, msgs, schema):
    """Bitta xom kalit (`key`) bilan strukturali javob so'raydi.
    Muvaffaqiyatsiz bo'lsa Exception ko'taradi (chaqiruvchi navbatdagi
    kalitga o'tadi).

    2026-07-18: `base_url` ANIQ berilgan bo'lsa (masalan tashqi manbadan
    olingan tayyor ro'yxat — Google AI Studio OpenAI-mos shim, DashScope,
    GitHub Models va h.k.) — provayder nomidan qat'iy nazar HAR DOIM
    generic OpenAI-mos yo'l ishlatiladi (admin nima bergan bo'lsa, shunga
    ishoniladi)."""
    model = (model or '').strip()
    if not model:
        raise RuntimeError('model nomi aniqlanmagan')
    if base_url:
        return _openai_compatible_structured(base_url.rstrip('/'), key, model, system, msgs, schema)
    if provider == 'gemini':
        return _gemini_structured(key, model, system, msgs, schema)
    _base = _PROVIDER_BASE_URL.get(provider)
    if not _base:
        raise RuntimeError(f"noma'lum provayder ({provider}), base_url ham berilmagan")
    return _openai_compatible_structured(_base, key, model, system, msgs, schema)


def try_free_keys(system, msgs, schema, user=None):
    """Faol ('is_active') tekin provayder qatorlarini PRIORITY tartibida,
    har qatorning `keys` ro'yxatidagi kalitlarni esa RO'YXAT TARTIBIDA
    sinaydi — bitta kalit limit tugasa (yoki yaroqsiz bo'lsa), navbatdagi
    kalit (xuddi shu yoki keyingi qatordan) avtomatik sinaladi.

    Muvaffaqiyatli bo'lsa parsed dict (+ _ai_meta) qaytaradi, aks holda
    (yoki hech qanday faol/ishlaydigan kalit bo'lmasa) None — chaqiruvchi
    o'z asosiy (Anthropic->OR->Gemini) zanjiriga o'zgarishsiz davom etadi.
    Bu funksiya HECH QACHON Exception ko'tarmaydi."""
    try:
        from .models import FreeApiKey, ApiUsageLog
        rows = list(FreeApiKey.objects.filter(is_active=True).order_by('priority', 'id'))
    except Exception as e:  # noqa: BLE001
        logger.warning("FreeApiKey ro'yxatini o'qishda xato: %s", e)
        return None

    from django.utils import timezone
    for row in rows:
        entries = row.keys or []
        row_changed = False
        for entry in entries:
            if entry.get('status') not in ('valid', 'unknown'):
                continue  # invalid/rate_limited — keyingi tekshiruvgacha o'tkazib yuboriladi
            key_str = entry.get('key', '')
            if not key_str:
                continue
            try:
                import time
                start_time = time.time()
                parsed = generate_structured_via_free_key(
                    row.provider, row.base_url, row.model_name, key_str, system, msgs, schema)
                response_time = int((time.time() - start_time) * 1000)
                
                entry['status'] = 'valid'
                entry['last_checked_at'] = timezone.now().isoformat()
                entry['last_error'] = ''
                entry['use_count'] = int(entry.get('use_count') or 0) + 1
                entry['last_used_at'] = timezone.now().isoformat()
                row.keys = entries
                row.save(using=row._state.db or 'default', update_fields=['keys'])
                
                # Usage log yaratish
                try:
                    ApiUsageLog.objects.create(
                        api_key=row,
                        user=user,
                        action='use',
                        status='valid',
                        provider=row.provider,
                        model=row.model_name,
                        response_time_ms=response_time,
                    )
                except Exception:  # noqa: BLE001
                    pass  # Log yaratish xatosi asosiy funksiyaga ta'sir qilmasin
                
                parsed['_ai_meta'] = {
                    'provider': f'{row.provider}-free', 'model': row.model_name,
                    'cost_usd': '0', 'free_key_name': row.name,
                }
                logger.info("Tekin kalit ishlatildi: %s (%s/%s)", row.name, row.provider, row.model_name)
                return parsed
            except Exception as e:  # noqa: BLE001
                logger.warning("Tekin kalit xato (%s/%s): %s — navbatdagisi sinaladi",
                               row.name, row.provider, e)
                _msg = str(e).lower()
                entry['status'] = 'rate_limited' if ('429' in _msg or 'rate' in _msg or 'quota' in _msg) else 'invalid'
                entry['last_error'] = str(e)[:500]
                entry['last_checked_at'] = timezone.now().isoformat()
                row_changed = True
                
                # Error log yaratish
                try:
                    ApiUsageLog.objects.create(
                        api_key=row,
                        user=user,
                        action='use',
                        status=entry['status'],
                        provider=row.provider,
                        model=row.model_name,
                        error_message=str(e)[:500],
                    )
                except Exception:  # noqa: BLE001
                    pass
        if row_changed:
            try:
                row.keys = entries
                row.save(using=row._state.db or 'default', update_fields=['keys'])
            except Exception:  # noqa: BLE001
                pass
    return None
