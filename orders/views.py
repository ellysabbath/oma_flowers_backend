from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .models import Order
from .serializers import OrderSerializer


# ---------- LIST + CREATE ----------

@api_view(['GET', 'POST'])
@permission_classes([AllowAny])
def order_list_create(request):
    """
    GET  /api/v1/orders/  -> list all orders
    POST /api/v1/orders/  -> create new order
    """
    if request.method == 'GET':
        orders = Order.objects.all().select_related(
            'customer', 'distributor'
        ).prefetch_related('items', 'items__product')

        status_filter = request.query_params.get('status')
        payment_filter = request.query_params.get('payment_status')
        if status_filter:
            orders = orders.filter(status=status_filter)
        if payment_filter:
            orders = orders.filter(payment_status=payment_filter)

        serializer = OrderSerializer(orders, many=True)
        return Response({
            'count': orders.count(),
            'results': serializer.data,
        }, status=status.HTTP_200_OK)

    serializer = OrderSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ---------- RETRIEVE + UPDATE + DELETE ----------

@api_view(['GET', 'PUT', 'PATCH', 'DELETE'])
@permission_classes([AllowAny])
def order_detail(request, pk):
    try:
        order = Order.objects.select_related(
            'customer', 'distributor'
        ).prefetch_related('items', 'items__product').get(pk=pk)
    except Order.DoesNotExist:
        return Response(
            {'error': 'Order not found'},
            status=status.HTTP_404_NOT_FOUND,
        )

    if request.method == 'GET':
        return Response(OrderSerializer(order).data)

    if request.method in ('PUT', 'PATCH'):
        partial = request.method == 'PATCH'
        serializer = OrderSerializer(order, data=request.data, partial=partial)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    order.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


# ---------- STATUS UPDATE ----------

@api_view(['PATCH'])
@permission_classes([AllowAny])
def order_update_status(request, pk):
    """
    PATCH /api/v1/orders/<pk>/status/
    Body: { "status": "shipped" } or { "payment_status": "paid" }
    """
    try:
        order = Order.objects.get(pk=pk)
    except Order.DoesNotExist:
        return Response(
            {'error': 'Order not found'},
            status=status.HTTP_404_NOT_FOUND,
        )

    new_status = request.data.get('status')
    new_payment = request.data.get('payment_status')

    if new_status:
        valid_statuses = [c[0] for c in Order.STATUS_CHOICES]
        if new_status.lower() not in valid_statuses:
            return Response(
                {'error': f'Invalid status. Choose from {valid_statuses}'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        order.status = new_status.lower()

    if new_payment:
        valid_payments = [c[0] for c in Order.PAYMENT_CHOICES]
        if new_payment.lower() not in valid_payments:
            return Response(
                {'error': f'Invalid payment status. Choose from {valid_payments}'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        order.payment_status = new_payment.lower()

    order.save()
    return Response(OrderSerializer(order).data)