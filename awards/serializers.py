from rest_framework import serializers
from .models import Award

class AwardSerializer(serializers.ModelSerializer):
    distributor_name = serializers.CharField(source='distributor.user.full_name', read_only=True)
    
    class Meta:
        model = Award
        fields = (
            'id', 'distributor', 'distributor_name', 'name', 'category',
            'prize', 'description', 'year', 'status', 'given_date', 'created_at'
        )