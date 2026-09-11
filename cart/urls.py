# cart/urls.py
from django.urls import path
from .views import (
    cart_list_create,
    cart_detail,
    cart_by_code,          # 👈 NEW
    cart_items_list_create,
    cart_item_detail,
    cart_clear,
    cart_checkout,
)

urlpatterns = [
    # ------------------------------
    # Static paths MUST come first
    # ------------------------------
    path('', cart_list_create, name='cart-list-create'),

    # 👇 New — lookup by code (string)
    path('by-code/<str:code>/', cart_by_code, name='cart-by-code'),

    # ------------------------------
    # Parameterized paths
    # ------------------------------
    path('<int:pk>/', cart_detail, name='cart-detail'),
    path('<int:cart_id>/items/', cart_items_list_create, name='cart-items'),
    path('<int:cart_id>/items/<int:item_id>/', cart_item_detail, name='cart-item-detail'),
    path('<int:cart_id>/clear/', cart_clear, name='cart-clear'),
    path('<int:cart_id>/checkout/', cart_checkout, name='cart-checkout'),
]