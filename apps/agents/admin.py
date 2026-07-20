from django.contrib import admin
from .models import AgentConfig, ConversationLog, UsageStats


@admin.register(AgentConfig)
class AgentConfigAdmin(admin.ModelAdmin):
    list_display = ['social_account', 'ai_credential', 'is_enabled', 'tone', 'language_mode']
    list_filter = ['is_enabled', 'tone', 'language_mode']
    search_fields = ['social_account__display_name']


@admin.register(ConversationLog)
class ConversationLogAdmin(admin.ModelAdmin):
    list_display = ['social_account', 'external_user_name', 'status', 'tokens_used', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['external_user_name', 'external_user_id', 'incoming_message']
    readonly_fields = ['created_at']


@admin.register(UsageStats)
class UsageStatsAdmin(admin.ModelAdmin):
    list_display = ['social_account', 'date', 'messages_count', 'tokens_used']
    list_filter = ['date']
