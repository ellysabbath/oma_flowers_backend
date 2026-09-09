from rest_framework import serializers
from .models import Category, Product

class CategorySerializer(serializers.ModelSerializer):
    product_count = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = Category
        fields = (
            'id', 'name', 'code', 'description', 'type', 'class_type',
            'bv', 'price', 'status', 'product_count', 'created_at'
        )

class ProductSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    category_code = serializers.CharField(source='category.code', read_only=True)
    effective_price = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    effective_bv = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = Product
        fields = (
            'id', 'category', 'category_name', 'category_code', 'sku', 'name',
            'description', 'price', 'bv', 'effective_price', 'effective_bv',
            'stock', 'sales', 'status', 'created_at'
        )