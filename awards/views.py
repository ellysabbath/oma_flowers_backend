# awards/views.py
from rest_framework import generics, filters
from django_filters.rest_framework import DjangoFilterBackend

from .models import Award
from .serializers import AwardSerializer


class AwardListView(generics.ListAPIView):
    """
    GET /api/v1/awards/

    Auto-seeds awards from the OMA document on the first request.
    Filters:
      ?category=legacy_circle|legacy|annual|special
      ?status=active|past|upcoming
      ?distributor=<id>
      ?year=2026
      ?search=<name or email>
    """
    queryset = Award.objects.select_related('distributor__user').all()
    serializer_class = AwardSerializer
    permission_classes = []
    authentication_classes = []

    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['category', 'status', 'distributor', 'year']
    search_fields = ['name', 'distributor__user__email']

    def get_queryset(self):
        # Lazy auto-seed — idempotent
        try:
            Award.auto_seed()
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(
                'Auto-seeding awards failed: %s', e, exc_info=True
            )
        return super().get_queryset()


class AwardDetailView(generics.RetrieveUpdateAPIView):
    """
    GET    /api/v1/awards/<id>/   → retrieve
    PATCH  /api/v1/awards/<id>/   → update status / given_date
    """
    queryset = Award.objects.select_related('distributor__user').all()
    serializer_class = AwardSerializer
    permission_classes = []
    authentication_classes = []
    lookup_field = 'id'