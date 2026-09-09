from django.db import models

# Create your models here.
from django.db import models
from django.conf import settings

class Award(models.Model):
    CATEGORY_CHOICES = (
        ('legacy_circle', 'Legacy Circle'),
        ('legacy', 'Legacy'),
        ('annual', 'Annual'),
        ('special', 'Special'),
    )
    
    STATUS_CHOICES = (
        ('active', 'Active'),
        ('past', 'Past'),
        ('upcoming', 'Upcoming'),
    )
    
    distributor = models.ForeignKey(
        'distributors.Distributor',
        on_delete=models.CASCADE,
        related_name='awards'
    )
    name = models.CharField(max_length=100)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    prize = models.CharField(max_length=100)
    description = models.TextField()
    year = models.PositiveSmallIntegerField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    given_date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'awards'
        ordering = ['-year', '-given_date']
    
    def __str__(self):
        return f"{self.distributor.user.full_name} - {self.name}"