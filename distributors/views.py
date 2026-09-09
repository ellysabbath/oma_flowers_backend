from django.shortcuts import render
from rest_framework import serializers
from rest_framework import generics, status, permissions, filters
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db.models import Sum, Count, Q
from django.shortcuts import get_object_or_404
from users.models import User
from .models import Distributor
from .serializers import (
    DistributorSerializer, DistributorCreateSerializer,
    DistributorHierarchySerializer, DistributorStatsSerializer
)

class DistributorListView(generics.ListCreateAPIView):
    """
    List all distributors or create a new distributor
    """
    queryset = Distributor.objects.select_related('user').all()
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.SearchFilter]
    search_fields = ['user__first_name', 'user__last_name', 'user__email']
    
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return DistributorCreateSerializer
        return DistributorSerializer
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by rank if provided
        rank = self.request.query_params.get('rank')
        if rank:
            queryset = queryset.filter(rank=rank)
        
        # Filter by status if provided
        status = self.request.query_params.get('status')
        if status:
            queryset = queryset.filter(user__status=status)
        
        # If user is a distributor, show only their downline
        if self.request.user.is_distributor():
            try:
                distributor = self.request.user.distributor_profile
                queryset = queryset.filter(upline=distributor)
            except Distributor.DoesNotExist:
                queryset = queryset.none()
        
        return queryset
    
    def perform_create(self, serializer):
        """Create a new distributor from existing user"""
        user_id = self.request.data.get('user_id')
        
        if not user_id:
            raise serializers.ValidationError(
                {'user_id': 'User ID is required'}
            )
        
        # Check if user exists
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            raise serializers.ValidationError(
                {'user_id': 'User not found'}
            )
        
        # Check if user is already a distributor
        if Distributor.objects.filter(user=user).exists():
            raise serializers.ValidationError(
                {'user_id': 'This user is already a distributor'}
            )
        
        # Check if upline exists if provided
        upline_id = self.request.data.get('upline_id')
        if upline_id:
            try:
                upline = Distributor.objects.get(id=upline_id)
            except Distributor.DoesNotExist:
                raise serializers.ValidationError(
                    {'upline_id': 'Upline distributor not found'}
                )
        
        # Save the distributor
        distributor = serializer.save(user=user)
        
        # Update user type to distributor
        user.user_type = 'distributor'
        user.save()
        
        return distributor

class DistributorDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Retrieve, update or delete a distributor
    """
    queryset = Distributor.objects.select_related('user').all()
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'id'
    
    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return DistributorCreateSerializer
        return DistributorSerializer
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # If user is a distributor, only allow access to themselves and their downline
        if self.request.user.is_distributor():
            try:
                distributor = self.request.user.distributor_profile
                queryset = queryset.filter(Q(id=distributor.id) | Q(upline=distributor))
            except Distributor.DoesNotExist:
                queryset = queryset.none()
        
        return queryset
    
    def perform_update(self, serializer):
        """Update a distributor"""
        # If updating upline, verify it exists and isn't self
        upline_id = self.request.data.get('upline_id')
        if upline_id:
            if upline_id == self.kwargs['id']:
                raise serializers.ValidationError(
                    {'upline_id': 'A distributor cannot be their own upline'}
                )
            try:
                upline = Distributor.objects.get(id=upline_id)
            except Distributor.DoesNotExist:
                raise serializers.ValidationError(
                    {'upline_id': 'Upline distributor not found'}
                )
        
        serializer.save()
    
    def perform_destroy(self, instance):
        """Delete a distributor"""
        # Update user type back to customer
        user = instance.user
        user.user_type = 'customer'
        user.save()
        
        # Delete the distributor
        instance.delete()

class DistributorHierarchyView(generics.RetrieveAPIView):
    queryset = Distributor.objects.all()
    serializer_class = DistributorHierarchySerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'id'
    
    def get_object(self):
        if self.request.user.is_distributor():
            return self.request.user.distributor_profile
        return super().get_object()

class DistributorStatsView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        try:
            if not request.user.is_distributor():
                return Response({'error': 'User is not a distributor'}, 
                              status=status.HTTP_400_BAD_REQUEST)
            
            distributor = request.user.distributor_profile
            
            # Get orders stats
            from orders.models import Order
            orders = Order.objects.filter(distributor=distributor)
            
            total_orders = orders.count()
            total_commission = distributor.commissions.filter(status='paid').aggregate(
                Sum('amount')
            )['amount__sum'] or 0
            
            total_bonuses = distributor.bonuses.filter(status='paid').aggregate(
                Sum('amount')
            )['amount__sum'] or 0
            
            # Calculate growth rate (simplified - compare last 30 days vs previous 30 days)
            from django.utils import timezone
            from datetime import timedelta
            
            now = timezone.now()
            thirty_days_ago = now - timedelta(days=30)
            sixty_days_ago = now - timedelta(days=60)
            
            recent_orders = orders.filter(order_date__gte=thirty_days_ago)
            previous_orders = orders.filter(
                order_date__gte=sixty_days_ago,
                order_date__lt=thirty_days_ago
            )
            
            recent_revenue = recent_orders.aggregate(Sum('total_amount'))['total_amount__sum'] or 0
            previous_revenue = previous_orders.aggregate(Sum('total_amount'))['total_amount__sum'] or 0
            
            growth_rate = 0
            if previous_revenue > 0:
                growth_rate = ((recent_revenue - previous_revenue) / previous_revenue) * 100
            
            stats = {
                'total_orders': total_orders,
                'total_commission': total_commission,
                'total_bonuses': total_bonuses,
                'downline_count': distributor.downline_count,
                'active_downline': distributor.active_downline_count,
                'rank': distributor.rank,
                'pbv': distributor.pbv,
                'cgv': distributor.cgv,
                'growth_rate': round(growth_rate, 2)
            }
            
            return Response(stats)
        except Distributor.DoesNotExist:
            return Response({'error': 'Distributor profile not found'}, 
                          status=status.HTTP_404_NOT_FOUND)