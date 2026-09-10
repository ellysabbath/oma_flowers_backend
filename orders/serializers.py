from rest_framework import serializers
from django.contrib.auth import get_user_model

from .models import Order, OrderItem
from products.models import Product
from distributors.models import Distributor

User = get_user_model()


# ---------- Nested read serializers ----------

class CustomerSerializer(serializers.ModelSerializer):
    """Read-only representation of the customer user."""
    full_name = serializers.SerializerMethodField()
    mobile_number = serializers.SerializerMethodField()
    country = serializers.SerializerMethodField()
    region = serializers.SerializerMethodField()
    city = serializers.SerializerMethodField()
    street = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email',
            'full_name', 'mobile_number',
            'country', 'region', 'city', 'street',
        ]

    def get_full_name(self, obj):
        return obj.get_full_name() or obj.username

    def get_mobile_number(self, obj):
        return getattr(obj, 'mobile_number', '') or getattr(obj, 'phone', '') or ''

    def get_country(self, obj):
        return getattr(obj, 'country', '') or ''

    def get_region(self, obj):
        return getattr(obj, 'region', '') or ''

    def get_city(self, obj):
        return getattr(obj, 'city', '') or ''

    def get_street(self, obj):
        return getattr(obj, 'street', '') or ''


class DistributorMiniSerializer(serializers.ModelSerializer):
    """Minimal distributor info for nested output."""
    full_name = serializers.SerializerMethodField()
    email = serializers.SerializerMethodField()

    class Meta:
        model = Distributor
        fields = ['id', 'full_name', 'email', 'rank']

    def get_full_name(self, obj):
        return getattr(obj, 'full_name', '') or ''

    def get_email(self, obj):
        user = getattr(obj, 'user', None)
        return getattr(user, 'email', '') if user else ''


class OrderItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_sku = serializers.CharField(source='product.sku', read_only=True)
    subtotal = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True
    )

    class Meta:
        model = OrderItem
        fields = [
            'id', 'product', 'product_name', 'product_sku',
            'quantity', 'price', 'bv', 'subtotal',
        ]


# ---------- Write serializer ----------

class OrderItemWriteSerializer(serializers.Serializer):
    product = serializers.PrimaryKeyRelatedField(queryset=Product.objects.all())
    quantity = serializers.IntegerField(min_value=1)
    price = serializers.DecimalField(max_digits=12, decimal_places=2, required=False)
    bv = serializers.IntegerField(min_value=0, required=False)


class OrderSerializer(serializers.ModelSerializer):
    # Read representation
    customer = CustomerSerializer(read_only=True)
    distributor = DistributorMiniSerializer(read_only=True)
    items = OrderItemSerializer(many=True, read_only=True)

    # Write fields
    customer_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        source='customer',
        write_only=True,
    )
    distributor_id = serializers.PrimaryKeyRelatedField(
        queryset=Distributor.objects.all(),
        source='distributor',
        write_only=True,
        required=False,
        allow_null=True,
    )
    items_data = OrderItemWriteSerializer(
        many=True, write_only=True, required=True
    )

    customer_name = serializers.SerializerMethodField(read_only=True)
    customer_email = serializers.SerializerMethodField(read_only=True)
    distributor_name = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Order
        fields = [
            'id', 'order_number',
            'customer', 'customer_id', 'customer_name', 'customer_email',
            'distributor', 'distributor_id', 'distributor_name',
            'total_amount', 'total_bv',
            'status', 'payment_status',
            'shipping_address', 'delivery_date', 'notes',
            'order_date', 'updated_at',
            'items', 'items_data',
        ]
        read_only_fields = ['id', 'order_date', 'updated_at']

    def get_customer_name(self, obj):
        return obj.customer.get_full_name() or obj.customer.username

    def get_customer_email(self, obj):
        return obj.customer.email

    def get_distributor_name(self, obj):
        if not obj.distributor:
            return None
        return getattr(obj.distributor, 'full_name', None) or str(obj.distributor)

    # ---------- create ----------
    def create(self, validated_data):
        items_data = validated_data.pop('items_data', [])
        customer = validated_data.get('customer')

        # auto-generate order number if missing
        if not validated_data.get('order_number'):
            import uuid
            validated_data['order_number'] = f"ORD-{uuid.uuid4().hex[:10].upper()}"

        # compute totals from items
        total_amount = 0
        total_bv = 0
        for item in items_data:
            product = item['product']
            qty = item['quantity']
            price = item.get('price', product.effective_price)
            bv = item.get('bv', product.effective_bv)
            total_amount += float(price) * qty
            total_bv += int(bv) * qty

        validated_data['total_amount'] = total_amount
        validated_data['total_bv'] = total_bv

        order = Order.objects.create(**validated_data)

        for item in items_data:
            product = item['product']
            qty = item['quantity']
            price = item.get('price', product.effective_price)
            bv = item.get('bv', product.effective_bv)
            OrderItem.objects.create(
                order=order,
                product=product,
                quantity=qty,
                price=price,
                bv=bv,
            )
        return order

    # ---------- update ----------
    def update(self, instance, validated_data):
        items_data = validated_data.pop('items_data', None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        if items_data is not None:
            instance.items.all().delete()
            total_amount = 0
            total_bv = 0
            for item in items_data:
                product = item['product']
                qty = item['quantity']
                price = item.get('price', product.effective_price)
                bv = item.get('bv', product.effective_bv)
                OrderItem.objects.create(
                    order=instance,
                    product=product,
                    quantity=qty,
                    price=price,
                    bv=bv,
                )
                total_amount += float(price) * qty
                total_bv += int(bv) * qty
            instance.total_amount = total_amount
            instance.total_bv = total_bv

        instance.save()
        return instance