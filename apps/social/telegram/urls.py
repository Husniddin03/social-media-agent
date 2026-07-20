from django.urls import path
from . import views
from .. import dashboard_views

app_name = 'social_telegram'

urlpatterns = [
    # Webhook endpoint (Telegram dan keladigan update'lar)
    path('webhook/<int:account_id>/', views.webhook, name='webhook'),
    
    # Webhook o'rnatish (admin uchun)
    path('set-webhook/', views.set_webhook, name='set_webhook'),
    
    # Webhook holatini tekshirish
    path('webhook-info/', views.webhook_info, name='webhook_info'),
    
    # Dashboard — botlarni boshqarish
    path('dashboard/', dashboard_views.dashboard, name='dashboard'),
    path('dashboard/add-bot/', dashboard_views.add_bot, name='add_bot'),
    path('dashboard/bot/<int:account_id>/', dashboard_views.bot_settings, name='bot_settings'),
    path('dashboard/bot/<int:account_id>/update/', dashboard_views.update_agent_config, name='update_agent_config'),
    path('dashboard/bot/<int:account_id>/delete/', dashboard_views.delete_bot, name='delete_bot'),
    path('dashboard/bot/<int:account_id>/reconnect/', dashboard_views.reconnect_webhook, name='reconnect_webhook'),
    path('dashboard/bot/<int:account_id>/toggle/', dashboard_views.toggle_bot_status, name='toggle_bot_status'),
]
