from django.shortcuts import render

# Create your views here.
from rest_framework import generics, permissions, filters, status
from rest_framework.response import Response
from rest_framework.views import APIView
from django_filters.rest_framework import DjangoFilterBackend
from .models import Order
from .serializers import OrderSerializer, OrderCreateSerializer

class OrderListView(generics.ListAPIView):
    queryset = Order.objects.select_related('customer', 'distributor__user').prefetch_related('items__product').all()
    serializer_class = OrderSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['status', 'payment_status']
    search_fields = ['order_number', 'customer__email', 'customer__first_name', 'customer__last_name']
    
    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        
        # Admin can see all orders
        if user.is_admin():
            return queryset
        
        # Distributor can see their own orders
        if user.is_distributor():
            try:
                distributor = user.distributor_profile
                return queryset.filter(distributor=distributor)
            except:
                return queryset.none()
        
        # Customer can see their own orders
        return queryset.filter(customer=user)

class OrderDetailView(generics.RetrieveUpdateAPIView):
    queryset = Order.objects.select_related('customer', 'distributor__user').prefetch_related('items__product').all()
    serializer_class = OrderSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'id'
    
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
        
        return queryset.filter(customer=user)

class OrderCreateView(generics.CreateAPIView):
    queryset = Order.objects.all()
    serializer_class = OrderCreateSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def perform_create(self, serializer):
        # Auto-set customer if not provided
        if not serializer.validated_data.get('customer'):
            serializer.save(customer=self.request.user)
        else:
            serializer.save()

class OrderStatusUpdateView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def patch(self, request, id):
        try:
            order = Order.objects.get(id=id)
            
            # Check permissions
            if not request.user.is_admin():
                return Response(
                    {'error': 'Only admins can update order status'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            status_value = request.data.get('status')
            if status_value not in dict(Order.STATUS_CHOICES):
                return Response(
                    {'error': 'Invalid status'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            order.status = status_value
            order.save()
            
            return Response(OrderSerializer(order).data)
        except Order.DoesNotExist:
            return Response(
                {'error': 'Order not found'},
                status=status.HTTP_404_NOT_FOUND
            )