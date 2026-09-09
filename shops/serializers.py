from rest_framework import serializers
from distributors.serializers import DistributorSerializer
from .models import Shop

class ShopSerializer(serializers.ModelSerializer):
    distributor_name = serializers.SerializerMethodField()
    performance_display = serializers.SerializerMethodField()
    
    class Meta:
        model = Shop
        fields = (
            'id', 'distributor', 'distributor_name', 'name', 'location',
            'region', 'country', 'phone', 'email', 'performance_level',
            'performance_display', 'monthly_revenue', 'bonus_percentage',
            'customers', 'rating', 'status', 'established_date', 'created_at'
        )
    
    def get_distributor_name(self, obj):
        if obj.distributor:
            return obj.distributor.user.full_name
        return None
    
    def get_performance_display(self, obj):
        return obj.get_performance_level_display()

class ShopCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Shop
        fields = '__all__'