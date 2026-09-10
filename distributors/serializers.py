# serializers.py

from rest_framework import serializers
from users.serializers import UserSerializer
from users.models import User
from .models import Distributor

class DistributorSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    full_name = serializers.SerializerMethodField()
    downline_count = serializers.IntegerField(read_only=True)
    active_downline_count = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = Distributor
        fields = (
            'id', 'user', 'full_name', 'rank', 'level', 'pbv', 'cgv',
            'bonus_percentage', 'join_date', 'downline_count',
            'active_downline_count', 'created_at'
        )
    
    def get_full_name(self, obj):
        return obj.user.full_name

class DistributorCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating/updating distributors
    """
    user_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)  # Changed to required=False
    upline_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    
    class Meta:
        model = Distributor
        fields = (
            'id', 'user_id', 'rank', 'level', 'pbv', 'cgv', 
            'bonus_percentage', 'upline_id'
        )
        extra_kwargs = {
            'rank': {'required': False, 'default': 'Associate'},
            'level': {'required': False, 'default': 1},
            'pbv': {'required': False, 'default': 0},
            'cgv': {'required': False, 'default': 0},
            'bonus_percentage': {'required': False, 'default': 4.00},
        }
    
    def create(self, validated_data):
        user_id = validated_data.pop('user_id')
        upline_id = validated_data.pop('upline_id', None)
        
        # Get the user
        user = User.objects.get(id=user_id)
        
        # Get upline if provided
        upline = None
        if upline_id:
            upline = Distributor.objects.get(id=upline_id)
        
        # Create distributor
        distributor = Distributor.objects.create(
            user=user,
            upline=upline,
            rank=validated_data.get('rank', 'Associate'),
            level=validated_data.get('level', 1),
            pbv=validated_data.get('pbv', 0),
            cgv=validated_data.get('cgv', 0),
            bonus_percentage=validated_data.get('bonus_percentage', 4.00),
        )
        
        return distributor
    
    def update(self, instance, validated_data):
        # Remove user_id if present (should not be updated)
        validated_data.pop('user_id', None)
        
        # Update distributor fields
        instance.rank = validated_data.get('rank', instance.rank)
        instance.level = validated_data.get('level', instance.level)
        instance.pbv = validated_data.get('pbv', instance.pbv)
        instance.cgv = validated_data.get('cgv', instance.cgv)
        instance.bonus_percentage = validated_data.get('bonus_percentage', instance.bonus_percentage)
        
        # Update upline if provided
        upline_id = validated_data.get('upline_id')
        if upline_id is not None:
            instance.upline = Distributor.objects.get(id=upline_id) if upline_id else None
        
        instance.save()
        return instance

class DistributorHierarchySerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    downline = serializers.SerializerMethodField()
    
    class Meta:
        model = Distributor
        fields = (
            'id', 'user', 'rank', 'level', 'pbv', 'cgv',
            'bonus_percentage', 'downline'
        )
    
    def get_downline(self, obj):
        return DistributorHierarchySerializer(
            obj.downline_members.select_related('user').all(),
            many=True
        ).data

class DistributorStatsSerializer(serializers.Serializer):
    total_orders = serializers.IntegerField()
    total_commission = serializers.DecimalField(max_digits=12, decimal_places=2)
    total_bonuses = serializers.DecimalField(max_digits=12, decimal_places=2)
    downline_count = serializers.IntegerField()
    active_downline = serializers.IntegerField()
    rank = serializers.CharField()
    pbv = serializers.DecimalField(max_digits=10, decimal_places=2)
    cgv = serializers.DecimalField(max_digits=12, decimal_places=2)
    growth_rate = serializers.DecimalField(max_digits=5, decimal_places=2)