from django.db import models
from django.contrib.auth.models import User


class SocialPlatform(models.Model):
    """Tizim qo'llab-quvvatlaydigan ijtimoiy tarmoq turi"""
    slug = models.SlugField(unique=True, verbose_name="Platforma kodi")
    name = models.CharField(max_length=100, verbose_name="Nomi")
    logo = models.CharField(max_length=255, blank=True, default='', verbose_name="Logo ikonka (CSS class yoki emoji)")
    is_active = models.BooleanField(default=True, verbose_name="Faol")

    class Meta:
        verbose_name = "Ijtimoiy tarmoq"
        verbose_name_plural = "Ijtimoiy tarmoqlar"
        ordering = ['name']

    def __str__(self):
        return self.name


class SocialAccount(models.Model):
    """Foydalanuvchi ulagan aniq akkaunt/kanal/bot"""
    STATUS_CHOICES = [
        ('active', 'Faol'),
        ('paused', 'Pauza'),
        ('error', 'Xato'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='social_accounts', verbose_name="Foydalanuvchi")
    platform = models.ForeignKey(SocialPlatform, on_delete=models.CASCADE, verbose_name="Platforma")
    display_name = models.CharField(max_length=150, verbose_name="Ko'rinadigan nom")
    external_id = models.CharField(max_length=255, verbose_name="Tashqi ID (bot_id, page_id va h.k.)")
    
    # Bot token / access token (shifrlangan holda saqlanadi)
    access_token = models.TextField(verbose_name="Access token / Bot token")
    webhook_secret = models.CharField(max_length=255, blank=True, default='', verbose_name="Webhook maxfiy so'zi")
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active', verbose_name="Holati")
    is_connected = models.BooleanField(default=False, verbose_name="Ulanganki?")
    connected_at = models.DateTimeField(auto_now_add=True, verbose_name="Ulangan vaqt")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Yangilangan vaqt")
    meta = models.JSONField(default=dict, blank=True, verbose_name="Qo'shimcha ma'lumot")

    class Meta:
        verbose_name = "Ijtimoiy akkaunt"
        verbose_name_plural = "Ijtimoiy akkauntlar"
        ordering = ['-connected_at']
        unique_together = [['user', 'platform', 'external_id']]

    def __str__(self):
        return f"{self.display_name} ({self.platform.name})"
