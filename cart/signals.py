# cart/signals.py
from collections import defaultdict

from django.db.models import F
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Cart
from distributors.models import Distributor
from products.models import Product


@receiver(post_save, sender=Cart)
def raise_distributor_volumes_on_checkout(sender, instance, created, **kwargs):
    """
    When a Cart moves to status='converted':
      For every CartItem, credit the **product's seller**:
        - seller.pbv += item.bv * item.quantity
        - seller.cgv += item.bv * item.quantity
        - every ancestor's cgv += item.bv * item.quantity

    Also bumps Product.sales by the quantity sold.

    Idempotent — a marker in cart.notes ensures it runs exactly once per cart.
    """
    if created:
        return
    if instance.status != 'converted':
        return

    marker = f'[bv_applied:{instance.id}]'
    notes = instance.notes or ''
    if marker in notes:
        return  # already applied

    items = list(
        instance.items.select_related('product__seller').all()
    )
    if not items:
        Cart.objects.filter(pk=instance.pk).update(
            notes=f'{notes} {marker}'.strip()
        )
        return

    # ---------- 1. Aggregate BV per seller ----------
    seller_bv_map: dict[int, int] = defaultdict(int)

    for item in items:
        product = item.product
        seller_id = getattr(product, 'seller_id', None)
        if not seller_id:
            continue  # product has no owner — nothing to credit
        seller_bv_map[seller_id] += (item.bv or 0) * item.quantity

    # ---------- 2. Credit each seller and their uplines ----------
    for seller_id, total_bv in seller_bv_map.items():
        if total_bv <= 0:
            continue

        # Seller: PBV + CGV
        Distributor.objects.filter(pk=seller_id).update(
            pbv=F('pbv') + total_bv,
            cgv=F('cgv') + total_bv,
        )

        # Uplines: CGV only
        try:
            seller_obj = Distributor.objects.select_related('upline').get(
                pk=seller_id
            )
        except Distributor.DoesNotExist:
            continue

        seen = {seller_obj.pk}
        ancestor = seller_obj.upline
        while ancestor is not None and ancestor.pk not in seen:
            Distributor.objects.filter(pk=ancestor.pk).update(
                cgv=F('cgv') + total_bv
            )
            seen.add(ancestor.pk)
            ancestor = ancestor.upline

    # ---------- 3. Bump Product.sales ----------
    for item in items:
        if item.product_id:
            Product.objects.filter(pk=item.product_id).update(
                sales=F('sales') + item.quantity
            )

    # ---------- 4. Stamp the cart so we never double-count ----------
    Cart.objects.filter(pk=instance.pk).update(
        notes=f'{notes} {marker}'.strip()
    )