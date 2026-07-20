from django.urls import path, include
from django.shortcuts import redirect
from rest_framework.routers import DefaultRouter
from . import views

app_name = 'api'

# DRF ViewSets uchun router
router = DefaultRouter()
router.register(r'keys', views.FreeApiKeyViewSet, basename='freeapikey')
router.register(r'logs', views.ApiUsageLogViewSet, basename='apiusagelog')
router.register(r'analytics', views.ApiAnalyticsViewSet, basename='apianalytics')

urlpatterns = [
    # Eski frontend URL - yangi API Keys sahifasiga redirect
    path('', lambda req: redirect('base:api_keys'), name='manager'),
    
    # DRF API endpoints (ichki foydalanish uchun)
    path('api/', include(router.urls)),
]
