from urllib.parse import unquote

from rest_framework import serializers

from .models import EthosLog, EthosResource, EthosMessage
from .campus import has_no_campus


class NoCampusMixin(serializers.Serializer):
    """`no_campus`: a multi-campus row with no campus, which only superusers see (#14)."""
    no_campus = serializers.SerializerMethodField()
    def get_no_campus(self, obj):
        return has_no_campus(obj)


class EthosResourceSerializer(NoCampusMixin, serializers.ModelSerializer):
    application_name = serializers.CharField(source='application.name', read_only=True)
    methods = serializers.SerializerMethodField()
    representation_count = serializers.SerializerMethodField()
    preferred_accept = serializers.SerializerMethodField()
    detail_url = serializers.SerializerMethodField()

    class Meta:
        model = EthosResource
        fields = ['id', 'name', 'application_name', 'methods', 'representation_count', 'preferred_accept', 'detail_url', 'no_campus']
        datatables_always_serialize = ['id', 'detail_url', 'no_campus']

    def get_methods(self, obj):
        seen = set()
        result = []
        for rep in obj.representations.all():
            for m in (rep.methods or []):
                if m not in seen:
                    seen.add(m)
                    result.append(m)
        return result

    def get_representation_count(self, obj):
        return obj.representations.count()

    def get_preferred_accept(self, obj):
        if obj.preferred_representation_id:
            return obj.preferred_representation.x_media_type
        return None

    def get_no_campus(self, obj):
        return has_no_campus(obj.application) if obj.application_id else False

    def get_detail_url(self, obj):
        return f'/ce/ethos/resources/{obj.pk}/'


class EthosLogSerializer(NoCampusMixin, serializers.ModelSerializer):
    sent_on = serializers.DateTimeField(format='%Y-%m-%d %I:%M %p')
    success = serializers.BooleanField(read_only=True)
    path    = serializers.SerializerMethodField()
    url     = serializers.SerializerMethodField()

    def get_path(self, obj):
        return unquote(obj.path or '')

    def get_url(self, obj):
        return unquote(obj.url or '')

    class Meta:
        model = EthosLog
        fields = [
            'id', 'sent_on', 'method', 'path', 'url',
            'message_type', 'description', 'response_status', 'success', 'no_campus',
        ]
        datatables_always_serialize = ['id', 'no_campus']


class EthosMessageSerializer(NoCampusMixin, serializers.ModelSerializer):
    published_on = serializers.DateTimeField(format='%Y-%m-%d %I:%M %p', read_only=True)
    consumed_at  = serializers.DateTimeField(format='%Y-%m-%d %I:%M %p', read_only=True)
    status_reason = serializers.CharField(read_only=True)

    class Meta:
        model = EthosMessage
        fields = ['id', 'queue_id', 'published_on', 'resource_name', 'resource_id',
                  'operation', 'status_reason', 'status', 'action', 'consumed_at',
                  'target_label', 'no_campus']
        datatables_always_serialize = ['id', 'no_campus']
