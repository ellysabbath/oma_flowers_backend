from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone

class User(AbstractUser):
    USER_TYPE_CHOICES = (
        ('customer', 'Customer'),
        ('distributor', 'Distributor'),
        ('admin', 'Admin'),
    )
    
    STATUS_CHOICES = (
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('pending', 'Pending'),
        ('banned', 'Banned'),
    )
    
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    country = models.CharField(max_length=50, blank=True, null=True)
    region = models.CharField(max_length=50, blank=True, null=True)
    city = models.CharField(max_length=50, blank=True, null=True)
    profile_picture = models.TextField(blank=True, null=True)
    user_type = models.CharField(max_length=20, choices=USER_TYPE_CHOICES, default='customer')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    email_verified = models.BooleanField(default=False)
    email_verified_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username', 'first_name', 'last_name']
    
    class Meta:
        db_table = 'users'
        ordering = ['-created_at']
    
    def __str__(self):
        return self.email
    
    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()
    
    def is_distributor(self):
        return self.user_type == 'distributor'
    
    def is_admin(self):
        return self.user_type == 'admin'
    
    def is_customer(self):
        return self.user_type == 'customer'


class VerificationCode(models.Model):
    VERIFICATION_TYPES = (
        ('email', 'Email Verification'),
        ('password_reset', 'Password Reset'),
    )
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='verification_codes'
    )
    code = models.CharField(max_length=6)
    type = models.CharField(max_length=20, choices=VERIFICATION_TYPES)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)
    
    class Meta:
        db_table = 'verification_codes'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'code', 'type', 'is_used']),
        ]
    
    def __str__(self):
        return f"{self.user.email} - {self.code}"
    
    def is_valid(self):
        return not self.is_used and timezone.now() < self.expires_at