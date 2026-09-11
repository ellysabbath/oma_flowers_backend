# bonuses/serializers.py
from rest_framework import serializers
from .models import Bonus


class BonusSerializer(serializers.ModelSerializer):
    distributor_name = serializers.CharField(
        source='distributor.user.full_name', read_only=True
    )
    distributor_rank = serializers.CharField(
        source='distributor.rank', read_only=True
    )

    class Meta:
        model = Bonus
        fields = (
            'id', 'distributor', 'distributor_name', 'distributor_rank',
            'name', 'type',
            'amount', 'description', 'month', 'year',
            'status', 'payment_date',
            'created_at', 'updated_at',
        )
        read_only_fields = (
            'id', 'created_at', 'updated_at',
            'distributor', 'name', 'type',
            'amount', 'description', 'month', 'year',
        )