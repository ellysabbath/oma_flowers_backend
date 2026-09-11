# commissions/serializers.py
from rest_framework import serializers
from .models import Commission


class CommissionSerializer(serializers.ModelSerializer):
    distributor_name = serializers.CharField(
        source='distributor.user.full_name', read_only=True
    )
    distributor_rank = serializers.CharField(
        source='distributor.rank', read_only=True
    )
    distributor_level = serializers.IntegerField(
        source='distributor.level', read_only=True
    )
    order_number = serializers.SerializerMethodField()
    source_distributor_name = serializers.SerializerMethodField()

    class Meta:
        model = Commission
        fields = (
            'id',
            'distributor', 'distributor_name',
            'distributor_rank', 'distributor_level',
            'order', 'order_number',
            'type',
            'source_distributor', 'source_distributor_name',
            'pbv',
            'percentage', 'amount',
            'status', 'payment_date',
            'created_at', 'updated_at',
        )
        read_only_fields = (
            'id', 'created_at', 'updated_at',
            'distributor', 'order', 'type',
            'source_distributor', 'pbv',
            'percentage', 'amount',
        )

    def get_order_number(self, obj):
        if obj.order:
            return getattr(obj.order, 'order_number', None)
        return None

    def get_source_distributor_name(self, obj):
        if obj.source_distributor:
            return obj.source_distributor.user.full_name
        return None