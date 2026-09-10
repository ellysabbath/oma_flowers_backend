from django.urls import path
from . import views

app_name = 'orders'

urlpatterns = [
    # List + Create
    path('', views.order_list_create, name='order-list-create'),

    # Retrieve + Update + Delete
    path('<int:pk>/', views.order_detail, name='order-detail'),

    # Status update helper
    path('<int:pk>/status/', views.order_update_status, name='order-update-status'),
]