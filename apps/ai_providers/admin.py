from django.contrib import admin
from .models import AIProvider, AIProviderCredential


@admin.register(AIProvider)
class AIProviderAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'is_free_tier_available', 'is_active']
    prepopulated_fields = {'slug': ('name',)}


@admin.register(AIProviderCredential)
class AIProviderCredentialAdmin(admin.ModelAdmin):
    list_display = ['label', 'user', 'provider', 'model_name', 'is_valid', 'created_at']
    list_filter = ['provider', 'is_valid']
    search_fields = ['label', 'user__username']
    readonly_fields = ['created_at', 'updated_at', 'last_checked_at']
