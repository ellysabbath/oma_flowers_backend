# distributors/serializers.py
from rest_framework import serializers
from users.serializers import UserSerializer
from users.models import User
from .models import Distributor


class DistributorSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    full_name = serializers.CharField(source='user.full_name', read_only=True)

    downline_count = serializers.SerializerMethodField()
    active_downline_count = serializers.SerializerMethodField()

    class Meta:
        model = Distributor
        fields = (
            'id', 'user', 'full_name', 'rank', 'level',
            'pbv', 'cgv', 'bonus_percentage', 'join_date',
            'downline_count', 'active_downline_count',
            'created_at', 'updated_at',
        )

    def get_downline_count(self, obj):
        if hasattr(obj, '_downline_count'):
            return obj._downline_count
        return obj.downline_members.count()

    def get_active_downline_count(self, obj):
        if hasattr(obj, '_active_downline_count'):
            return obj._active_downline_count
        return obj.downline_members.filter(user__status='active').count()


class DistributorCreateSerializer(serializers.ModelSerializer):
    user_id = serializers.IntegerField(
        write_only=True, required=False, allow_null=True
    )
    upline_id = serializers.IntegerField(
        write_only=True, required=False, allow_null=True
    )

    class Meta:
        model = Distributor
        fields = (
            'id', 'user_id', 'rank', 'level', 'pbv', 'cgv',
            'bonus_percentage', 'upline_id',
        )
        extra_kwargs = {
            'rank': {'required': False, 'default': 'Associate'},
            'level': {'required': False, 'default': 1},
            'pbv': {'required': False, 'default': 0},
            'cgv': {'required': False, 'default': 0},
            'bonus_percentage': {'required': False, 'default': 4.00},
        }

    def validate_user_id(self, value):
        """Reject if this user is already a distributor."""
        if value is None:
            return value
        if Distributor.objects.filter(user_id=value).exists():
            raise serializers.ValidationError(
                'This user is already a distributor.'
            )
        return value

    def create(self, validated_data):
        user_id = validated_data.pop('user_id')
        upline_id = validated_data.pop('upline_id', None)

        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            raise serializers.ValidationError(
                {'user_id': 'User not found.'}
            )

        if Distributor.objects.filter(user=user).exists():
            raise serializers.ValidationError(
                {'user_id': 'This user is already a distributor.'}
            )

        upline = None
        if upline_id:
            try:
                upline = Distributor.objects.get(id=upline_id)
            except Distributor.DoesNotExist:
                raise serializers.ValidationError(
                    {'upline_id': 'Upline distributor not found.'}
                )

        # Promote the user to distributor
        if user.user_type != 'distributor':
            user.user_type = 'distributor'
            user.save(update_fields=['user_type'])

        new_dist = Distributor.objects.create(
            user=user,
            upline=upline,
            rank=validated_data.get('rank', 'Associate'),
            level=validated_data.get('level', 1),
            pbv=validated_data.get('pbv', 0),
            cgv=validated_data.get('cgv', 0),
            bonus_percentage=validated_data.get('bonus_percentage', 4.00),
        )

        # Recompute upline's CGV chain now that a new member joined
        if new_dist.upline:
            new_dist.upline.cgv = new_dist.upline.compute_cgv()
            new_dist.upline.save(update_fields=['cgv'])
            new_dist.refresh_ancestors_cgv()

        return new_dist

    def update(self, instance, validated_data):
        # Capture old upline BEFORE any change
        old_upline = instance.upline

        validated_data.pop('user_id', None)

        instance.rank = validated_data.get('rank', instance.rank)
        instance.level = validated_data.get('level', instance.level)
        instance.pbv = validated_data.get('pbv', instance.pbv)
        instance.cgv = validated_data.get('cgv', instance.cgv)
        instance.bonus_percentage = validated_data.get(
            'bonus_percentage', instance.bonus_percentage
        )

        upline_id = validated_data.get('upline_id')
        if upline_id is not None:
            if upline_id == instance.id:
                raise serializers.ValidationError(
                    {'upline_id': 'A distributor cannot be their own upline.'}
                )
            try:
                instance.upline = (
                    Distributor.objects.get(id=upline_id)
                    if upline_id else None
                )
            except Distributor.DoesNotExist:
                raise serializers.ValidationError(
                    {'upline_id': 'Upline distributor not found.'}
                )

        instance.save()

        # Recompute both old and new upline CGV chains
        seen_ids = set()
        for up in (old_upline, instance.upline):
            if up and up.pk not in seen_ids:
                seen_ids.add(up.pk)
                up.cgv = up.compute_cgv()
                up.save(update_fields=['cgv'])
                up.refresh_ancestors_cgv()

        return instance


class DistributorHierarchySerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    downline = serializers.SerializerMethodField()

    downline_count = serializers.SerializerMethodField()
    active_downline_count = serializers.SerializerMethodField()

    class Meta:
        model = Distributor
        fields = (
            'id', 'user', 'rank', 'level', 'pbv', 'cgv',
            'bonus_percentage',
            'downline_count', 'active_downline_count',
            'downline',
        )

    def get_downline(self, obj):
        return DistributorHierarchySerializer(
            obj.downline_members.select_related('user').all(),
            many=True,
        ).data

    def get_downline_count(self, obj):
        return obj.downline_members.count()

    def get_active_downline_count(self, obj):
        return obj.downline_members.filter(user__status='active').count()


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