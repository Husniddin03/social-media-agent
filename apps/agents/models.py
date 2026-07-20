from django.db import models
from django.contrib.auth.models import User
from apps.social.models import SocialAccount
from apps.ai_providers.models import AIProviderCredential


class AgentConfig(models.Model):
    """Bitta SocialAccount uchun AI sozlamalari"""
    LANGUAGE_CHOICES = [
        ('auto', 'Avtomatik'),
        ('uz', "O'zbek"),
        ('ru', 'Rus'),
        ('en', 'Ingliz'),
    ]

    social_account = models.OneToOneField(
        SocialAccount, on_delete=models.CASCADE,
        related_name='agent_config', verbose_name="Ijtimoiy akkaunt"
    )
    ai_credential = models.ForeignKey(
        AIProviderCredential, on_delete=models.SET_NULL,
        null=True, blank=True, verbose_name="AI kaliti"
    )
    system_prompt = models.TextField(
        default=("Siz foydalanuvchilarga yordam beruvchi AI yordamchisiz. "
                 "Savollarga aniq, foydali va do'stona javob bering."),
        verbose_name="Tizim prompti"
    )
    tone = models.CharField(max_length=50, default="do'stona", verbose_name="Ohang")
    language_mode = models.CharField(
        max_length=10, choices=LANGUAGE_CHOICES, default='auto', verbose_name="Til rejimi"
    )
    max_response_length = models.PositiveIntegerField(default=1000, verbose_name="Maksimal javob uzunligi (belgi)")
    is_enabled = models.BooleanField(default=True, verbose_name="Agent faolmi?")
    fallback_to_human = models.BooleanField(default=True, verbose_name="AI ishlamasa odamga otkazish")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Yaratilgan vaqt")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Yangilangan vaqt")

    class Meta:
        verbose_name = "Agent sozlamasi"
        verbose_name_plural = "Agent sozlamalari"

    def __str__(self):
        return f"Agent: {self.social_account.display_name}"


class ConversationLog(models.Model):
    """Kiruvchi xabar va AI javobi tarixi"""
    STATUS_CHOICES = [
        ('sent', 'Yuborildi'),
        ('failed', 'Xato'),
        ('escalated', "Odamga otkazildi"),
    ]

    social_account = models.ForeignKey(
        SocialAccount, on_delete=models.CASCADE,
        related_name='logs', verbose_name="Ijtimoiy akkaunt"
    )
    external_user_id = models.CharField(
        max_length=255, verbose_name="Tashqi foydalanuvchi ID"
    )
    external_user_name = models.CharField(
        max_length=255, blank=True, default='', verbose_name="Tashqi foydalanuvchi nomi"
    )
    incoming_message = models.TextField(verbose_name="Kiruvchi xabar")
    ai_response = models.TextField(blank=True, default='', verbose_name="AI javobi")
    tokens_used = models.PositiveIntegerField(default=0, verbose_name="Ishlatilgan tokenlar")
    response_time_ms = models.PositiveIntegerField(default=0, verbose_name="Javob vaqti (ms)")
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='sent', verbose_name="Holati"
    )
    error_message = models.TextField(blank=True, default='', verbose_name="Xato xabari")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Yaratilgan vaqt")

    class Meta:
        verbose_name = "Muloqot logi"
        verbose_name_plural = "Muloqot loglari"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['social_account', '-created_at']),
            models.Index(fields=['external_user_id']),
        ]

    def __str__(self):
        return f"{self.social_account.display_name} - {self.external_user_name or self.external_user_id}"


class UsageStats(models.Model):
    """Kunlik foydalanish statistikasi"""
    social_account = models.ForeignKey(
        SocialAccount, on_delete=models.CASCADE,
        related_name='stats', verbose_name="Ijtimoiy akkaunt"
    )
    date = models.DateField(verbose_name="Sana")
    messages_count = models.PositiveIntegerField(default=0, verbose_name="Xabarlar soni")
    tokens_used = models.PositiveIntegerField(default=0, verbose_name="Tokenlar")

    class Meta:
        verbose_name = "Foydalanish statistikasi"
        verbose_name_plural = "Foydalanish statistikasi"
        ordering = ['-date']
        unique_together = ['social_account', 'date']

    def __str__(self):
        return f"{self.social_account.display_name} - {self.date}"
