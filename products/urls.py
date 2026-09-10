# products/urls.py
from django.urls import path
from .views import (
    CategoryListView, CategoryDetailView,
    ProductListView, ProductDetailView
)

urlpatterns = [
    # Category URLs
    path('categories/', CategoryListView.as_view(), name='category-list'),
    path('categories/<int:id>/', CategoryDetailView.as_view(), name='category-detail'),
    
    # Product URLs
    path('products/', ProductListView.as_view(), name='product-list'),
    path('products/<int:id>/', ProductDetailView.as_view(), name='product-detail'),
]