from rest_framework import serializers
from .models import Bonus

class BonusSerializer(serializers.ModelSerializer):
    distributor_name = serializers.CharField(source='distributor.user.full_name', read_only=True)
    
    class Meta:
        model = Bonus
        fields = (
            'id', 'distributor', 'distributor_name', 'name', 'type',
            'amount', 'description', 'month', 'year', 'status',
            'payment_date', 'created_at'
        )