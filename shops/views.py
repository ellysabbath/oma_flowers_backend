from django.shortcuts import render

# Create your views here.
from rest_framework import generics, permissions, filters
from django_filters.rest_framework import DjangoFilterBackend
from .models import Shop
from .serializers import ShopSerializer, ShopCreateSerializer

class ShopListView(generics.ListAPIView):
    queryset = Shop.objects.select_related('distributor__user').all()
    serializer_class = ShopSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['performance_level', 'status']
    search_fields = ['name', 'location', 'region']
    
    def get_queryset(self):
        queryset = super().get_queryset()
        # If user is a distributor, show only their shops
        if self.request.user.is_distributor():
            try:
                distributor = self.request.user.distributor_profile
                queryset = queryset.filter(distributor=distributor)
            except:
                queryset = queryset.none()
        return queryset

class ShopDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Shop.objects.select_related('distributor__user').all()
    serializer_class = ShopSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'id'

class ShopCreateView(generics.CreateAPIView):
    queryset = Shop.objects.all()
    serializer_class = ShopCreateSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def perform_create(self, serializer):
        # If user is a distributor, automatically assign them
        if self.request.user.is_distributor():
            distributor = self.request.user.distributor_profile
            serializer.save(distributor=distributor)
        else:
            serializer.save()