from django.urls import path
from .views import (
    DistributorListView,
    DistributorDetailView,
    DistributorHierarchyView,
    DistributorStatsView,
    MyHierarchyView,
    remove_downline,
)

urlpatterns = [
    # List + create
    path('', DistributorListView.as_view(), name='distributor-list'),

    # ⚠️ Fixed-path routes MUST come before <int:id> routes,
    #    otherwise Django tries to interpret "me" as an integer.
    path(
        'me/hierarchy/',
        MyHierarchyView.as_view(),
        name='my-hierarchy',
    ),
    path(
        'stats/',
        DistributorStatsView.as_view(),
        name='distributor-stats',
    ),

    # Remove a direct downline
    path(
        '<int:distributor_id>/remove-downline/',
        remove_downline,
        name='remove-downline',
    ),

    # Hierarchy by id
    path(
        '<int:id>/hierarchy/',
        DistributorHierarchyView.as_view(),
        name='distributor-hierarchy',
    ),

    # Detail (keep last so it doesn't shadow specific routes)
    path(
        '<int:id>/',
        DistributorDetailView.as_view(),
        name='distributor-detail',
    ),
]