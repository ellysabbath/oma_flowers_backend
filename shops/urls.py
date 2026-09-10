from django.urls import path
from .views import ShopListView, ShopDetailView
urlpatterns = [
    path('', ShopListView.as_view(), name='shop-list'),
    
    path('<int:id>/', ShopDetailView.as_view(), name='shop-detail'),
]