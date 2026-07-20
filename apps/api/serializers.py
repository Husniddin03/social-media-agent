from rest_framework import serializers
from .models import FreeApiKey, ApiUsageLog, ApiAnalytics, new_key_entry


class KeyEntrySerializer(serializers.Serializer):
    """JSON kalitlar ro'yxatidagi bitta element uchun serializer"""
    key = serializers.CharField()
    status = serializers.CharField(default='unknown')
    remaining_credit = serializers.CharField(default='')
    remaining_time = serializers.CharField(default='')
    last_error = serializers.CharField(default='')
    last_checked_at = serializers.DateTimeField(allow_null=True, required=False)
    last_used_at = serializers.DateTimeField(allow_null=True, required=False)
    use_count = serializers.IntegerField(default=0)


class FreeApiKeySerializer(serializers.ModelSerializer):
    """FreeApiKey model uchun asosiy serializer"""
    keys = KeyEntrySerializer(many=True, required=False)
    keys_summary = serializers.CharField(read_only=True)
    provider_display = serializers.CharField(source='get_provider_display', read_only=True)
    valid_keys_count = serializers.IntegerField(read_only=True)
    total_use_count = serializers.IntegerField(read_only=True)
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)
    
    class Meta:
        model = FreeApiKey
        fields = [
            'id', 'name', 'purpose', 'priority', 'is_active',
            'provider', 'provider_display', 'base_url', 'model_name',
            'keys', 'keys_summary', 'valid_keys_count', 'total_use_count',
            'created_at', 'updated_at', 'created_by', 'created_by_name'
        ]
        read_only_fields = ['created_at', 'updated_at', 'created_by']
    
    def create(self, validated_data):
        keys_data = validated_data.pop('keys', [])
        # Kalitlarni xom stringlar ro'yxati sifatida qabul qilish
        if isinstance(keys_data, list) and keys_data and isinstance(keys_data[0], str):
            keys_entries = [new_key_entry(key) for key in keys_data if key.strip()]
        else:
            keys_entries = keys_data
        
        validated_data['keys'] = keys_entries
        validated_data['created_by'] = self.context['request'].user
        return super().create(validated_data)
    
    def update(self, instance, validated_data):
        keys_data = validated_data.pop('keys', None)
        
        if keys_data is not None:
            # Yangi kalitlarni qo'shish (mavjudlarni o'zgartirmasdan)
            if isinstance(keys_data, list) and keys_data:
                if isinstance(keys_data[0], str):
                    # Xom stringlar ro'yxati
                    existing_keys = {entry.get('key') for entry in (instance.keys or [])}
                    new_entries = []
                    for key in keys_data:
                        key = key.strip()
                        if key and key not in existing_keys:
                            new_entries.append(new_key_entry(key))
                    instance.keys = (instance.keys or []) + new_entries
                else:
                    # To'liq key entry obyektlari
                    instance.keys = keys_data
        
        # Boshqa maydonlarni yangilash
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        instance.save()
        return instance


class FreeApiKeyListSerializer(serializers.ModelSerializer):
    """Ro'yxat uchun qisqaroq serializer"""
    keys_summary = serializers.CharField(read_only=True)
    provider_display = serializers.CharField(source='get_provider_display', read_only=True)
    valid_keys_count = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = FreeApiKey
        fields = [
            'id', 'name', 'purpose', 'priority', 'is_active',
            'provider', 'provider_display', 'base_url', 'model_name',
            'keys_summary', 'valid_keys_count', 'created_at', 'updated_at'
        ]


class ApiUsageLogSerializer(serializers.ModelSerializer):
    """API foydalanish loglari uchun serializer"""
    api_key_name = serializers.CharField(source='api_key.name', read_only=True)
    user_name = serializers.CharField(source='user.username', read_only=True)
    
    class Meta:
        model = ApiUsageLog
        fields = [
            'id', 'api_key', 'api_key_name', 'user', 'user_name',
            'action', 'status', 'provider', 'model',
            'error_message', 'response_time_ms', 'created_at'
        ]
        read_only_fields = ['created_at']


class ApiAnalyticsSerializer(serializers.ModelSerializer):
    """Analytics uchun serializer"""
    api_key_name = serializers.CharField(source='api_key.name', read_only=True)
    success_rate = serializers.SerializerMethodField()
    
    class Meta:
        model = ApiAnalytics
        fields = [
            'id', 'date', 'api_key', 'api_key_name',
            'total_requests', 'successful_requests', 'failed_requests',
            'rate_limited_requests', 'total_tokens_used',
            'avg_response_time_ms', 'success_rate',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']
    
    def get_success_rate(self, obj):
        if obj.total_requests == 0:
            return 0
        return round((obj.successful_requests / obj.total_requests) * 100, 2)


class KeyCheckSerializer(serializers.Serializer):
    """Kalitni tekshirish uchun serializer"""
    key = serializers.CharField()
    provider = serializers.CharField(required=False, allow_blank=True)
    base_url = serializers.CharField(required=False, allow_blank=True)
    model_name = serializers.CharField(required=False, allow_blank=True)


class BulkActionSerializer(serializers.Serializer):
    """Ommaviy amallar uchun serializer"""
    ids = serializers.ListField(child=serializers.IntegerField())
    action = serializers.ChoiceField(['activate', 'deactivate', 'delete', 'check'])
