# products/serializers.py
from rest_framework import serializers
from .models import Category, Product


# ==================== CATEGORY ====================

class CategorySerializer(serializers.ModelSerializer):
    product_count = serializers.IntegerField(read_only=True)
    class_type_display = serializers.CharField(
        source='get_class_type_display', read_only=True
    )

    class Meta:
        model = Category
        fields = (
            'id', 'name', 'code', 'description',
            'type', 'class_type', 'class_type_display',
            'bv', 'price', 'status', 'product_count',
            'created_at', 'updated_at',
        )
        read_only_fields = ('id', 'created_at', 'updated_at')


class CategoryCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = (
            'id', 'name', 'code', 'description',
            'type', 'class_type', 'bv', 'price', 'status',
        )
        extra_kwargs = {
            'name': {'required': True},
            'code': {'required': True},
            'type': {'required': True},
            'class_type': {'required': True},
            'bv': {'required': True},
            'price': {'required': True},
        }

    def validate_code(self, value):
        value = value.upper()
        if Category.objects.filter(code=value).exists():
            if self.instance and self.instance.code == value:
                return value
            raise serializers.ValidationError(
                'Category with this code already exists.'
            )
        return value

    def validate_name(self, value):
        if Category.objects.filter(name=value).exists():
            if self.instance and self.instance.name == value:
                return value
            raise serializers.ValidationError(
                'Category with this name already exists.'
            )
        return value


# ==================== PRODUCT ====================

class ProductSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    category_code = serializers.CharField(source='category.code', read_only=True)
    category_type = serializers.CharField(source='category.type', read_only=True)
    category_class_type = serializers.CharField(
        source='category.class_type', read_only=True
    )
    effective_price = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True
    )
    effective_bv = serializers.IntegerField(read_only=True)

    # 👇 NEW — seller info for display
    seller_name = serializers.SerializerMethodField()
    seller_rank = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = (
            'id', 'category',
            'category_name', 'category_code',
            'category_type', 'category_class_type',
            'seller', 'seller_name', 'seller_rank',          # 👈 NEW
            'sku', 'name', 'description',
            'price', 'bv', 'effective_price', 'effective_bv',
            'stock', 'sales', 'status', 'product_picture',
            'created_at', 'updated_at',
        )
        read_only_fields = ('id', 'created_at', 'updated_at')

    def get_seller_name(self, obj):
        if not obj.seller:
            return None
        # Prefer distributor.full_name, fall back to user.full_name / username / email
        return (
            getattr(obj.seller, 'full_name', None)
            or getattr(obj.seller.user, 'full_name', None)
            or getattr(obj.seller.user, 'username', None)
            or getattr(obj.seller.user, 'email', None)
        )

    def get_seller_rank(self, obj):
        return obj.seller.rank if obj.seller else None


class ProductCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = (
            'id',
            'category',
            'seller',                                         # 👈 MUST be here
            'sku', 'name', 'description',
            'price', 'bv', 'stock', 'status', 'product_picture',
        )
        extra_kwargs = {
            'category': {'required': True},
            'seller': {'required': False, 'allow_null': True},  # 👈 NEW
            'sku': {'required': False, 'allow_blank': True},
            'name': {'required': True},
            'price': {'required': False, 'allow_null': True},
            'bv': {'required': False, 'allow_null': True},
            'product_picture': {
                'required': False, 'allow_null': True, 'allow_blank': True,
            },
        }

    def create(self, validated_data):
        # If the caller didn't provide a SKU, generate one
        if not validated_data.get('sku'):
            validated_data['sku'] = self._generate_sku(
                validated_data['category']
            )
        return super().create(validated_data)

    def update(self, instance, validated_data):
        # Do NOT regenerate SKU on update unless explicitly changed
        if not validated_data.get('sku'):
            validated_data.pop('sku', None)
        return super().update(instance, validated_data)

    def _generate_sku(self, category):
        """
        Compose a SKU like CCA-0001, CCA-0002, ... per category.
        """
        from django.db import transaction
        import time

        prefix = category.code
        with transaction.atomic():
            existing = (
                Product.objects.select_for_update()
                .filter(category=category)
                .count()
            )
            next_num = existing + 1
            candidate = f"{prefix}-{next_num:04d}"

            while Product.objects.filter(sku=candidate).exists():
                next_num += 1
                candidate = f"{prefix}-{next_num:04d}"

            if next_num > existing + 1000:
                candidate = f"{prefix}-{int(time.time() * 1000)}"

            return candidate

    def validate_sku(self, value):
        if not value:
            return value
        value = value.upper()
        if Product.objects.filter(sku=value).exists():
            if self.instance and self.instance.sku == value:
                return value
            raise serializers.ValidationError(
                'Product with this SKU already exists.'
            )
        return value