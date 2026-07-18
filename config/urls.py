from django.contrib import admin
from django.urls import path, include
from django.conf import settings

urlpatterns = [
    path('admin/', admin.site.urls, name='admin'),
    path('', include('apps.base.urls')),
    path('api/', include('apps.api.urls')),
    path('telegram/telegram/', include('apps.telegram.telegram.urls')),
    path('telegram/bot/', include('apps.telegram.bot.urls')),
]


if settings.DEBUG:
    import debug_toolbar
    urlpatterns = [
        path('__debug__/', include(debug_toolbar.urls)),
    ] + urlpatterns
