from urllib.parse import unquote

from rest_framework import serializers

from .models import EthosLog, EthosResource


class EthosResourceSerializer(serializers.ModelSerializer):
    application_name = serializers.CharField(source='application.name', read_only=True)
    methods = serializers.SerializerMethodField()
    representation_count = serializers.SerializerMethodField()
    preferred_accept = serializers.SerializerMethodField()
    detail_url = serializers.SerializerMethodField()

    class Meta:
        model = EthosResource
        fields = ['id', 'name', 'application_name', 'methods', 'representation_count', 'preferred_accept', 'detail_url']
        datatables_always_serialize = ['id', 'detail_url']

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

    def get_detail_url(self, obj):
        return f'/ce/ethos/resources/{obj.pk}/'


class EthosLogSerializer(serializers.ModelSerializer):
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
            'message_type', 'description', 'response_status', 'success',
        ]
        datatables_always_serialize = ['id']
