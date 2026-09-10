# cart/urls.py
from django.urls import path
from . import views

app_name = 'cart'

urlpatterns = [
    # Carts
    path('', views.cart_list_create, name='cart-list-create'),
    path('<int:pk>/', views.cart_detail, name='cart-detail'),
    path('<int:cart_id>/clear/', views.cart_clear, name='cart-clear'),
    path('<int:cart_id>/checkout/', views.cart_checkout, name='cart-checkout'),

    # Cart items
    path('<int:cart_id>/items/', views.cart_items_list_create, name='cart-items'),
    path('<int:cart_id>/items/<int:item_id>/', views.cart_item_detail, name='cart-item-detail'),
]