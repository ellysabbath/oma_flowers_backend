from django.db import models

# Create your models here.
from django.db import models
from django.conf import settings

class Shop(models.Model):
    PERFORMANCE_CHOICES = (
        ('Seed', 'Seed'),
        ('Bloom', 'Bloom'),
        ('Garden', 'Garden'),
        ('Emerald', 'Emerald'),
        ('Diamond', 'Diamond'),
        ('Crown', 'Crown'),
        ('Gold Crown', 'Gold Crown'),
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
        related_name='shops'
    )
    name = models.CharField(max_length=100)
    location = models.CharField(max_length=150)
    region = models.CharField(max_length=50)
    country = models.CharField(max_length=50)
    phone = models.CharField(max_length=20)
    email = models.EmailField(blank=True, null=True)
    performance_level = models.CharField(max_length=20, choices=PERFORMANCE_CHOICES, default='Seed')
    monthly_revenue = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    bonus_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=3.50)
    customers = models.PositiveIntegerField(default=0)
    rating = models.DecimalField(max_digits=3, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    established_date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'shops'
        ordering = ['-monthly_revenue']
    
    def __str__(self):
        return self.name