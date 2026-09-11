# shops/urls.py
from django.urls import path

from .views import (
    ShopListView,
    ShopDetailView,
    recompute_shop_performance,
    recompute_shops_for_distributor,
)

urlpatterns = [
    # ------------------------------
    # Recompute endpoints (MUST come BEFORE <int:id>/)
    # ------------------------------
    path(
        'recompute-performance/',
        recompute_shop_performance,
        name='shop-recompute-performance',
    ),
    path(
        'recompute-performance/<int:distributor_id>/',
        recompute_shops_for_distributor,
        name='shop-recompute-performance-distributor',
    ),

    # ------------------------------
    # Standard CRUD
    # ------------------------------
    path('', ShopListView.as_view(), name='shop-list'),
    path('<int:id>/', ShopDetailView.as_view(), name='shop-detail'),
]