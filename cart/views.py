from django.shortcuts import render

# Create your views here.
# cart/views.py
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from django.db import transaction

from .models import Cart, CartItem
from .serializers import (
    CartSerializer,
    CartWriteSerializer,
    CartItemSerializer,
    CartItemWriteSerializer,
)
from products.models import Product


# ==================== CARTS ====================

@api_view(['GET', 'POST'])
@permission_classes([AllowAny])
def cart_list_create(request):
    """
    GET  /api/v1/carts/   -> list all carts
    POST /api/v1/carts/   -> create a cart

    Filters (GET):
      ?status=active
      ?user=<id>
      ?distributor=<id>
      ?shop=<id>
      ?session_key=<token>
    """
    if request.method == 'GET':
        carts = Cart.objects.select_related(
            'user', 'distributor__user', 'shop'
        ).prefetch_related('items__product')

        status_filter = request.query_params.get('status')
        user_filter = request.query_params.get('user')
        distributor_filter = request.query_params.get('distributor')
        shop_filter = request.query_params.get('shop')
        session_filter = request.query_params.get('session_key')

        if status_filter:
            carts = carts.filter(status=status_filter)
        if user_filter:
            carts = carts.filter(user_id=user_filter)
        if distributor_filter:
            carts = carts.filter(distributor_id=distributor_filter)
        if shop_filter:
            carts = carts.filter(shop_id=shop_filter)
        if session_filter:
            carts = carts.filter(session_key=session_filter)

        serializer = CartSerializer(carts, many=True)
        return Response({
            'count': carts.count(),
            'results': serializer.data,
        }, status=status.HTTP_200_OK)

    # POST
    serializer = CartWriteSerializer(data=request.data)
    if serializer.is_valid():
        cart = serializer.save()
        # Re-serialize with read serializer for the full response
        return Response(CartSerializer(cart).data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'PUT', 'PATCH', 'DELETE'])
@permission_classes([AllowAny])
def cart_detail(request, pk):
    """
    GET    /api/v1/carts/<pk>/
    PUT    /api/v1/carts/<pk>/
    PATCH  /api/v1/carts/<pk>/
    DELETE /api/v1/carts/<pk>/
    """
    try:
        cart = Cart.objects.select_related(
            'user', 'distributor__user', 'shop'
        ).prefetch_related('items__product').get(pk=pk)
    except Cart.DoesNotExist:
        return Response({'error': 'Cart not found'}, status=status.HTTP_404_NOT_FOUND)

    if request.method == 'GET':
        return Response(CartSerializer(cart).data)

    if request.method in ('PUT', 'PATCH'):
        partial = request.method == 'PATCH'
        serializer = CartWriteSerializer(cart, data=request.data, partial=partial)
        if serializer.is_valid():
            serializer.save()
            return Response(CartSerializer(cart).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    cart.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


# ==================== CART ITEMS ====================

@api_view(['GET', 'POST'])
@permission_classes([AllowAny])
def cart_items_list_create(request, cart_id):
    """
    GET  /api/v1/carts/<cart_id>/items/    -> list items in cart
    POST /api/v1/carts/<cart_id>/items/    -> add an item
         Body: { "product": 12, "quantity": 2 }
               (price/bv optional — default to product.effective_*)
    """
    try:
        cart = Cart.objects.get(pk=cart_id)
    except Cart.DoesNotExist:
        return Response({'error': 'Cart not found'}, status=status.HTTP_404_NOT_FOUND)

    if request.method == 'GET':
        items = cart.items.select_related('product').all()
        return Response(CartItemSerializer(items, many=True).data)

    # POST
    serializer = CartItemWriteSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    data = serializer.validated_data
    product = data['product']
    qty = data['quantity']
    price = data.get('price', product.effective_price)
    bv = data.get('bv', product.effective_bv)

    with transaction.atomic():
        item, created = CartItem.objects.get_or_create(
            cart=cart,
            product=product,
            defaults={'quantity': qty, 'price': price, 'bv': bv},
        )
        if not created:
            # Bump quantity on existing line
            item.quantity += qty
            item.price = price
            item.bv = bv
            item.save()

    return Response(
        CartItemSerializer(item).data,
        status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
    )


@api_view(['GET', 'PUT', 'PATCH', 'DELETE'])
@permission_classes([AllowAny])
def cart_item_detail(request, cart_id, item_id):
    """
    GET    /api/v1/carts/<cart_id>/items/<item_id>/
    PUT    /api/v1/carts/<cart_id>/items/<item_id>/
    PATCH  /api/v1/carts/<cart_id>/items/<item_id>/
    DELETE /api/v1/carts/<cart_id>/items/<item_id>/
    """
    try:
        item = CartItem.objects.select_related('product', 'cart').get(
            pk=item_id, cart_id=cart_id
        )
    except CartItem.DoesNotExist:
        return Response({'error': 'Cart item not found'}, status=status.HTTP_404_NOT_FOUND)

    if request.method == 'GET':
        return Response(CartItemSerializer(item).data)

    if request.method in ('PUT', 'PATCH'):
        partial = request.method == 'PATCH'
        serializer = CartItemSerializer(item, data=request.data, partial=partial)
        if serializer.is_valid():
            serializer.save()
            return Response(CartItemSerializer(item).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    item.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


# ==================== HELPERS ====================

@api_view(['POST'])
@permission_classes([AllowAny])
def cart_clear(request, cart_id):
    """
    POST /api/v1/carts/<cart_id>/clear/
    Removes all items from the cart.
    """
    try:
        cart = Cart.objects.get(pk=cart_id)
    except Cart.DoesNotExist:
        return Response({'error': 'Cart not found'}, status=status.HTTP_404_NOT_FOUND)

    cart.items.all().delete()
    return Response(CartSerializer(cart).data, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([AllowAny])
def cart_checkout(request, cart_id):
    """
    POST /api/v1/carts/<cart_id>/checkout/
    Marks the cart as 'converted'. Frontend can then create the Order
    from the cart contents (or backend can be extended to do it here).
    """
    try:
        cart = Cart.objects.get(pk=cart_id)
    except Cart.DoesNotExist:
        return Response({'error': 'Cart not found'}, status=status.HTTP_404_NOT_FOUND)

    if not cart.items.exists():
        return Response(
            {'error': 'Cart is empty'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    cart.status = 'converted'
    cart.save(update_fields=['status', 'updated_at'])
    return Response(CartSerializer(cart).data, status=status.HTTP_200_OK)