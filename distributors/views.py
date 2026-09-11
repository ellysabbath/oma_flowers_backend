# distributors/views.py
from django.db.models import Count, Q, Sum
from rest_framework import serializers
from rest_framework import generics, status, permissions, filters
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView

from users.models import User
from .models import Distributor
from .serializers import (
    DistributorSerializer, DistributorCreateSerializer,
    DistributorHierarchySerializer, DistributorStatsSerializer
)


# ==================== LIST + CREATE ====================

class DistributorListView(generics.ListCreateAPIView):
    queryset = Distributor.objects.select_related('user').all()
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.SearchFilter]
    search_fields = ['user__first_name', 'user__last_name', 'user__email']
    pagination_class = None

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return DistributorCreateSerializer
        return DistributorSerializer

    def get_queryset(self):
        return (
            Distributor.objects
            .select_related('user')
            .annotate(
                _downline_count=Count(
                    'downline_members', distinct=True
                ),
                _active_downline_count=Count(
                    'downline_members',
                    filter=Q(downline_members__user__status='active'),
                    distinct=True,
                ),
            )
        )


# ==================== DETAIL ====================

class DistributorDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Distributor.objects.select_related('user').all()
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'id'

    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return DistributorCreateSerializer
        return DistributorSerializer

    def perform_update(self, serializer):
        upline_id = self.request.data.get('upline_id')
        if upline_id:
            if str(upline_id) == str(self.kwargs['id']):
                raise serializers.ValidationError(
                    {'upline_id': 'A distributor cannot be their own upline'}
                )
            try:
                Distributor.objects.get(id=upline_id)
            except Distributor.DoesNotExist:
                raise serializers.ValidationError(
                    {'upline_id': 'Upline distributor not found'}
                )
        serializer.save()

    def perform_destroy(self, instance):
        user = instance.user
        user.user_type = 'customer'
        user.save()
        instance.delete()


# ==================== HIERARCHY (by id) ====================

class DistributorHierarchyView(generics.RetrieveAPIView):
    """
    GET /api/v1/distributors/<id>/hierarchy/
    Returns the direct downline of the given distributor (each with
    its own nested subtree).
    """
    queryset = Distributor.objects.all()
    serializer_class = DistributorHierarchySerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'id'

    def get(self, request, *args, **kwargs):
        root = self.get_object()
        children = root.downline_members.select_related('user').all()
        serializer = self.get_serializer(children, many=True)
        return Response(serializer.data)


# ==================== HIERARCHY (mine) ====================

class MyHierarchyView(APIView):
    """
    GET /api/v1/distributors/me/hierarchy/
    Returns { distributor: {...}, downline: [...] } for the logged-in user.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        try:
            me = request.user.distributor_profile
        except AttributeError:
            return Response(
                {'error': 'You are not registered as a distributor.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        children = me.downline_members.select_related('user').all()
        serializer = DistributorHierarchySerializer(children, many=True)

        return Response({
            'distributor': {
                'id': me.id,
                'name': me.user.get_full_name() or me.user.username,
                'rank': me.rank,
                'level': me.level,
                'pbv': str(me.pbv),
                'cgv': str(me.cgv),
                'bonus_percentage': str(me.bonus_percentage),
            },
            'downline': serializer.data,
        })


# ==================== REMOVE DOWNLINE ====================

@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def remove_downline(request, distributor_id):
    """
    POST /api/v1/distributors/<id>/remove-downline/

    Body:
      { "action": "detach" }  → clears the upline
      { "action": "delete" }  → deletes the Distributor profile entirely
    """
    try:
        me = request.user.distributor_profile
    except AttributeError:
        return Response(
            {'error': 'You are not a distributor'},
            status=status.HTTP_403_FORBIDDEN,
        )

    try:
        target = Distributor.objects.select_related('user').get(
            pk=distributor_id
        )
    except Distributor.DoesNotExist:
        return Response(
            {'error': 'Distributor not found'},
            status=status.HTTP_404_NOT_FOUND,
        )

    if target.upline_id != me.id:
        return Response(
            {'error': 'You can only remove your direct downlines'},
            status=status.HTTP_403_FORBIDDEN,
        )

    if target.id == me.id:
        return Response(
            {'error': 'You cannot remove yourself'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    action = request.data.get('action', 'detach')

    # Capture former upline BEFORE any change
    former_upline = target.upline

    if action == 'delete':
        user = target.user
        user.user_type = 'customer'
        user.save()
        target.delete()
        message = 'Distributor removed'
    else:
        target.upline = None
        target.save(update_fields=['upline'])
        message = 'Detached from your downline'

    # Recompute the (former) upline's CGV chain
    if former_upline:
        former_upline.cgv = former_upline.compute_cgv()
        former_upline.save(update_fields=['cgv'])
        former_upline.refresh_ancestors_cgv()

    return Response({'message': message})


# ==================== STATS ====================

class DistributorStatsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        try:
            if not request.user or not request.user.is_authenticated:
                return Response(
                    {'error': 'Authentication required'},
                    status=status.HTTP_401_UNAUTHORIZED,
                )

            distributor = request.user.distributor_profile

            from orders.models import Order
            orders = Order.objects.filter(distributor=distributor)

            total_orders = orders.count()
            total_commission = (
                distributor.commissions
                .filter(status='paid')
                .aggregate(Sum('amount'))['amount__sum'] or 0
            )
            total_bonuses = (
                distributor.bonuses
                .filter(status='paid')
                .aggregate(Sum('amount'))['amount__sum'] or 0
            )

            from django.utils import timezone
            from datetime import timedelta

            now = timezone.now()
            thirty_days_ago = now - timedelta(days=30)
            sixty_days_ago = now - timedelta(days=60)

            recent_orders = orders.filter(order_date__gte=thirty_days_ago)
            previous_orders = orders.filter(
                order_date__gte=sixty_days_ago,
                order_date__lt=thirty_days_ago,
            )

            recent_revenue = (
                recent_orders.aggregate(Sum('total_amount'))['total_amount__sum']
                or 0
            )
            previous_revenue = (
                previous_orders.aggregate(Sum('total_amount'))['total_amount__sum']
                or 0
            )

            growth_rate = 0
            if previous_revenue > 0:
                growth_rate = (
                    (recent_revenue - previous_revenue) / previous_revenue
                ) * 100

            stats = {
                'total_orders': total_orders,
                'total_commission': total_commission,
                'total_bonuses': total_bonuses,
                'downline_count': distributor.downline_count,
                'active_downline': distributor.active_downline_count,
                'rank': distributor.rank,
                'pbv': distributor.pbv,
                'cgv': distributor.cgv,
                'growth_rate': round(growth_rate, 2),
            }

            return Response(stats)
        except Distributor.DoesNotExist:
            return Response(
                {'error': 'Distributor profile not found'},
                status=status.HTTP_404_NOT_FOUND,
            )