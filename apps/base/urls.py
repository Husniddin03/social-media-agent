from django.urls import path
from . import views

app_name = 'base'

urlpatterns = [
    path('', views.index, name='index'),
    path('telegram/', views.telegram, name='telegram'),
    path('telegram/bots/', views.bot_list, name='bot_list'),
    path('telegram/bots/add/', views.bot_add, name='bot_add'),
    path('telegram/bots/<int:account_id>/', views.bot_settings, name='bot_settings'),
    path('telegram/bots/<int:account_id>/save/', views.bot_settings_save, name='bot_settings_save'),
    path('telegram/bots/<int:account_id>/delete/', views.bot_delete, name='bot_delete'),
    path('telegram/bots/<int:account_id>/toggle/', views.bot_toggle, name='bot_toggle'),
    path('telegram/bots/<int:account_id>/reconnect/', views.bot_reconnect, name='bot_reconnect'),
    path('api-keys/', views.api_keys, name='api_keys'),
    path('api-keys/add/', views.api_key_add, name='api_key_add'),
    path('api-keys/<int:credential_id>/delete/', views.api_key_delete, name='api_key_delete'),
    path('api-keys/<int:credential_id>/validate/', views.api_key_validate, name='api_key_validate'),
]
