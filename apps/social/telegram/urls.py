from django.urls import path
from . import views

app_name = 'social_telegram'

urlpatterns = [
    # Webhook endpoint (Telegram dan keladigan update'lar)
    path('webhook/<int:account_id>/', views.webhook, name='webhook'),
    
    # Webhook o'rnatish (admin uchun)
    path('set-webhook/', views.set_webhook, name='set_webhook'),
    
    # Webhook holatini tekshirish
    path('webhook-info/', views.webhook_info, name='webhook_info'),
]
