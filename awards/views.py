from django.shortcuts import render

# Create your views here.
from rest_framework import generics, permissions, filters
from django_filters.rest_framework import DjangoFilterBackend
from .models import Award
from .serializers import AwardSerializer

class AwardListView(generics.ListAPIView):
    queryset = Award.objects.select_related('distributor__user').all()
    serializer_class = AwardSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['category', 'status', 'year']
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

class AwardDetailView(generics.RetrieveAPIView):
    queryset = Award.objects.select_related('distributor__user').all()
    serializer_class = AwardSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'id'