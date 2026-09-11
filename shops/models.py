# shops/models.py
"""
OMA Flowers — Shop model.

Includes:
  • Shop profile (distributor, location, contact, revenue).
  • Auto-computed performance_level + bonus_percentage + owner_bv
    from the OWNER'S product BV.
  • Auto-computed customers count from carts/orders that belong to this shop.
"""

from decimal import Decimal

from django.db import models


# ------------------------------------------------------------------
# Performance tiers (OMA document, Section 7)
# ------------------------------------------------------------------
PERFORMANCE_TIERS = [
    ('Seed',       Decimal('1000'),   Decimal('2000'),   Decimal('3.00')),
    ('Bloom',      Decimal('2000'),   Decimal('5000'),   Decimal('3.50')),
    ('Garden',     Decimal('5000'),   Decimal('10000'),  Decimal('4.00')),
    ('Emerald',    Decimal('10000'),  Decimal('20000'),  Decimal('4.50')),
    ('Diamond',    Decimal('20000'),  Decimal('30000'),  Decimal('5.00')),
    ('Crown',      Decimal('30000'),  Decimal('40000'),  Decimal('5.50')),
    ('Gold Crown', Decimal('40000'),  None,               Decimal('6.00')),
]


def compute_performance(bv):
    """Return (level, bonus_percentage) for the given BV."""
    bv = Decimal(bv or 0)

    for level, min_bv, max_bv, bonus in PERFORMANCE_TIERS:
        if bv < min_bv:
            continue
        if max_bv is not None and bv >= max_bv:
            continue
        return (level, bonus)

    if bv < Decimal('1000'):
        return ('Seed', Decimal('3.00'))

    return ('Gold Crown', Decimal('6.00'))


class Shop(models.Model):
    PERFORMANCE_CHOICES = tuple(
        (name, name) for name, *_rest in PERFORMANCE_TIERS
    )

    STATUS_CHOICES = (
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('pending', 'Pending'),
    )

    distributor = models.ForeignKey(
        'distributors.Distributor',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='shops',
    )
    name = models.CharField(max_length=100)
    location = models.CharField(max_length=150)
    region = models.CharField(max_length=50)
    country = models.CharField(max_length=50)
    phone = models.CharField(max_length=20)
    email = models.EmailField(blank=True, null=True)

    # --------------------------------------------------------------
    # AUTO-COMPUTED — do not edit by hand
    # --------------------------------------------------------------
    performance_level = models.CharField(
        max_length=20, choices=PERFORMANCE_CHOICES, default='Seed',
        help_text='AUTO-COMPUTED from owner_bv.',
    )
    bonus_percentage = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('3.00'),
        help_text='AUTO-COMPUTED from performance_level.',
    )
    owner_bv = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        help_text='AUTO-COMPUTED: total BV the owner has sold.',
    )
    customers = models.PositiveIntegerField(
        default=0,
        help_text='AUTO-COMPUTED: distinct customers who shopped at this shop.',
    )

    # --------------------------------------------------------------
    # Editable business fields
    # --------------------------------------------------------------
    monthly_revenue = models.DecimalField(
        max_digits=12, decimal_places=2, default=0
    )
    rating = models.DecimalField(max_digits=3, decimal_places=2, default=0)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='pending'
    )
    established_date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'shops'
        ordering = ['-owner_bv', '-monthly_revenue']

    def __str__(self):
        return self.name

    # ==============================================================
    # COMPUTE HELPERS
    # ==============================================================

    def _compute_owner_bv(self):
        """
        Sum of (effective_bv × sales) across all products owned by
        this shop's distributor.
        """
        if not self.distributor_id:
            return Decimal('0')

        from products.models import Product

        total = Decimal('0')
        products = (
            Product.objects
            .filter(seller_id=self.distributor_id)
            .select_related('category')
        )
        for p in products:
            bv = p.bv if p.bv is not None else p.category.bv
            total += Decimal(bv) * Decimal(p.sales or 0)
        return total

    def _compute_customers(self):
        """
        Number of DISTINCT users who have a cart in this shop.

        Guests (carts with no `user`) count as one distinct "guest"
        per session_key.
        """
        from cart.models import Cart

        if not self.pk:
            return 0

        user_ids = (
            Cart.objects
            .filter(shop_id=self.pk, user__isnull=False)
            .values_list('user_id', flat=True)
            .distinct()
        )
        guest_keys = (
            Cart.objects
            .filter(shop_id=self.pk, user__isnull=True,
                    session_key__isnull=False)
            .exclude(session_key='')
            .values_list('session_key', flat=True)
            .distinct()
        )
        return len(set(user_ids)) + len(set(guest_keys))

    # ==============================================================
    # OVERRIDE save() — auto-compute everything
    # ==============================================================

    def save(self, *args, **kwargs):
        update_fields = kwargs.get('update_fields') or []

        # Allow explicit overrides from recompute helpers
        bypass = (
            'performance_level' in update_fields
            or 'bonus_percentage' in update_fields
            or 'owner_bv' in update_fields
            or 'customers' in update_fields
        )

        if not bypass:
            self.owner_bv = self._compute_owner_bv()
            self.customers = self._compute_customers()

            level, bonus = compute_performance(self.owner_bv)
            self.performance_level = level
            self.bonus_percentage = bonus

        super().save(*args, **kwargs)

    # ==============================================================
    # BULK RECOMPUTE
    # ==============================================================

    @classmethod
    def recompute_all_performance(cls):
        """Recompute owner_bv, level, bonus, and customers for every shop."""
        updated = 0
        for s in cls.objects.all():
            owner_bv = s._compute_owner_bv()
            customers = s._compute_customers()
            level, bonus = compute_performance(owner_bv)

            if (
                s.owner_bv != owner_bv
                or s.customers != customers
                or s.performance_level != level
                or Decimal(s.bonus_percentage) != bonus
            ):
                s.owner_bv = owner_bv
                s.customers = customers
                s.performance_level = level
                s.bonus_percentage = bonus
                super(Shop, s).save(
                    update_fields=[
                        'owner_bv',
                        'customers',
                        'performance_level',
                        'bonus_percentage',
                    ]
                )
                updated += 1
        return updated

    @classmethod
    def recompute_for_distributor(cls, distributor_id):
        """Recompute all shops owned by a specific distributor."""
        updated = 0
        for s in cls.objects.filter(distributor_id=distributor_id):
            owner_bv = s._compute_owner_bv()
            customers = s._compute_customers()
            level, bonus = compute_performance(owner_bv)

            s.owner_bv = owner_bv
            s.customers = customers
            s.performance_level = level
            s.bonus_percentage = bonus
            super(Shop, s).save(
                update_fields=[
                    'owner_bv',
                    'customers',
                    'performance_level',
                    'bonus_percentage',
                ]
            )
            updated += 1
        return updated

    @classmethod
    def recompute_for_shop(cls, shop_id):
        """Recompute one shop by id."""
        try:
            s = cls.objects.get(pk=shop_id)
        except cls.DoesNotExist:
            return 0

        owner_bv = s._compute_owner_bv()
        customers = s._compute_customers()
        level, bonus = compute_performance(owner_bv)

        s.owner_bv = owner_bv
        s.customers = customers
        s.performance_level = level
        s.bonus_percentage = bonus
        super(Shop, s).save(
            update_fields=[
                'owner_bv',
                'customers',
                'performance_level',
                'bonus_percentage',
            ]
        )
        return 1