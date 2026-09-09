from rest_framework import serializers
from products.serializers import ProductSerializer
from users.serializers import UserSerializer
from .models import Order, OrderItem

class OrderItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_sku = serializers.CharField(source='product.sku', read_only=True)
    subtotal = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    
    class Meta:
        model = OrderItem
        fields = (
            'id', 'product', 'product_name', 'product_sku', 'quantity',
            'price', 'bv', 'subtotal'
        )

class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    customer_name = serializers.CharField(source='customer.full_name', read_only=True)
    customer_email = serializers.CharField(source='customer.email', read_only=True)
    distributor_name = serializers.SerializerMethodField()
    
    class Meta:
        model = Order
        fields = (
            'id', 'order_number', 'customer', 'customer_name', 'customer_email',
            'distributor', 'distributor_name', 'total_amount', 'total_bv',
            'status', 'payment_status', 'shipping_address', 'delivery_date',
            'notes', 'order_date', 'items'
        )
    
    def get_distributor_name(self, obj):
        if obj.distributor:
            return obj.distributor.user.full_name
        return None

class OrderCreateSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True)
    
    class Meta:
        model = Order
        fields = (
            'customer', 'distributor', 'shipping_address', 'notes', 'items'
        )
    
    def create(self, validated_data):
        items_data = validated_data.pop('items')
        order = Order.objects.create(**validated_data)
        
        total_amount = 0
        total_bv = 0
        
        for item_data in items_data:
            product = item_data['product']
            price = item_data.get('price', product.effective_price)
            bv = item_data.get('bv', product.effective_bv)
            
            order_item = OrderItem.objects.create(
                order=order,
                product=product,
                quantity=item_data['quantity'],
                price=price,
                bv=bv
            )
            
            total_amount += price * item_data['quantity']
            total_bv += bv * item_data['quantity']
        
        order.total_amount = total_amount
        order.total_bv = total_bv
        order.save()
        
        return order