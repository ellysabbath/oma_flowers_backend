# commissions/models.py
from django.db import models
from django.conf import settings


class Commission(models.Model):
    TYPE_CHOICES = (
        ('personal', 'Personal'),
        ('differential', 'Differential'),
    )

    STATUS_CHOICES = (
        ('paid', 'Paid'),
        ('pending', 'Pending'),
        ('processing', 'Processing'),
    )

    distributor = models.ForeignKey(
        'distributors.Distributor',
        on_delete=models.CASCADE,
        related_name='commissions',
    )
    order = models.ForeignKey(
        'orders.Order',
        on_delete=models.CASCADE,
        related_name='commissions',
        null=True,
        blank=True,
    )
    type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    source_distributor = models.ForeignKey(
        'distributors.Distributor',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='source_commissions',
    )
    pbv = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        help_text='The BV that this commission was calculated from.',
    )
    percentage = models.DecimalField(max_digits=5, decimal_places=2)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='pending'
    )
    payment_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'commissions'
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['distributor', 'type', 'source_distributor'],
                condition=models.Q(source_distributor__isnull=False),
                name='unique_differential_per_source',
            ),
        ]

    def __str__(self):
        return (
            f"{self.distributor.user.full_name} - "
            f"{self.type} - {self.amount}"
        )