# distributors/models.py
"""
OMA Flowers — Distributor model.

Includes:
  • Full distributor profile (user, upline, rank, PBV, CGV, bonus).
  • Recursive hierarchy helpers.
  • raise_volumes() — called on every sale to bump PBV, then recompute CGV
    for every ancestor from the tree.
  • Auto rank promotion based on the OMA Flowers business plan, Section 3.1.
  • CGV is *derived*: always the sum of own PBV + all descendants' PBV.
"""

from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models import F


# ------------------------------------------------------------------
# Rank ladder — single source of truth
# ------------------------------------------------------------------
RANK_LADDER = [
    ('Associate',            Decimal('0'),      Decimal('20'),  Decimal('4.00')),
    ('Builder',              Decimal('200'),    Decimal('30'),  Decimal('5.00')),
    ('Leader',               Decimal('600'),    Decimal('50'),  Decimal('8.00')),
    ('Senior Leader',        Decimal('1500'),   Decimal('70'),  Decimal('11.00')),
    ('Executive',            Decimal('4000'),   Decimal('90'),  Decimal('14.00')),
    ('Manager',              Decimal('10000'),  Decimal('120'), Decimal('17.00')),
    ('Senior Manager',       Decimal('25000'),  Decimal('160'), Decimal('20.00')),
    ('Director',             Decimal('60000'),  Decimal('200'), Decimal('24.00')),
    ('Crown Director',       Decimal('120000'), Decimal('250'), Decimal('28.00')),
    ('Royal Crown Director', Decimal('184000'), Decimal('300'), Decimal('32.00')),
]

RANK_ORDER = {name: idx for idx, (name, *_rest) in enumerate(RANK_LADDER)}


def compute_rank(pbv, cgv):
    """
    Return (rank_name, bonus_percentage) for the highest tier whose
    CGV *and* PBV thresholds are both satisfied.
    """
    pbv = Decimal(pbv or 0)
    cgv = Decimal(cgv or 0)

    qualified = None
    for name, min_cgv, min_pbv, bonus in RANK_LADDER:
        if cgv >= min_cgv and pbv >= min_pbv:
            qualified = (name, bonus)

    if qualified is None:
        return ('Associate', Decimal('0.00'))

    return qualified


class Distributor(models.Model):
    RANK_CHOICES = tuple((name, name) for name, *_ in RANK_LADDER)

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='distributor_profile',
    )
    upline = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='downline_members',
    )
    rank = models.CharField(
        max_length=50, choices=RANK_CHOICES, default='Associate'
    )
    level = models.PositiveSmallIntegerField(default=1)
    pbv = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    cgv = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    bonus_percentage = models.DecimalField(
        max_digits=5, decimal_places=2, default=4.00
    )
    join_date = models.DateField(auto_now_add=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'distributors'
        ordering = ['-cgv']

    def __str__(self):
        return f"{self.user.full_name} - {self.rank}"

    # ----------------------------------------------------------------
    # Downline helpers
    # ----------------------------------------------------------------

    @property
    def downline_count(self):
        return self.downline_members.count()

    @property
    def active_downline_count(self):
        return self.downline_members.filter(user__status='active').count()

    def get_full_hierarchy(self):
        """Return the full nested subtree as plain dicts."""
        hierarchy = []
        for downline in self.downline_members.select_related('user').all():
            hierarchy.append({
                'id': downline.id,
                'name': downline.user.full_name,
                'rank': downline.rank,
                'level': downline.level,
                'pbv': downline.pbv,
                'cgv': downline.cgv,
                'downline': downline.get_full_hierarchy(),
            })
        return hierarchy

    # ----------------------------------------------------------------
    # Derived CGV
    # ----------------------------------------------------------------

    def compute_cgv(self):
        """
        CGV = own PBV + Σ every descendant's PBV.
        BFS over the tree — one query per level, not per node.
        """
        total = Decimal(self.pbv or 0)
        frontier = list(self.downline_members.values_list('id', flat=True))
        while frontier:
            rows = list(
                Distributor.objects
                .filter(pk__in=frontier)
                .values_list('pbv', 'id')
            )
            next_frontier = []
            for pbv, node_id in rows:
                total += Decimal(pbv or 0)
                next_frontier.extend(
                    Distributor.objects
                    .filter(upline_id=node_id)
                    .values_list('id', flat=True)
                )
            frontier = next_frontier
        return total

    def refresh_ancestors_cgv(self):
        """
        Recompute CGV for every ancestor of this node (walk uplines).
        """
        ancestor = self.upline
        seen = {self.pk}
        while ancestor is not None and ancestor.pk not in seen:
            ancestor.cgv = ancestor.compute_cgv()
            ancestor.save(update_fields=['cgv'])
            seen.add(ancestor.pk)
            ancestor = (
                Distributor.objects
                .select_related('upline')
                .get(pk=ancestor.pk)
                .upline
            )

    # ----------------------------------------------------------------
    # Save hook — auto rank promotion
    # ----------------------------------------------------------------

    def save(self, *args, **kwargs):
        if self.pk is not None:
            try:
                old = Distributor.objects.only('rank', 'pbv', 'cgv').get(pk=self.pk)
            except Distributor.DoesNotExist:
                old = None

            if old and (old.pbv != self.pbv or old.cgv != self.cgv):
                qualified_rank, qualified_bonus = compute_rank(self.pbv, self.cgv)
                current_idx = RANK_ORDER.get(self.rank, -1)
                qualified_idx = RANK_ORDER.get(qualified_rank, -1)

                if qualified_idx > current_idx:
                    self.rank = qualified_rank
                    self.bonus_percentage = qualified_bonus

        super().save(*args, **kwargs)

    # ----------------------------------------------------------------
    # Volume raising
    # ----------------------------------------------------------------

    @classmethod
    def raise_volumes(cls, seller_id, total_bv):
        """
        Called when a sale happens.

        1) Seller's PBV is incremented.
        2) Seller's CGV and every ancestor's CGV are RECOMPUTED from the
           tree (not incremented manually).
        3) Ranks are refreshed for the seller.
        """
        if not seller_id or total_bv <= 0:
            return

        total_bv = Decimal(total_bv)

        # 1) Seller's PBV
        cls.objects.filter(pk=seller_id).update(pbv=F('pbv') + total_bv)

        # 2) Reload and recompute CGV
        try:
            seller = cls.objects.select_related('upline').get(pk=seller_id)
        except cls.DoesNotExist:
            return

        seller.cgv = seller.compute_cgv()
        seller.save(update_fields=['cgv'])

        # 3) Every ancestor
        seller.refresh_ancestors_cgv()

        # 4) Rank refresh for seller + ancestors
        ancestor_ids = set()
        anc = seller.upline
        seen = {seller.pk}
        while anc is not None and anc.pk not in seen:
            ancestor_ids.add(anc.pk)
            seen.add(anc.pk)
            anc = cls.objects.select_related('upline').get(pk=anc.pk).upline

        cls.recalculate_ranks({seller.pk, *ancestor_ids})

    # ----------------------------------------------------------------
    # Bulk rank recalculation
    # ----------------------------------------------------------------

    @classmethod
    def recalculate_ranks(cls, distributor_ids):
        if not distributor_ids:
            return

        qs = cls.objects.filter(pk__in=distributor_ids).only(
            'id', 'rank', 'pbv', 'cgv', 'bonus_percentage'
        )

        to_update = []
        for d in qs:
            qualified_rank, qualified_bonus = compute_rank(d.pbv, d.cgv)
            current_idx = RANK_ORDER.get(d.rank, -1)
            qualified_idx = RANK_ORDER.get(qualified_rank, -1)

            if qualified_idx > current_idx:
                d.rank = qualified_rank
                d.bonus_percentage = qualified_bonus
                to_update.append(d)

        if to_update:
            cls.objects.bulk_update(to_update, ['rank', 'bonus_percentage'])