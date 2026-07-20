from django.db import models
from django.contrib.auth.models import User


class AIProvider(models.Model):
    """Tizim darajasida oldindan ro'yxatga olingan AI provayderlar"""
    slug = models.SlugField(unique=True, verbose_name="Provider kodi")
    name = models.CharField(max_length=100, verbose_name="Nomi")
    adapter_class_path = models.CharField(
        max_length=255, blank=True, default='',
        verbose_name="Adapter klass yo'li (masalan: apps.ai_providers.adapters.openai.OpenAIAdapter)"
    )
    is_free_tier_available = models.BooleanField(default=False, verbose_name="Tekin tier bormi?")
    default_base_url = models.URLField(blank=True, default='', verbose_name="Standart base URL")
    logo = models.CharField(max_length=255, blank=True, default='', verbose_name="Logo (emoji/CSS)")
    is_active = models.BooleanField(default=True, verbose_name="Faol")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "AI provayder"
        verbose_name_plural = "AI provayderlar"
        ordering = ['name']

    def __str__(self):
        return self.name


class AIProviderCredential(models.Model):
    """Foydalanuvchining shaxsiy AI API kaliti"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='ai_credentials', verbose_name="Foydalanuvchi")
    provider = models.ForeignKey(AIProvider, on_delete=models.CASCADE, verbose_name="Provayder")
    label = models.CharField(max_length=100, verbose_name="Label (masalan: Mening OpenAI kalitim)")
    api_key = models.TextField(verbose_name="API kalit")
    base_url_override = models.URLField(blank=True, default='', verbose_name="Base URL (ixtiyoriy)")
    model_name = models.CharField(max_length=100, verbose_name="Model nomi")
    extra_config = models.JSONField(default=dict, blank=True, verbose_name="Qo'shimcha sozlamalar (temperature va h.k.)")
    
    is_valid = models.BooleanField(default=True, verbose_name="Kalit ishlaydimi?")
    last_checked_at = models.DateTimeField(null=True, blank=True, verbose_name="Oxirgi tekshirilgan vaqt")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Yaratilgan vaqt")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Yangilangan vaqt")

    class Meta:
        verbose_name = "AI provayder kaliti"
        verbose_name_plural = "AI provayder kalitlari"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.label} ({self.provider.name})"
