from rest_framework import generics, permissions, filters, status
from rest_framework.response import Response
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
    pagination_class = None                          # <-- no pagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['performance_level', 'status']
    search_fields = ['name', 'location', 'region', 'distributor__user__email']
    ordering_fields = ['monthly_revenue', 'customers', 'rating', 'created_at']

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return ShopCreateSerializer
        return ShopSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            shop = serializer.save()
            # Re-serialize with the read serializer for the full response
            return Response(ShopSerializer(shop).data, status=status.HTTP_201_CREATED)
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
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        if serializer.is_valid():
            serializer.save()
            return Response(ShopSerializer(instance).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.delete()
        return Response({'message': 'Shop deleted successfully'}, status=status.HTTP_200_OK)