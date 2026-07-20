from django.urls import path
from . import views

app_name = 'base'

urlpatterns = [
    path('', views.index, name='index'),
    path('telegram/', views.telegram, name='telegram'),
    
    # Bot CRUD
    path('telegram/bots/', views.bot_list, name='bot_list'),
    path('telegram/bots/add/', views.bot_add, name='bot_add'),
    path('telegram/bots/<int:account_id>/', views.bot_settings, name='bot_settings'),
    path('telegram/bots/<int:account_id>/save/', views.bot_settings_save, name='bot_settings_save'),
    path('telegram/bots/<int:account_id>/delete/', views.bot_delete, name='bot_delete'),
    path('telegram/bots/<int:account_id>/toggle/', views.bot_toggle, name='bot_toggle'),
    path('telegram/bots/<int:account_id>/reconnect/', views.bot_reconnect, name='bot_reconnect'),
    
    # Chat (User Account) CRUD
    path('telegram/chats/', views.chat_list, name='chat_list'),
    path('telegram/chats/add/', views.chat_add, name='chat_add'),
    path('telegram/chats/<int:account_id>/verify/', views.chat_verify, name='chat_verify'),
    path('telegram/chats/<int:account_id>/', views.chat_settings, name='chat_settings'),
    path('telegram/chats/<int:account_id>/save/', views.chat_settings_save, name='chat_settings_save'),
    path('telegram/chats/<int:account_id>/delete/', views.chat_delete, name='chat_delete'),
    path('telegram/chats/<int:account_id>/toggle/', views.chat_toggle, name='chat_toggle'),
    
    # API Keys
    path('api-keys/', views.api_keys, name='api_keys'),
    path('api-keys/add/', views.api_key_add, name='api_key_add'),
    path('api-keys/<int:credential_id>/delete/', views.api_key_delete, name='api_key_delete'),
    path('api-keys/<int:credential_id>/validate/', views.api_key_validate, name='api_key_validate'),
]
