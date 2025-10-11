from django.db import models
from django.contrib.auth.models import User
from django.core.validators import RegexValidator

# Create your models here.

class Voter(models.Model):
    """Model to store eligible voters"""
    phone_validator = RegexValidator(
        regex=r'^\+\d{1,3}\d{4,14}$',
        message="Phone number must be in international format: +[country code][number] (e.g., +1234567890)"
    )
    
    phone_number = models.CharField(
        max_length=20,
        unique=True,
        validators=[phone_validator],
        help_text="Phone number in international format: +[country code][number]"
    )
    is_verified = models.BooleanField(default=False)
    has_voted = models.BooleanField(default=False)
    registered_at = models.DateTimeField(auto_now_add=True)
    voted_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-registered_at']
        verbose_name = 'Voter'
        verbose_name_plural = 'Voters'
    
    def __str__(self):
        return self.phone_number
    
    @staticmethod
    def normalize_phone_number(phone):
        """
        Normalize phone number to international format: +[country code][number]
        Accepts various formats and ensures it starts with +
        Examples: +1234567890, +447123456789, +232XXXXXXXX, etc.
        """
        # Remove all whitespace, dashes, parentheses, and other common separators
        phone = phone.strip()
        phone = phone.replace(' ', '').replace('-', '').replace('(', '').replace(')', '').replace('.', '')
        
        # Keep digits and plus sign
        raw = ''.join(c for c in phone if c.isdigit() or c == '+')
        
        # If it already starts with +, return as is
        if raw.startswith('+'):
            return raw
        
        # If it doesn't start with +, add it
        digits_only = ''.join(c for c in raw if c.isdigit())
        
        # Remove leading zeros (for local format numbers)
        digits_only = digits_only.lstrip('0')
        
        # Check if it looks like a Sierra Leone number (8 digits after removing leading zeros)
        # This maintains backward compatibility for users entering local SL numbers
        if len(digits_only) == 8:
            return '+232' + digits_only
        
        # If starts with 232 and has 11 digits total, it's Sierra Leone
        if digits_only.startswith('232') and len(digits_only) == 11:
            return '+' + digits_only
        
        # For all other cases, assume it's already a complete international number
        # Just add the + prefix
        return '+' + digits_only


class Candidate(models.Model):
    """Model to store candidates"""
    name = models.CharField(max_length=100)
    nickname = models.CharField(max_length=60, blank=True)
    position = models.CharField(max_length=80, default='Candidate')
    description = models.TextField(blank=True)
    photo = models.ImageField(upload_to='candidates/', null=True, blank=True)
    votes = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['name']
    
    def __str__(self):
        return f"{self.name} ({self.position})"


class Vote(models.Model):
    """Model to track votes"""
    voter = models.ForeignKey(Voter, on_delete=models.CASCADE)
    candidate = models.ForeignKey(Candidate, on_delete=models.CASCADE)
    voted_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['voter', 'candidate']
        ordering = ['-voted_at']
    
    def __str__(self):
        return f"{self.voter.phone_number} -> {self.candidate.name}"


class AdminUser(models.Model):
    """Link Django User to admin sessions for password management"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='admin_profile')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Admin User'
        verbose_name_plural = 'Admin Users'
    
    def __str__(self):
        return f"Admin: {self.user.username}"
