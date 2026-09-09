from django.urls import path
from .views import (
    DistributorListView, DistributorDetailView,
    DistributorHierarchyView, DistributorStatsView
)

urlpatterns = [
    path('', DistributorListView.as_view(), name='distributor-list'),
    path('<int:id>/', DistributorDetailView.as_view(), name='distributor-detail'),
    path('<int:id>/hierarchy/', DistributorHierarchyView.as_view(), name='distributor-hierarchy'),
    path('stats/', DistributorStatsView.as_view(), name='distributor-stats'),
]