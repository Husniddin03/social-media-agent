from django.contrib import admin
from django.utils.html import format_html

from .models import FreeApiKey, ApiUsageLog, ApiAnalytics


@admin.register(FreeApiKey)
class FreeApiKeyAdmin(admin.ModelAdmin):
    list_display = ['name', 'provider', 'model_name', 'priority', 'is_active', 'keys_count', 'total_use_count', 'created_by']
    list_filter = ['provider', 'is_active', 'created_at']
    search_fields = ['name', 'purpose', 'base_url']
    readonly_fields = ['created_at', 'updated_at', 'created_by']
    fieldsets = (
        ('Asosiy ma\'lumotlar', {
            'fields': ('name', 'purpose', 'priority', 'is_active', 'created_by')
        }),
        ('API konfiguratsiyasi', {
            'fields': ('provider', 'base_url', 'model_name')
        }),
        ('Kalitlar', {
            'fields': ('keys',)
        }),
        ('Vaqt ma\'lumotlari', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def keys_count(self, obj):
        valid = obj.valid_keys_count()
        total = len(obj.keys or [])
        color = 'green' if valid > 0 else 'red'
        return format_html(
            '<span style="color: {};">{}/{}</span>',
            color, valid, total
        )
    keys_count.short_description = "Kalitlar (ishlayapti/jami)"
    
    def total_use_count(self, obj):
        return obj.total_use_count()
    total_use_count.short_description = "Jami ishlatilgan"


@admin.register(ApiUsageLog)
class ApiUsageLogAdmin(admin.ModelAdmin):
    list_display = ['api_key', 'user', 'action', 'status', 'provider', 'model', 'response_time_ms', 'created_at']
    list_filter = ['status', 'action', 'provider', 'created_at']
    search_fields = ['api_key__name', 'user__username', 'error_message']
    readonly_fields = ['created_at']
    date_hierarchy = 'created_at'


@admin.register(ApiAnalytics)
class ApiAnalyticsAdmin(admin.ModelAdmin):
    list_display = ['api_key', 'date', 'total_requests', 'successful_requests', 'failed_requests', 'success_rate', 'total_tokens_used']
    list_filter = ['date']
    readonly_fields = ['created_at', 'updated_at']
    date_hierarchy = 'date'
    
    def success_rate(self, obj):
        if obj.total_requests == 0:
            return "0%"
        rate = (obj.successful_requests / obj.total_requests) * 100
        color = 'green' if rate >= 80 else 'orange' if rate >= 50 else 'red'
        return format_html(
            '<span style="color: {};">{:.1f}%</span>',
            color, rate
        )
    success_rate.short_description = "Muvaffaqiyat foizi"
