from django.shortcuts import render

# Create your views here.
from rest_framework import generics, permissions, filters
from django_filters.rest_framework import DjangoFilterBackend
from .models import Commission
from .serializers import CommissionSerializer

class CommissionListView(generics.ListAPIView):
    queryset = Commission.objects.select_related(
        'distributor__user', 'order', 'source_distributor__user'
    ).all()
    serializer_class = CommissionSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['type', 'status', 'distributor']
    search_fields = ['order__order_number', 'distributor__user__email']
    
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

class CommissionDetailView(generics.RetrieveAPIView):
    queryset = Commission.objects.select_related(
        'distributor__user', 'order', 'source_distributor__user'
    ).all()
    serializer_class = CommissionSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'id'