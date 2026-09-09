from rest_framework import serializers
from distributors.serializers import DistributorSerializer
from orders.serializers import OrderSerializer
from .models import Commission

class CommissionSerializer(serializers.ModelSerializer):
    distributor_name = serializers.CharField(source='distributor.user.full_name', read_only=True)
    order_number = serializers.CharField(source='order.order_number', read_only=True)
    source_distributor_name = serializers.SerializerMethodField()
    
    class Meta:
        model = Commission
        fields = (
            'id', 'distributor', 'distributor_name', 'order', 'order_number',
            'type', 'source_distributor', 'source_distributor_name',
            'percentage', 'amount', 'status', 'payment_date', 'created_at'
        )
    
    def get_source_distributor_name(self, obj):
        if obj.source_distributor:
            return obj.source_distributor.user.full_name
        return None