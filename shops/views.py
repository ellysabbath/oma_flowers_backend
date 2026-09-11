# shops/views.py
"""
OMA Flowers — Shop views.

CRUD for shops plus two recompute endpoints:

  POST /api/v1/shops/recompute-performance/
      Recompute every shop's owner_bv, customers, level, and bonus.

  POST /api/v1/shops/recompute-performance/<distributor_id>/
      Recompute all shops owned by a specific distributor.
"""

from rest_framework import generics, permissions, filters, status
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from django_filters.rest_framework import DjangoFilterBackend

from .models import Shop
from .serializers import ShopSerializer, ShopCreateSerializer


class ShopListView(generics.ListCreateAPIView):
    """
    GET  /api/v1/shops/  -> list all shops
    POST /api/v1/shops/  -> create shop
    """
    queryset = Shop.objects.select_related('distributor__user').all()
    permission_classes = [permissions.AllowAny]
    pagination_class = None
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ['performance_level', 'status']
    search_fields = ['name', 'location', 'region', 'distributor__user__email']
    ordering_fields = [
        'owner_bv', 'customers', 'monthly_revenue', 'rating', 'created_at',
    ]

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return ShopCreateSerializer
        return ShopSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            shop = serializer.save()
            # save() auto-computes owner_bv, customers, level, bonus
            return Response(
                ShopSerializer(shop).data,
                status=status.HTTP_201_CREATED,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ShopDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    GET/PUT/PATCH/DELETE /api/v1/shops/<id>/
    """
    queryset = Shop.objects.select_related('distributor__user').all()
    permission_classes = [permissions.AllowAny]
    lookup_field = 'id'

    def get_serializer_class(self):
        if self.request.method in ('PUT', 'PATCH'):
            return ShopCreateSerializer
        return ShopSerializer

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(
            instance, data=request.data, partial=partial
        )
        if serializer.is_valid():
            serializer.save()   # save() recomputes level from owner BV
            return Response(ShopSerializer(instance).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.delete()
        return Response(
            {'message': 'Shop deleted successfully'},
            status=status.HTTP_200_OK,
        )


# ------------------------------------------------------------------
# Recompute endpoints
# ------------------------------------------------------------------

@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def recompute_shop_performance(request):
    """
    POST /api/v1/shops/recompute-performance/

    Recompute owner_bv, customers, performance_level, and
    bonus_percentage for EVERY shop in the DB.
    """
    updated = Shop.recompute_all_performance()
    return Response({'detail': f'Recomputed {updated} shop(s).'})


@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def recompute_shops_for_distributor(request, distributor_id):
    """
    POST /api/v1/shops/recompute-performance/<distributor_id>/

    Recompute performance for all shops owned by a specific distributor.
    """
    updated = Shop.recompute_for_distributor(distributor_id)
    return Response({'detail': f'Recomputed {updated} shop(s).'})