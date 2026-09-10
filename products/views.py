# products/views.py
from django.shortcuts import render
from rest_framework import generics, status, permissions, filters
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db.models import Count, Q
from .models import Category, Product
from .serializers import (
    CategorySerializer, CategoryCreateSerializer,
    ProductSerializer, ProductCreateSerializer
)

# ==================== CATEGORY VIEWS ====================

class CategoryListView(generics.ListCreateAPIView):
    """
    List all categories or create a new category
    - AllowAny access - No authentication required
    - NO PAGINATION - Show all categories
    """
    queryset = Category.objects.annotate(product_count=Count('products')).all()
    permission_classes = [permissions.AllowAny]  # <-- Added AllowAny
    filter_backends = [filters.SearchFilter]
    search_fields = ['name', 'code', 'description']
    pagination_class = None
    
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return CategoryCreateSerializer
        return CategorySerializer
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by type if provided
        type_filter = self.request.query_params.get('type')
        if type_filter:
            queryset = queryset.filter(type=type_filter)
        
        # Filter by class_type if provided
        class_type = self.request.query_params.get('class_type')
        if class_type:
            queryset = queryset.filter(class_type=class_type)
        
        # Filter by status if provided
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        return queryset
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CategoryDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Retrieve, update or delete a category
    - AllowAny access - No authentication required
    """
    queryset = Category.objects.annotate(product_count=Count('products')).all()
    permission_classes = [permissions.AllowAny]  # <-- Added AllowAny
    lookup_field = 'id'
    
    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return CategoryCreateSerializer
        return CategorySerializer
    
    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        # Check if category has products
        if instance.products.exists():
            return Response(
                {'error': 'Cannot delete category with existing products. Move or delete products first.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        instance.delete()
        return Response({'message': 'Category deleted successfully'}, status=status.HTTP_200_OK)


# ==================== PRODUCT VIEWS ====================

class ProductListView(generics.ListCreateAPIView):
    """
    List all products or create a new product
    - AllowAny access - No authentication required
    - NO PAGINATION - Show all products
    """
    queryset = Product.objects.select_related('category').all()
    permission_classes = [permissions.AllowAny]  # <-- Added AllowAny
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'sku', 'category__name']
    ordering_fields = ['price', 'bv', 'sales', 'created_at']
    pagination_class = None
    
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return ProductCreateSerializer
        return ProductSerializer
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by category if provided
        category = self.request.query_params.get('category')
        if category:
            queryset = queryset.filter(category_id=category)
        
        # Filter by category type if provided
        category_type = self.request.query_params.get('category_type')
        if category_type:
            queryset = queryset.filter(category__type=category_type)
        
        # Filter by status if provided
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        return queryset
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ProductDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Retrieve, update or delete a product
    - AllowAny access - No authentication required
    """
    queryset = Product.objects.select_related('category').all()
    permission_classes = [permissions.AllowAny]  # <-- Added AllowAny
    lookup_field = 'id'
    
    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return ProductCreateSerializer
        return ProductSerializer
    
    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.delete()
        return Response({'message': 'Product deleted successfully'}, status=status.HTTP_200_OK)