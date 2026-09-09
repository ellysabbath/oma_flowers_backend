from django.db import models

# Create your models here.
from django.db import models
from django.conf import settings

class Bonus(models.Model):
    TYPE_CHOICES = (
        ('consistency', 'Consistency'),
        ('referral', 'Referral'),
        ('dynamic', 'Dynamic'),
        ('training', 'Training'),
        ('event', 'Event'),
        ('booking', 'Booking'),
        ('festival', 'Festival'),
        ('loyalty', 'Loyalty'),
    )
    
    STATUS_CHOICES = (
        ('paid', 'Paid'),
        ('pending', 'Pending'),
        ('processing', 'Processing'),
    )
    
    distributor = models.ForeignKey(
        'distributors.Distributor',
        on_delete=models.CASCADE,
        related_name='bonuses'
    )
    name = models.CharField(max_length=100)
    type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    description = models.TextField()
    month = models.CharField(max_length=15)
    year = models.PositiveSmallIntegerField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    payment_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'bonuses'
        ordering = ['-year', '-month']
    
    def __str__(self):
        return f"{self.distributor.user.full_name} - {self.name}"