# cart/models.py
"""
OMA Flowers — Cart & CartItem models.

Includes:
  • Cart (user or guest via session_key; optional distributor and shop)
  • Auto-generated unique alphanumeric `code` for every cart (e.g. OMA-A7B9-K2M4-P8QX)
  • CartItem (snapshot of price/BV at add-time)
  • Auto-recompute the shop's `customers` count whenever a cart changes
    (no signals — handled in Cart.save() and Cart.delete())
"""

import secrets

from django.db import models
from django.conf import settings


# ------------------------------------------------------------------
# Cart code generator
# ------------------------------------------------------------------
# Alphabet: uppercase letters (A-Z) + digits (2-9).
# We exclude 0/O and 1/I/L to avoid confusion when read out loud.
# 32 characters × 12 positions = 32^12 ≈ 1.15 × 10^18 combinations.
CART_CODE_ALPHABET = 'ABCDEFGHJKMNPQRSTUVWXYZ23456789'
CART_CODE_LENGTH = 12
CART_CODE_PREFIX = 'OMA-'          # 👈 changed from 'CART-'
CART_CODE_GROUP = 4                # split into groups of 4 → OMA-ABCD-EFGH-IJKL


def generate_cart_code():
    """
    Return a fresh code like 'OMA-A7B9-K2M4-P8QX'.
    Not checked for uniqueness here — the caller loops until it's free.
    """
    raw = ''.join(
        secrets.choice(CART_CODE_ALPHABET)
        for _ in range(CART_CODE_LENGTH)
    )
    groups = [
        raw[i:i + CART_CODE_GROUP]
        for i in range(0, CART_CODE_LENGTH, CART_CODE_GROUP)
    ]
    return f"{CART_CODE_PREFIX}{'-'.join(groups)}"


class Cart(models.Model):
    """
    A shopping cart.

    Can belong to:
      - a registered user (customer/distributor/admin) via `user`, OR
      - a guest via `session_key`.

    Optionally tied to a shop and/or distributor.
    """
    STATUS_CHOICES = (
        ('active', 'Active'),
        ('converted', 'Converted'),
        ('abandoned', 'Abandoned'),
        ('expired', 'Expired'),
    )

    # Unique, human-friendly cart identifier (OMA-XXXX-XXXX-XXXX)
    code = models.CharField(
        max_length=24,
        unique=True,
        null=True,
        db_index=True,
        editable=False,
        help_text='Auto-generated unique cart code (e.g. OMA-A7B9-K2M4-P8QX).',
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='carts',
    )
    distributor = models.ForeignKey(
        'distributors.Distributor',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='carts',
    )
    shop = models.ForeignKey(
        'shops.Shop',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='carts',
    )

    session_key = models.CharField(
        max_length=64,
        blank=True,
        null=True,
        db_index=True,
        help_text='Anonymous cart token for guests.',
    )

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    notes = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'carts'
        ordering = ['-updated_at']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['session_key', 'status']),
            models.Index(fields=['shop', 'status']),
            models.Index(fields=['code']),
        ]

    def __str__(self):
        owner = self.user.email if self.user else (self.session_key or 'guest')
        return f"{self.code} — {owner}"

    # ----------------------------------------------------------------
    # Code generation
    # ----------------------------------------------------------------
    @classmethod
    def _generate_unique_code(cls, max_attempts=10):
        """
        Return a code that isn't already taken.
        Raises RuntimeError if we can't find a free one in `max_attempts`
        (essentially impossible given the keyspace).
        """
        for _ in range(max_attempts):
            candidate = generate_cart_code()
            if not cls.objects.filter(code=candidate).exists():
                return candidate
        raise RuntimeError(
            'Unable to generate a unique cart code after multiple attempts.'
        )

    # ----------------------------------------------------------------
    # Derived properties
    # ----------------------------------------------------------------
    @property
    def subtotal(self):
        return sum(item.subtotal for item in self.items.all())

    @property
    def total_bv(self):
        return sum(item.bv * item.quantity for item in self.items.all())

    @property
    def total_items(self):
        return sum(item.quantity for item in self.items.all())

    # ----------------------------------------------------------------
    # Auto-generate the code + recompute shop customers on save
    # ----------------------------------------------------------------
    def save(self, *args, **kwargs):
        # 1) Generate code on first save only
        if not self.code:
            self.code = self._generate_unique_code()

        # 2) Snapshot the previous shop id to detect shop changes
        prev_shop_id = None
        if self.pk is not None:
            try:
                prev = Cart.objects.only('shop_id').get(pk=self.pk)
                prev_shop_id = prev.shop_id
            except Cart.DoesNotExist:
                prev_shop_id = None

        super().save(*args, **kwargs)

        # 3) Recompute shop customers
        from shops.models import Shop

        if self.shop_id:
            Shop.recompute_for_shop(self.shop_id)

        if prev_shop_id and prev_shop_id != self.shop_id:
            Shop.recompute_for_shop(prev_shop_id)

    # ----------------------------------------------------------------
    # Auto-recompute the shop's customers count on delete
    # ----------------------------------------------------------------
    def delete(self, *args, **kwargs):
        shop_id = self.shop_id
        super().delete(*args, **kwargs)

        if shop_id:
            from shops.models import Shop
            Shop.recompute_for_shop(shop_id)


class CartItem(models.Model):
    cart = models.ForeignKey(
        Cart,
        on_delete=models.CASCADE,
        related_name='items',
    )
    product = models.ForeignKey(
        'products.Product',
        on_delete=models.CASCADE,
        related_name='cart_items',
    )
    quantity = models.PositiveIntegerField(default=1)

    # Snapshot at add-time
    price = models.DecimalField(max_digits=12, decimal_places=2)
    bv = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'cart_items'
        ordering = ['id']
        unique_together = ('cart', 'product')

    def __str__(self):
        return f"{self.cart.code} — {self.product.name} x{self.quantity}"

    @property
    def subtotal(self):
        return self.price * self.quantity