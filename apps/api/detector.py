"""
free_api_key/detector.py — 2026-07-18 (foydalanuvchi so'rovi): xom API kalit
satridan qaysi tekin AI provayderga tegishli ekanini avtomatik aniqlash +
real-vaqtda holat/qolgan-kredit/qolgan-vaqt ma'lumotini olish.

Har provayder uchun alohida "probe" — birinchi muvaffaqiyatli javob provayder
sifatida qabul qilinadi. Provayderlarning HAMMASI ham "qolgan kredit/vaqt"
APIsini oshkor qilmaydi (masalan Gemini/Mistral/Cerebras'da bunday endpoint
yo'q) — bunday holda aniq "noma'lum" deb ko'rsatiladi, hech qachon
o'ylab-topilmaydi.
"""
import logging

import requests

logger = logging.getLogger('apps.api')

_TIMEOUT = 10
_DEFAULT_OR_FREE_MODEL = 'meta-llama/llama-3.3-70b-instruct:free'


def _pick_openrouter_free_model():
    try:
        r = requests.get('https://openrouter.ai/api/v1/models', timeout=_TIMEOUT)
        if r.status_code == 200:
            for m in (r.json() or {}).get('data', []):
                mid = m.get('id', '')
                pricing = m.get('pricing', {}) or {}
                if mid.endswith(':free') and str(pricing.get('prompt')) in ('0', '0.0'):
                    return mid
    except Exception as e:  # noqa: BLE001
        logger.debug('OpenRouter bepul model ro\'yxatini olishda xato: %s', e)
    return _DEFAULT_OR_FREE_MODEL


def _probe_openrouter(key):
    r = requests.get('https://openrouter.ai/api/v1/auth/key',
                     headers={'Authorization': f'Bearer {key}'}, timeout=_TIMEOUT)
    if r.status_code != 200:
        return None
    data = (r.json() or {}).get('data', {}) or {}
    limit = data.get('limit')
    remaining = data.get('limit_remaining')
    usage = data.get('usage') or 0
    if limit is None:
        credit_txt = f"Cheksiz (${usage:.4f} sarflangan)"
    else:
        credit_txt = f"${remaining:.4f} qoldi (limit ${limit})"
    rl = data.get('rate_limit') or {}
    time_txt = (f"Har {rl.get('interval')} da {rl.get('requests')} so'rov limiti"
               if rl else "Cheksiz (kredit tugagunча amal qiladi)")
    return {
        'provider': 'openrouter', 'model_name': _pick_openrouter_free_model(),
        'status': 'valid', 'remaining_credit': credit_txt,
        'remaining_time': time_txt, 'last_error': '',
    }


def _probe_groq(key):
    r = requests.get('https://api.groq.com/openai/v1/models',
                     headers={'Authorization': f'Bearer {key}'}, timeout=_TIMEOUT)
    if r.status_code != 200:
        return None
    models = [m.get('id', '') for m in (r.json() or {}).get('data', [])]
    model = 'llama-3.3-70b-versatile' if 'llama-3.3-70b-versatile' in models else (models[0] if models else 'llama-3.3-70b-versatile')
    credit_txt, time_txt = "Noma'lum (birinchi haqiqiy so'rovda aniqlanadi)", "Noma'lum"
    try:
        rc = requests.post(
            'https://api.groq.com/openai/v1/chat/completions',
            headers={'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'},
            json={'model': model, 'messages': [{'role': 'user', 'content': 'hi'}], 'max_tokens': 1},
            timeout=_TIMEOUT,
        )
        h = rc.headers
        rem_t, lim_t, reset_t = (h.get('x-ratelimit-remaining-tokens'),
                                 h.get('x-ratelimit-limit-tokens'),
                                 h.get('x-ratelimit-reset-tokens'))
        if rem_t and lim_t:
            credit_txt = f"{rem_t}/{lim_t} token qoldi (kunlik)"
        if reset_t:
            time_txt = f"{reset_t} dan keyin to'liq tiklanadi"
    except Exception as e:  # noqa: BLE001
        logger.debug('Groq rate-limit header o\'qishda xato: %s', e)
    return {
        'provider': 'groq', 'model_name': model, 'status': 'valid',
        'remaining_credit': credit_txt, 'remaining_time': time_txt, 'last_error': '',
    }


def _probe_gemini(key):
    r = requests.get('https://generativelanguage.googleapis.com/v1beta/models',
                     params={'key': key}, timeout=_TIMEOUT)
    if r.status_code != 200:
        return None
    models = [m.get('name', '').replace('models/', '') for m in (r.json() or {}).get('models', [])]
    model = 'gemini-2.5-flash' if 'gemini-2.5-flash' in models else (models[0] if models else 'gemini-2.5-flash')
    return {
        'provider': 'gemini', 'model_name': model, 'status': 'valid',
        'remaining_credit': "Google taqdim etmaydi (kunlik so'rov limiti bor, sonini ko'rsatmaydi)",
        'remaining_time': "Noma'lum (kuniga avtomatik tiklanadi)", 'last_error': '',
    }


def _probe_openai_compat(base_url, provider_key, default_model, key):
    r = requests.get(f'{base_url}/models',
                     headers={'Authorization': f'Bearer {key}'}, timeout=_TIMEOUT)
    if r.status_code != 200:
        return None
    models = [m.get('id', '') for m in (r.json() or {}).get('data', [])]
    model = default_model if default_model in models else (models[0] if models else default_model)
    return {
        'provider': provider_key, 'model_name': model, 'status': 'valid',
        'remaining_credit': "Noma'lum (bu provayder balans APIsini oshkor qilmaydi)",
        'remaining_time': "Noma'lum", 'last_error': '',
    }


_PROBES = [
    ('openrouter', _probe_openrouter),
    ('groq', _probe_groq),
    ('gemini', _probe_gemini),
    ('mistral', lambda key: _probe_openai_compat('https://api.mistral.ai/v1', 'mistral', 'mistral-small-latest', key)),
    ('cerebras', lambda key: _probe_openai_compat('https://api.cerebras.ai/v1', 'cerebras', 'llama3.1-8b', key)),
]


def check_custom_endpoint(base_url: str, key: str, model: str) -> dict:
    """2026-07-18: admin BAZA'ni (provider/model/base_url) allaqachon bilgan
    holatlar uchun (masalan tashqi manbadan olingan tayyor ro'yxat) — ko'r-
    ko'rona provayder-taxmin qilinmaydi, aynan berilgan `base_url`+`model`ga
    REAL ulanish sinaladi. Natija: status/remaining_*/last_error —
    provider/model_name O'ZGARTIRILMAYDI (admin kiritgani saqlanadi).

    2026-07-18 (real bug — birinchi jonli sinovda aniqlandi, DashScope):
    avval FAQAT `GET /models` (200 bo'lsa 'valid') tekshirilardi — bu FAQAT
    kalitning umuman haqiqiyligini ko'rsatadi, ANIQ KO'RSATILGAN MODEL
    ishlashini EMAS. Natijada bir provayder "valid" ko'rinib turdi, lekin
    haqiqiy chat so'rovi 403 "AccessDenied.Unpurchased" bilan muvaffaqiyatsiz
    bo'lardi (model account'da faollashtirilmagan). Endi ANIQ `model` bilan
    minimal chat so'rovi ASOSIY tekshiruv — bu haqiqatan ham ISHLATILADIGAN
    narsani sinaydi. `GET /models` faqat model berilmagan holatlar uchun
    zaxira sifatida qoladi."""
    base_url = (base_url or '').rstrip('/')
    key = (key or '').strip()
    if not base_url or not key:
        return {'status': 'invalid', 'remaining_credit': '', 'remaining_time': '',
               'last_error': "base_url yoki kalit bo'sh"}
    if model:
        try:
            rc = requests.post(
                f'{base_url}/chat/completions',
                headers={'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'},
                json={'model': model, 'messages': [{'role': 'user', 'content': 'hi'}], 'max_tokens': 1},
                timeout=_TIMEOUT,
            )
            if rc.status_code < 400:
                return {'status': 'valid', 'remaining_credit': "Noma'lum (maxsus ulanish)",
                       'remaining_time': "Noma'lum", 'last_error': ''}
            _status = 'rate_limited' if rc.status_code == 429 else 'invalid'
            return {'status': _status, 'remaining_credit': '', 'remaining_time': '',
                   'last_error': f'POST /chat/completions {rc.status_code}: {rc.text[:300]}'}
        except Exception as e:  # noqa: BLE001
            return {'status': 'invalid', 'remaining_credit': '', 'remaining_time': '',
                   'last_error': f'POST /chat/completions xato: {e}'}
    # model berilmagan — kamida kalitning haqiqiyligini GET /models bilan sinash
    try:
        r = requests.get(f'{base_url}/models',
                         headers={'Authorization': f'Bearer {key}'}, timeout=_TIMEOUT)
        if r.status_code == 200:
            return {'status': 'valid', 'remaining_credit': "Noma'lum (maxsus ulanish)",
                   'remaining_time': "Noma'lum", 'last_error': ''}
        return {'status': 'invalid', 'remaining_credit': '', 'remaining_time': '',
               'last_error': f'GET /models {r.status_code}: {r.text[:200]}'}
    except Exception as e:  # noqa: BLE001
        return {'status': 'invalid', 'remaining_credit': '', 'remaining_time': '',
               'last_error': f'GET /models xato: {e}'}


def detect_and_check(key: str) -> dict:
    """Xom kalitni ma'lum provayderlar bo'yicha ketma-ket sinaydi (har biri
    mustaqil — biri xato bersa, keyingisi baribir sinaladi). Birinchi
    muvaffaqiyatli javob provayder sifatida qaytadi. Hech biri mos kelmasa
    — status='invalid' + sabab (barcha probe xatolari qisqartirilib)."""
    key = (key or '').strip()
    if not key:
        return {'provider': '', 'model_name': '', 'status': 'invalid',
               'remaining_credit': '', 'remaining_time': '', 'last_error': "Kalit bo'sh"}
    errors = []
    for name, probe in _PROBES:
        try:
            result = probe(key)
            if result:
                return result
        except Exception as e:  # noqa: BLE001
            errors.append(f'{name}: {e}')
            logger.debug('Probe %s xato: %s', name, e)
    return {
        'provider': '', 'model_name': '', 'status': 'invalid',
        'remaining_credit': '', 'remaining_time': '',
        'last_error': ('Hech qaysi provayderga mos kelmadi: ' + '; '.join(errors))[:500],
    }
