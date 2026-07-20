from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

app_name = 'api'

# DRF ViewSets uchun router
router = DefaultRouter()
router.register(r'keys', views.FreeApiKeyViewSet, basename='freeapikey')
router.register(r'logs', views.ApiUsageLogViewSet, basename='apiusagelog')
router.register(r'analytics', views.ApiAnalyticsViewSet, basename='apianalytics')

urlpatterns = [
    # Main frontend template
    path('', views.manager, name='manager'),
    
    # DRF API endpoints
    path('api/', include(router.urls)),
]
