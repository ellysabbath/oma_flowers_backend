from django.db import models

# Create your models here.
from django.db import models
from django.conf import settings

class Distributor(models.Model):
    RANK_CHOICES = (
        ('Royal Crown Director', 'Royal Crown Director'),
        ('Crown Director', 'Crown Director'),
        ('Director', 'Director'),
        ('Senior Manager', 'Senior Manager'),
        ('Manager', 'Manager'),
        ('Executive', 'Executive'),
        ('Senior Leader', 'Senior Leader'),
        ('Leader', 'Leader'),
        ('Builder', 'Builder'),
        ('Associate', 'Associate'),
    )
    
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='distributor_profile'
    )
    upline = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='downline_members'
    )
    rank = models.CharField(max_length=50, choices=RANK_CHOICES, default='Associate')
    level = models.PositiveSmallIntegerField(default=1)
    pbv = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    cgv = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    bonus_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=4.00)
    join_date = models.DateField(auto_now_add=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'distributors'
        ordering = ['-cgv']
    
    def __str__(self):
        return f"{self.user.full_name} - {self.rank}"
    
    @property
    def downline_count(self):
        return self.downline_members.count()
    
    @property
    def active_downline_count(self):
        return self.downline_members.filter(user__status='active').count()
    
    def get_full_hierarchy(self):
        """Get complete downline tree for this distributor"""
        hierarchy = []
        for downline in self.downline_members.select_related('user').all():
            hierarchy.append({
                'id': downline.id,
                'name': downline.user.full_name,
                'rank': downline.rank,
                'level': downline.level,
                'pbv': downline.pbv,
                'cgv': downline.cgv,
                'downline': downline.get_full_hierarchy()
            })
        return hierarchy