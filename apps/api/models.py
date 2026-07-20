from django.db import models
from django.utils import timezone
from django.contrib.auth import get_user_model

User = get_user_model()

STATUS_CHOICES = [
    ('valid', "Ishlayapti"),
    ('invalid', "Yaroqsiz/xato"),
    ('rate_limited', "Limit tugagan"),
    ('unknown', "Tekshirilmagan"),
]


def new_key_entry(key_str: str) -> dict:
    """`FreeApiKey.keys` JSON ro'yxatidagi bitta element — har kalit
    o'zining holati/qolgan-kredit/vaqti bilan MUSTAQIL kuzatiladi (bir xil
    provayderning turli kalitlari turli vaqtda tugaydi)."""
    return {
        'key': key_str,
        'status': 'unknown',
        'remaining_credit': '',
        'remaining_time': '',
        'last_error': '',
        'last_checked_at': None,
        'last_used_at': None,
        'use_count': 0,
    }


class FreeApiKey(models.Model):
    """Tekin/bepul AI provayder konfiguratsiyasi — 2026-07-18 (foydalanuvchi
    so'rovi): BITTA provayder/model uchun BIR NECHTA kalit saqlanishi mumkin
    (`keys` JSON ro'yxati) — biri limit tugasa, navbatdagisi avtomatik
    sinaladi. Provayder/model/base_url QATOR darajasida (barcha kalitlar
    uchun umumiy), holat/kredit/vaqt esa HAR BIR kalit uchun alohida.

    instacore/chatplace_ai.py bu ro'yxatni Anthropic'dan OLDIN, priority
    tartibida (avval qator, so'ng qatordagi kalitlar ro'yxat tartibida)
    sinaydi."""

    PROVIDER_CHOICES = [
        ('openrouter', 'OpenRouter'),
        ('groq', 'Groq'),
        ('gemini', 'Google Gemini'),
        ('mistral', 'Mistral'),
        ('cerebras', 'Cerebras'),
        ('google_openai', 'Google AI Studio (OpenAI-mos)'),
        ('dashscope', 'Alibaba Cloud (DashScope)'),
        ('cohere', 'Cohere'),
        ('github_models', 'GitHub Models'),
        ('custom', "Boshqa (maxsus Base URL)"),
        ('', "Aniqlanmagan"),
    ]

    name = models.CharField(max_length=100, verbose_name="Nomi")
    purpose = models.TextField(blank=True, default='', verbose_name="Nima uchun ishlatiladi (izoh)")
    priority = models.PositiveIntegerField(default=100, verbose_name="Tartib (kichik raqam — avval sinaladi)")
    is_active = models.BooleanField(default=True, verbose_name="Faol")

    provider = models.CharField(max_length=20, choices=PROVIDER_CHOICES, blank=True, default='')
    base_url = models.CharField(
        max_length=255, blank=True, default='',
        verbose_name="Maxsus Base URL (OpenAI-mos /chat/completions; bo'sh "
                     "qoldirsa provayder kalitdan avtomatik aniqlanadi)")
    model_name = models.CharField(max_length=120, blank=True, default='', verbose_name="Model")

    keys = models.JSONField(default=list, blank=True, verbose_name="Kalitlar (har biri mustaqil holat bilan)")

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, 
                                   related_name='api_keys_created', verbose_name="Yaratdi")

    class Meta:
        ordering = ['priority', 'id']
        verbose_name = "Tekin API kalit"
        verbose_name_plural = "Tekin API kalitlari"
        indexes = [
            models.Index(fields=['priority', 'is_active']),
            models.Index(fields=['provider']),
        ]

    def __str__(self):
        return f"{self.name} ({self.provider or '?'}, {len(self.keys or [])} kalit)"

    def valid_keys_count(self):
        return sum(1 for e in (self.keys or []) if e.get('status') == 'valid')
    
    def total_use_count(self):
        return sum(e.get('use_count', 0) for e in (self.keys or []))


class ApiUsageLog(models.Model):
    """API kalitlaridan foydalanish tarixi va analytics"""
    api_key = models.ForeignKey(FreeApiKey, on_delete=models.CASCADE, related_name='usage_logs')
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='api_usage')
    
    action = models.CharField(max_length=50)  # 'check', 'use', 'error', etc.
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    provider = models.CharField(max_length=50, blank=True)
    model = models.CharField(max_length=120, blank=True)
    
    error_message = models.TextField(blank=True)
    response_time_ms = models.IntegerField(null=True, blank=True)
    
    created_at = models.DateTimeField(default=timezone.now)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = "API foydalanish logi"
        verbose_name_plural = "API foydalanish loglari"
        indexes = [
            models.Index(fields=['api_key', '-created_at']),
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['user', '-created_at']),
        ]
    
    def __str__(self):
        return f"{self.api_key.name} - {self.action} ({self.status})"


class ApiAnalytics(models.Model):
    """Kunlik analytics yig'indisi"""
    date = models.DateField()
    api_key = models.ForeignKey(FreeApiKey, on_delete=models.CASCADE, related_name='analytics')
    
    total_requests = models.IntegerField(default=0)
    successful_requests = models.IntegerField(default=0)
    failed_requests = models.IntegerField(default=0)
    rate_limited_requests = models.IntegerField(default=0)
    
    total_tokens_used = models.IntegerField(default=0)
    avg_response_time_ms = models.FloatField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-date']
        verbose_name = "API analytics"
        verbose_name_plural = "API analytics"
        unique_together = ['date', 'api_key']
        indexes = [
            models.Index(fields=['date', 'api_key']),
        ]
    
    def __str__(self):
        return f"{self.api_key.name} - {self.date}"
