from django.urls import path
from .views import ShopListView, ShopDetailView, ShopCreateView

urlpatterns = [
    path('', ShopListView.as_view(), name='shop-list'),
    path('create/', ShopCreateView.as_view(), name='shop-create'),
    path('<int:id>/', ShopDetailView.as_view(), name='shop-detail'),
]