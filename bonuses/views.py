from django.shortcuts import render

# Create your views here.
from rest_framework import generics, permissions, filters
from django_filters.rest_framework import DjangoFilterBackend
from .models import Bonus
from .serializers import BonusSerializer

class BonusListView(generics.ListAPIView):
    queryset = Bonus.objects.select_related('distributor__user').all()
    serializer_class = BonusSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['type', 'status', 'distributor', 'year', 'month']
    search_fields = ['name', 'distributor__user__email']
    
    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        
        if user.is_admin():
            return queryset
        
        if user.is_distributor():
            try:
                distributor = user.distributor_profile
                return queryset.filter(distributor=distributor)
            except:
                return queryset.none()
        
        return queryset.none()

class BonusDetailView(generics.RetrieveAPIView):
    queryset = Bonus.objects.select_related('distributor__user').all()
    serializer_class = BonusSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'id'