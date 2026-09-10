from rest_framework import serializers
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
            'customers', 'rating', 'status', 'established_date',
            'created_at', 'updated_at',
        )

    def get_distributor_name(self, obj):
        if not obj.distributor:
            return None
        # Prefer distributor.full_name, fall back to user.full_name
        return (
            getattr(obj.distributor, 'full_name', None)
            or (obj.distributor.user.full_name if obj.distributor.user else None)
        )

    def get_performance_display(self, obj):
        return obj.get_performance_level_display()


class ShopCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Shop
        fields = (
            'id', 'distributor', 'name', 'location', 'region', 'country',
            'phone', 'email', 'performance_level', 'monthly_revenue',
            'bonus_percentage', 'customers', 'rating', 'status',
            'established_date',
        )
        extra_kwargs = {
            'distributor': {'required': False, 'allow_null': True},
            'email': {'required': False, 'allow_null': True, 'allow_blank': True},
            'rating': {'required': False},
            'bonus_percentage': {'required': False},
            'monthly_revenue': {'required': False},
            'customers': {'required': False},
        }