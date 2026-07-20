from django.contrib import admin
from .models import SocialPlatform, SocialAccount


@admin.register(SocialPlatform)
class SocialPlatformAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'is_active']
    prepopulated_fields = {'slug': ('name',)}


@admin.register(SocialAccount)
class SocialAccountAdmin(admin.ModelAdmin):
    list_display = ['display_name', 'platform', 'user', 'status', 'is_connected', 'connected_at']
    list_filter = ['platform', 'status', 'is_connected']
    search_fields = ['display_name', 'external_id', 'user__username']
    readonly_fields = ['connected_at', 'updated_at']
