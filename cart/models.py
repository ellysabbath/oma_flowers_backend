from django.db import models

# Create your models here.
# cart/models.py
from django.db import models
from django.conf import settings


class Cart(models.Model):
    """
    A shopping cart.

    Can belong to:
      - a registered user (customer/distributor/admin) via `user`, OR
      - a guest via `session_key` (frontend supplies an anonymous token).

    Optionally tied to the shop and/or distributor that owns the storefront.
    """
    STATUS_CHOICES = (
        ('active', 'Active'),
        ('converted', 'Converted'),   # became an order
        ('abandoned', 'Abandoned'),
        ('expired', 'Expired'),
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
        ]

    def __str__(self):
        owner = self.user.email if self.user else (self.session_key or 'guest')
        return f"Cart #{self.id} — {owner}"

    @property
    def subtotal(self):
        return sum(item.subtotal for item in self.items.all())

    @property
    def total_bv(self):
        return sum(item.bv * item.quantity for item in self.items.all())

    @property
    def total_items(self):
        return sum(item.quantity for item in self.items.all())


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

    # Price & BV are snapshotted at time of adding so later product
    # changes don't silently alter the cart contents.
    price = models.DecimalField(max_digits=12, decimal_places=2)
    bv = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'cart_items'
        ordering = ['id']
        unique_together = ('cart', 'product')   # one line per product per cart

    def __str__(self):
        return f"{self.cart} — {self.product.name} x{self.quantity}"

    @property
    def subtotal(self):
        return self.price * self.quantity