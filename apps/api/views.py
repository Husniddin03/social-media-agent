"""
apps/api/views.py — REST API boshqaruv uchun DRF ViewSets va custom actions
"""
import logging
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .detector import check_custom_endpoint, detect_and_check
from .models import FreeApiKey, ApiUsageLog, ApiAnalytics, new_key_entry
from .serializers import (
    FreeApiKeySerializer, FreeApiKeyListSerializer,
    ApiUsageLogSerializer, ApiAnalyticsSerializer,
    KeyCheckSerializer, BulkActionSerializer
)

logger = logging.getLogger('apps.api.views')

# Ro'yxat sahifasi ochilganda, so'nggi tekshiruvdan shuncha soniya o'tgan
# bo'lsa — real-vaqt ma'lumot uchun avtomatik qayta tekshiriladi.
_AUTO_RECHECK_AFTER = 60


class IsStaffUser(permissions.BasePermission):
    """Faqat staff userlar ruxsat beriladi"""
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_staff


def _mask(key_str):
    """Kalitni niqoblash uchun yordamchi funksiya"""
    key_str = key_str or ''
    return (key_str[:6] + '…' + key_str[-4:]) if len(key_str) > 12 else key_str


def _row_is_stale(row, now):
    """Qator eskirganligini tekshirish"""
    entries = row.keys or []
    if not entries:
        return False
    for e in entries:
        lc = e.get('last_checked_at')
        if not lc:
            return True
        dt = parse_datetime(lc) if isinstance(lc, str) else None
        if not dt or (now - dt).total_seconds() > _AUTO_RECHECK_AFTER:
            return True
    return False


def _recheck_row(row, save=True):
    """Qatorni qayta tekshirish"""
    now_iso = timezone.now().isoformat()
    entries = row.keys or []
    for entry in entries:
        key_str = entry.get('key', '')
        if not key_str:
            continue
        if row.base_url:
            result = check_custom_endpoint(row.base_url, key_str, row.model_name)
        else:
            result = detect_and_check(key_str)
            if result.get('provider') and not row.provider:
                row.provider = result['provider']
            if result.get('model_name') and not row.model_name:
                row.model_name = result['model_name']
        entry['status'] = result['status']
        entry['remaining_credit'] = result['remaining_credit']
        entry['remaining_time'] = result['remaining_time']
        entry['last_error'] = result['last_error']
        entry['last_checked_at'] = now_iso
    row.keys = entries
    if save:
        row.save(using=row._state.db or 'default')
    return row


class FreeApiKeyViewSet(viewsets.ModelViewSet):
    """FreeApiKey model uchun ViewSet"""
    permission_classes = [IsStaffUser]
    
    def get_serializer_class(self):
        if self.action == 'list':
            return FreeApiKeyListSerializer
        return FreeApiKeySerializer
    
    def get_queryset(self):
        queryset = FreeApiKey.objects.all()
        provider = self.request.query_params.get('provider')
        is_active = self.request.query_params.get('is_active')
        
        if provider:
            queryset = queryset.filter(provider=provider)
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        
        return queryset
    
    def list(self, request, *args, **kwargs):
        """Ro'yxat — real-vaqt ma'lumot uchun eskirgan kalitlar avtomatik qayta tekshiriladi"""
        queryset = self.filter_queryset(self.get_queryset())
        rows = list(queryset)
        now = timezone.now()
        
        for row in rows:
            if _row_is_stale(row, now):
                try:
                    _recheck_row(row)
                except Exception as e:
                    logger.warning('Avto-tekshiruv xato (id=%s): %s', row.id, e)
        
        serializer = self.get_serializer(rows, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def check(self, request, pk=None):
        """Shu qatordagi BARCHA kalitlarni QO'LDA qayta tekshirish"""
        try:
            row = self.get_object()
            _recheck_row(row)
            serializer = self.get_serializer(row)
            return Response(serializer.data)
        except Exception as e:
            return Response(
                {'error': str(e)[:300]}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def remove_key(self, request, pk=None):
        """Qatordagi BITTA kalitni (index bo'yicha) o'chiradi"""
        row = self.get_object()
        key_index = request.data.get('key_index')
        
        if key_index is None:
            return Response(
                {'error': 'key_index majburiy'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        entries = row.keys or []
        try:
            key_index = int(key_index)
        except (ValueError, TypeError):
            return Response(
                {'error': 'key_index noto\'g\'ri'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not (0 <= key_index < len(entries)):
            return Response(
                {'error': 'key_index noto\'g\'ri'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        entries.pop(key_index)
        row.keys = entries
        row.save(update_fields=['keys'])
        
        serializer = self.get_serializer(row)
        return Response(serializer.data)
    
    @action(detail=False, methods=['post'])
    def bulk_action(self, request):
        """Ommaviy amallar: activate, deactivate, delete, check"""
        serializer = BulkActionSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        ids = serializer.validated_data['ids']
        action_type = serializer.validated_data['action']
        
        queryset = FreeApiKey.objects.filter(id__in=ids)
        
        if action_type == 'activate':
            queryset.update(is_active=True)
        elif action_type == 'deactivate':
            queryset.update(is_active=False)
        elif action_type == 'delete':
            count, _ = queryset.delete()
            return Response({'deleted': count})
        elif action_type == 'check':
            for row in queryset:
                try:
                    _recheck_row(row)
                except Exception as e:
                    logger.warning('Bulk check xato (id=%s): %s', row.id, e)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['post'])
    def detect_provider(self, request):
        """Xom kalitdan provayderni aniqlash"""
        serializer = KeyCheckSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        key = serializer.validated_data['key']
        base_url = serializer.validated_data.get('base_url', '')
        
        if base_url:
            result = check_custom_endpoint(
                base_url, 
                key, 
                serializer.validated_data.get('model_name', '')
            )
        else:
            result = detect_and_check(key)
        
        return Response(result)


class ApiUsageLogViewSet(viewsets.ReadOnlyModelViewSet):
    """API foydalanish loglari uchun ViewSet"""
    serializer_class = ApiUsageLogSerializer
    permission_classes = [IsStaffUser]
    
    def get_queryset(self):
        queryset = ApiUsageLog.objects.all()
        api_key_id = self.request.query_params.get('api_key')
        user_id = self.request.query_params.get('user')
        status_filter = self.request.query_params.get('status')
        
        if api_key_id:
            queryset = queryset.filter(api_key_id=api_key_id)
        if user_id:
            queryset = queryset.filter(user_id=user_id)
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        return queryset.select_related('api_key', 'user')


class ApiAnalyticsViewSet(viewsets.ReadOnlyModelViewSet):
    """Analytics uchun ViewSet"""
    serializer_class = ApiAnalyticsSerializer
    permission_classes = [IsStaffUser]
    
    def get_queryset(self):
        queryset = ApiAnalytics.objects.all()
        api_key_id = self.request.query_params.get('api_key')
        date_from = self.request.query_params.get('date_from')
        date_to = self.request.query_params.get('date_to')
        
        if api_key_id:
            queryset = queryset.filter(api_key_id=api_key_id)
        if date_from:
            queryset = queryset.filter(date__gte=date_from)
        if date_to:
            queryset = queryset.filter(date__lte=date_to)
        
        return queryset.select_related('api_key')
    
    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Umumiy analytics xulosasi"""
        queryset = self.get_queryset()
        
        total_requests = sum(obj.total_requests for obj in queryset)
        successful_requests = sum(obj.successful_requests for obj in queryset)
        failed_requests = sum(obj.failed_requests for obj in queryset)
        total_tokens = sum(obj.total_tokens_used for obj in queryset)
        
        if total_requests > 0:
            success_rate = round((successful_requests / total_requests) * 100, 2)
        else:
            success_rate = 0
        
        return Response({
            'total_requests': total_requests,
            'successful_requests': successful_requests,
            'failed_requests': failed_requests,
            'success_rate': success_rate,
            'total_tokens_used': total_tokens,
            'period_count': queryset.count()
        })
