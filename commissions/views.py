# commissions/views.py
"""
Commission views.

The list endpoint automatically generates commission records from
existing carts + distributors every time it is called. Generation is
idempotent — running it repeatedly will not create duplicates.
"""

from decimal import Decimal

from django.db import transaction
from django.db.models import Q
from rest_framework import generics, filters
from django_filters.rest_framework import DjangoFilterBackend

from .models import Commission
from .serializers import CommissionSerializer


BV_TO_TSH = Decimal('2500')


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _get_upline_id(distributor):
    """Return the upline id whether it's exposed as upline or upline_id."""
    up = getattr(distributor, 'upline', None)
    if up is None:
        return None
    if hasattr(up, 'pk'):
        return up.pk
    return None


def _collect_seller_pbv_from_carts():
    """
    Walk every cart item, group BV by product.seller.id.

    Returns:
        dict { distributor_id: Decimal(total_bv) }
    """
    from cart.models import CartItem

    totals = {}
    for item in CartItem.objects.select_related('product__seller').all():
        seller = getattr(item.product, 'seller', None)
        if seller is None:
            continue
        bv = Decimal(item.bv or 0) * Decimal(item.quantity or 1)
        totals[seller.id] = totals.get(seller.id, Decimal('0')) + bv
    return totals


def _generate_commissions():
    """
    Idempotent generation of commission rows from cart data.

    For every distributor who has PBV > 0:
      • Personal commission: pbv × seller% × 2500
      • For each upline (walk up):
          Differential commission: pbv × (upline% − seller%) × 2500
    """
    from distributors.models import Distributor

    pbv_by_seller = _collect_seller_pbv_from_carts()
    if not pbv_by_seller:
        return

    # Load every distributor once
    dist_map = {
        d.id: d
        for d in Distributor.objects
        .select_related('upline', 'user')
        .all()
    }

    with transaction.atomic():
        for seller_id, seller_bv in pbv_by_seller.items():
            if seller_bv <= 0:
                continue

            seller = dist_map.get(seller_id)
            if seller is None:
                continue

            seller_pct = Decimal(seller.bonus_percentage or 0)

            # ---------- Personal commission ----------
            if seller_pct > 0:
                amount = (
                    seller_bv * seller_pct / 100 * BV_TO_TSH
                ).quantize(Decimal('0.01'))

                # Update if exists, otherwise create.
                # We use (distributor=seller, type='personal', source_distributor=None)
                # as the natural key.
                existing = Commission.objects.filter(
                    distributor=seller,
                    type='personal',
                    source_distributor__isnull=True,
                ).first()

                if existing:
                    existing.pbv = seller_bv
                    existing.percentage = seller_pct
                    existing.amount = amount
                    existing.save(update_fields=[
                        'pbv', 'percentage', 'amount', 'updated_at'
                    ])
                else:
                    Commission.objects.create(
                        distributor=seller,
                        order=None,
                        type='personal',
                        source_distributor=None,
                        pbv=seller_bv,
                        percentage=seller_pct,
                        amount=amount,
                        status='pending',
                    )

            # ---------- Differential commissions ----------
            ancestor = seller.upline
            seen = {seller.pk}
            while ancestor is not None and ancestor.pk not in seen:
                anc_pct = Decimal(ancestor.bonus_percentage or 0)
                diff = anc_pct - seller_pct

                if diff > 0:
                    amount = (
                        seller_bv * diff / 100 * BV_TO_TSH
                    ).quantize(Decimal('0.01'))

                    existing = Commission.objects.filter(
                        distributor=ancestor,
                        type='differential',
                        source_distributor=seller,
                    ).first()

                    if existing:
                        existing.pbv = seller_bv
                        existing.percentage = diff
                        existing.amount = amount
                        existing.save(update_fields=[
                            'pbv', 'percentage', 'amount', 'updated_at'
                        ])
                    else:
                        Commission.objects.create(
                            distributor=ancestor,
                            order=None,
                            type='differential',
                            source_distributor=seller,
                            pbv=seller_bv,
                            percentage=diff,
                            amount=amount,
                            status='pending',
                        )

                seen.add(ancestor.pk)
                ancestor = ancestor.upline


# ------------------------------------------------------------------
# Views
# ------------------------------------------------------------------

class CommissionListView(generics.ListAPIView):
    """
    GET /api/v1/commissions/

    On every call, regenerates commission rows from current cart data
    (idempotent), then returns the list.

    Filters:
      ?type=personal | differential
      ?status=paid | pending | processing
      ?distributor=<id>
      ?search=<name or email>
    """
    serializer_class = CommissionSerializer
    permission_classes = []
    authentication_classes = []

    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['type', 'status', 'distributor']
    search_fields = [
        'distributor__user__email',
        'distributor__user__first_name',
        'distributor__user__last_name',
    ]

    def get_queryset(self):
        try:
            _generate_commissions()
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(
                'Commission generation failed: %s', e, exc_info=True
            )

        return (
            Commission.objects
            .select_related(
                'distributor__user',
                'order',
                'source_distributor__user',
            )
            .all()
        )


class CommissionDetailView(generics.RetrieveUpdateAPIView):
    queryset = Commission.objects.select_related(
        'distributor__user', 'order', 'source_distributor__user'
    ).all()
    serializer_class = CommissionSerializer
    permission_classes = []
    authentication_classes = []
    lookup_field = 'id'