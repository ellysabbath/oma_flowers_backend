# cart/serializers.py
from rest_framework import serializers
from django.contrib.auth import get_user_model

from .models import Cart, CartItem
from products.models import Product
from distributors.models import Distributor
from shops.models import Shop

User = get_user_model()


# ---------- Mini nested serializers (read-only) ----------

class CartUserMiniSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'email', 'username', 'full_name']

    def get_full_name(self, obj):
        return obj.get_full_name() or obj.username


class CartDistributorMiniSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    email = serializers.SerializerMethodField()

    class Meta:
        model = Distributor
        fields = ['id', 'full_name', 'email', 'rank']

    def get_full_name(self, obj):
        return getattr(obj, 'full_name', '') or ''

    def get_email(self, obj):
        return obj.user.email if obj.user else ''


class CartShopMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = Shop
        fields = ['id', 'name', 'location', 'region', 'country']


# ---------- Cart item ----------

class CartItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_sku = serializers.CharField(source='product.sku', read_only=True)
    product_picture = serializers.CharField(
        source='product.product_picture', read_only=True
    )
    subtotal = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True
    )

    seller_id = serializers.IntegerField(
        source='product.seller.id', read_only=True, allow_null=True
    )
    seller_name = serializers.CharField(
        source='product.seller_name', read_only=True
    )
    seller_rank = serializers.CharField(
        source='product.seller.rank', read_only=True, allow_null=True
    )

    class Meta:
        model = CartItem
        fields = [
            'id', 'cart', 'product', 'product_name', 'product_sku',
            'product_picture', 'quantity', 'price', 'bv', 'subtotal',
            'seller_id', 'seller_name', 'seller_rank',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class CartItemWriteSerializer(serializers.Serializer):
    product = serializers.PrimaryKeyRelatedField(queryset=Product.objects.all())
    quantity = serializers.IntegerField(min_value=1)
    price = serializers.DecimalField(max_digits=12, decimal_places=2, required=False)
    bv = serializers.IntegerField(min_value=0, required=False)


# ---------- Cart read serializer ----------

class CartSerializer(serializers.ModelSerializer):
    user = CartUserMiniSerializer(read_only=True)
    distributor = CartDistributorMiniSerializer(read_only=True)
    shop = CartShopMiniSerializer(read_only=True)
    items = CartItemSerializer(many=True, read_only=True)

    subtotal = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    total_bv = serializers.IntegerField(read_only=True)
    total_items = serializers.IntegerField(read_only=True)

    class Meta:
        model = Cart
        fields = [
            'id', 'code',                            # 👈 NEW
            'user', 'distributor', 'shop', 'session_key',
            'status', 'notes',
            'items', 'subtotal', 'total_bv', 'total_items',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'code', 'created_at', 'updated_at']   # 👈 code is read-only


# ---------- Cart write serializer (create/update) ----------

class CartWriteSerializer(serializers.ModelSerializer):
    user_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        source='user',
        write_only=True,
        required=False,
        allow_null=True,
    )
    distributor_id = serializers.PrimaryKeyRelatedField(
        queryset=Distributor.objects.all(),
        source='distributor',
        write_only=True,
        required=False,
        allow_null=True,
    )
    shop_id = serializers.PrimaryKeyRelatedField(
        queryset=Shop.objects.all(),
        source='shop',
        write_only=True,
        required=False,
        allow_null=True,
    )

    class Meta:
        model = Cart
        fields = [
            'id', 'user_id', 'distributor_id', 'shop_id',
            'session_key', 'status', 'notes',
            # NOTE: `code` is intentionally NOT here — the model
            # generates it automatically on first save.
        ]
        read_only_fields = ['id']