from django.db import models

# Create your models here.
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
        related_name='commissions'
    )
    order = models.ForeignKey(
        'orders.Order',
        on_delete=models.CASCADE,
        related_name='commissions'
    )
    type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    source_distributor = models.ForeignKey(
        'distributors.Distributor',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='source_commissions'
    )
    percentage = models.DecimalField(max_digits=5, decimal_places=2)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    payment_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'commissions'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.distributor.user.full_name} - {self.type} - {self.amount}"