# cart/views.py
from django.shortcuts import render
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


# ==================== AUTO-ATTACH HELPER ====================

def _autofill_cart_owner(cart, request=None):
    """
    Ensures a cart has BOTH a shop and a distributor set when possible.

    Priority:
      1. If cart has a shop → distributor = shop's owner
      2. If cart has a distributor → shop = distributor's first shop
      3. If cart has neither → try the logged-in user's distributor
                                then that distributor's first shop
    Returns True if the cart was modified.
    """
    from shops.models import Shop

    changed = False

    # 1) Shop exists → fill distributor from shop owner
    if cart.shop_id and not cart.distributor_id:
        try:
            owner_id = cart.shop.distributor_id
            if owner_id:
                cart.distributor_id = owner_id
                changed = True
        except Exception:
            pass

    # 2) Distributor exists → fill shop from their first shop
    if cart.distributor_id and not cart.shop_id:
        shop = Shop.objects.filter(
            distributor_id=cart.distributor_id
        ).first()
        if shop:
            cart.shop = shop
            changed = True

    # 3) Neither → try the logged-in user
    if not cart.distributor_id and request and request.user.is_authenticated:
        try:
            cart.distributor = request.user.distributor_profile
            changed = True
        except AttributeError:
            pass

    # 4) Still no shop but we now have a distributor → get their first shop
    if cart.distributor_id and not cart.shop_id:
        shop = Shop.objects.filter(
            distributor_id=cart.distributor_id
        ).first()
        if shop:
            cart.shop = shop
            changed = True

    return changed


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
      ?code=OMA-XXXX-XXXX-XXXX     👈 NEW
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
        code_filter = request.query_params.get('code')          # 👈 NEW

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
        if code_filter:                                          # 👈 NEW
            carts = carts.filter(code__iexact=code_filter)

        serializer = CartSerializer(carts, many=True)
        return Response(
            {'count': carts.count(), 'results': serializer.data},
            status=status.HTTP_200_OK,
        )

    # ---------- POST: create cart ----------
    data = request.data.copy()

    # Auto-attach the logged-in user's distributor (if any)
    if request.user.is_authenticated and not data.get('distributor_id'):
        try:
            data['distributor_id'] = request.user.distributor_profile.id
        except AttributeError:
            pass

    # Auto-attach the logged-in user (if not supplied)
    if request.user.is_authenticated and not data.get('user_id'):
        data['user_id'] = request.user.id

    serializer = CartWriteSerializer(data=data)
    if serializer.is_valid():
        cart = serializer.save()

        # Auto-fill shop + distributor
        if _autofill_cart_owner(cart, request):
            cart.save()

        return Response(
            CartSerializer(cart).data, status=status.HTTP_201_CREATED
        )
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
        return Response(
            {'error': 'Cart not found'},
            status=status.HTTP_404_NOT_FOUND,
        )

    if request.method == 'GET':
        return Response(CartSerializer(cart).data)

    if request.method in ('PUT', 'PATCH'):
        partial = request.method == 'PATCH'
        serializer = CartWriteSerializer(
            cart, data=request.data, partial=partial
        )
        if serializer.is_valid():
            serializer.save()

            # Re-check attachments after any edit
            if _autofill_cart_owner(cart, request):
                cart.save()

            return Response(CartSerializer(cart).data)
        return Response(
            serializer.errors, status=status.HTTP_400_BAD_REQUEST
        )

    cart.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


# ==================== LOOKUP BY CODE ====================

@api_view(['GET'])
@permission_classes([AllowAny])
def cart_by_code(request, code):
    """
    GET /api/v1/carts/by-code/<code>/

    Look up a cart by its unique code, e.g.:
        GET /api/v1/carts/by-code/OMA-K7B2-X9NM-4PTR/

    Case-insensitive. Returns the same shape as the standard detail view.
    """
    try:
        cart = (
            Cart.objects
            .select_related('user', 'distributor__user', 'shop')
            .prefetch_related('items__product__seller')
            .get(code__iexact=code)
        )
    except Cart.DoesNotExist:
        return Response(
            {'error': f'No cart found with code "{code}".'},
            status=status.HTTP_404_NOT_FOUND,
        )

    return Response(CartSerializer(cart).data, status=status.HTTP_200_OK)


# ==================== CART ITEMS ====================

@api_view(['GET', 'POST'])
@permission_classes([AllowAny])
def cart_items_list_create(request, cart_id):
    """
    GET  /api/v1/carts/<cart_id>/items/    -> list items in cart
    POST /api/v1/carts/<cart_id>/items/    -> add an item
         Body: { "product": 12, "quantity": 2 }
    """
    try:
        cart = Cart.objects.get(pk=cart_id)
    except Cart.DoesNotExist:
        return Response(
            {'error': 'Cart not found'},
            status=status.HTTP_404_NOT_FOUND,
        )

    if request.method == 'GET':
        items = cart.items.select_related('product').all()
        return Response(CartItemSerializer(items, many=True).data)

    # POST
    serializer = CartItemWriteSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(
            serializer.errors, status=status.HTTP_400_BAD_REQUEST
        )

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
        return Response(
            {'error': 'Cart item not found'},
            status=status.HTTP_404_NOT_FOUND,
        )

    if request.method == 'GET':
        return Response(CartItemSerializer(item).data)

    if request.method in ('PUT', 'PATCH'):
        partial = request.method == 'PATCH'
        serializer = CartItemSerializer(
            item, data=request.data, partial=partial
        )
        if serializer.is_valid():
            serializer.save()
            return Response(CartItemSerializer(item).data)
        return Response(
            serializer.errors, status=status.HTTP_400_BAD_REQUEST
        )

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
        return Response(
            {'error': 'Cart not found'},
            status=status.HTTP_404_NOT_FOUND,
        )

    cart.items.all().delete()
    return Response(CartSerializer(cart).data, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([AllowAny])
def cart_checkout(request, cart_id):
    """
    POST /api/v1/carts/<cart_id>/checkout/

    Marks the cart as 'converted' and updates downstream counters:

      1. Auto-fills shop + distributor using the priority helper
      2. Marks the cart as converted
      3. Bumps `Product.sales` for every item (triggers shop owner_bv recompute)
      4. Recomputes the shop's customers count
    """
    from shops.models import Shop

    # ---------- 1) Load cart ----------
    try:
        cart = Cart.objects.select_related(
            'distributor__user', 'shop', 'user'
        ).prefetch_related('items__product__seller').get(pk=cart_id)
    except Cart.DoesNotExist:
        return Response(
            {'error': 'Cart not found'},
            status=status.HTTP_404_NOT_FOUND,
        )

    if not cart.items.exists():
        return Response(
            {'error': 'Cart is empty'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # ---------- 2) Auto-fill shop + distributor ----------
    _autofill_cart_owner(cart, request)

    # ---------- 3) Save as converted + bump sales + recompute shop ----------
    with transaction.atomic():
        cart.status = 'converted'
        cart.save()

        for item in cart.items.select_related('product').all():
            product = item.product
            product.sales = (product.sales or 0) + item.quantity
            product.save(update_fields=['sales'])

        if cart.shop_id:
            Shop.recompute_for_shop(cart.shop_id)

    return Response(CartSerializer(cart).data, status=status.HTTP_200_OK)