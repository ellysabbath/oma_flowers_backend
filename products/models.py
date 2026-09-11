# products/models.py
"""
OMA Flowers — Product & Category models.

Includes:
  • Category (SKUs like CCA, LCA, etc.)
  • Product with optional seller (distributor who earns PBV/CGV)
  • Auto-recomputes the seller's shops whenever sales, seller, or BV changes
    (no signals — handled in Product.save() and Product.delete())
"""

from django.db import models


class Category(models.Model):
    """
    One of the OMA Flowers sellable SKUs.

    Examples:
        CCA  Classic Class A Flower  —  6 BV,  TSh 56,000
        LCA  Luxury  Class A Flower  — 20 BV,  TSh 250,000
    """

    TYPE_CHOICES = (
        ('Classic', 'Classic'),
        ('Luxury', 'Luxury'),
    )

    CLASS_CHOICES = (
        ('A', 'A — Table / Home / Office / Church flowers'),
        ('B', 'B — Wedding / Graduation flowers'),
        ('C', 'C — Gift & Premium flower packages'),
        ('D', 'D — Decoration kits & Event decoration'),
    )

    STATUS_CHOICES = (
        ('active', 'Active'),
        ('inactive', 'Inactive'),
    )

    name = models.CharField(max_length=50, unique=True)
    code = models.CharField(max_length=10, unique=True)
    description = models.TextField(blank=True, null=True)
    type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    class_type = models.CharField(max_length=1, choices=CLASS_CHOICES)
    bv = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'categories'
        ordering = ['type', 'class_type']
        verbose_name_plural = 'Categories'

    def __str__(self):
        return f"{self.code} — {self.name} ({self.bv} BV, TSh {self.price})"


class Product(models.Model):
    STATUS_CHOICES = (
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('coming_soon', 'Coming Soon'),
    )

    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        related_name='products',
    )

    # The distributor who earns PBV/CGV when this product sells
    seller = models.ForeignKey(
        'distributors.Distributor',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='products_sold',
        help_text='The distributor who earns PBV/CGV when this product is sold.',
    )

    sku = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    price = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        help_text='Leave blank to inherit from the category.',
    )
    bv = models.PositiveIntegerField(
        null=True, blank=True,
        help_text='Leave blank to inherit from the category.',
    )
    stock = models.PositiveIntegerField(default=0)
    sales = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')

    product_picture = models.TextField(
        blank=True, null=True,
        help_text='Base64 encoded image (data:image/...;base64,...)',
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'products'
        ordering = ['-created_at']

    def __str__(self):
        return self.name

    # ----------------------------------------------------------------
    # Derived helpers
    # ----------------------------------------------------------------

    @property
    def effective_price(self):
        return self.price if self.price is not None else self.category.price

    @property
    def effective_bv(self):
        return self.bv if self.bv is not None else self.category.bv

    @property
    def seller_name(self):
        if not self.seller:
            return None
        return (
            getattr(self.seller, 'full_name', None)
            or getattr(self.seller.user, 'full_name', None)
            or getattr(self.seller.user, 'email', None)
        )

    # ----------------------------------------------------------------
    # Auto-recompute the seller's shops on every save
    # ----------------------------------------------------------------
    def save(self, *args, **kwargs):
        # Snapshot previous seller/sales/bv to detect meaningful changes
        prev_seller_id = None
        prev_sales = None
        prev_bv = None

        if self.pk is not None:
            try:
                prev = Product.objects.only(
                    'seller_id', 'sales', 'bv'
                ).get(pk=self.pk)
                prev_seller_id = prev.seller_id
                prev_sales = prev.sales
                prev_bv = prev.bv
            except Product.DoesNotExist:
                prev = None

        super().save(*args, **kwargs)

        seller_changed = prev_seller_id != self.seller_id
        sales_changed = prev_sales != self.sales
        bv_changed = prev_bv != self.bv

        if not (seller_changed or sales_changed or bv_changed):
            return

        # Recompute shops for the current seller (if any)
        from shops.models import Shop

        if self.seller_id:
            Shop.recompute_for_distributor(self.seller_id)

        # If the seller changed, recompute the old seller's shops too
        if seller_changed and prev_seller_id and prev_seller_id != self.seller_id:
            Shop.recompute_for_distributor(prev_seller_id)

    # ----------------------------------------------------------------
    # Auto-recompute the seller's shops when a product is deleted
    # ----------------------------------------------------------------
    def delete(self, *args, **kwargs):
        seller_id = self.seller_id
        super().delete(*args, **kwargs)

        if seller_id:
            from shops.models import Shop
            Shop.recompute_for_distributor(seller_id)