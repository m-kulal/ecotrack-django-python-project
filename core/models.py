from django.db import models
from django.contrib.auth.models import User

# 1. Organization
class Organization(models.Model):
    name = models.CharField(max_length=255)
    industry = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    country = models.CharField(max_length=100, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

# 2. User Profile
class UserProfile(models.Model):
    ROLE_CHOICES = (('ADMIN', 'Organization Admin'), ('STAFF', 'Department Head'))
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)

# 3. Department (NOW DEFINED BEFORE EMISSION LOG)
from django.contrib.auth.models import User

class Department(models.Model):
    name = models.CharField(max_length=100)
    location = models.CharField(max_length=255)
    organization = models.ForeignKey('Organization', on_delete=models.CASCADE)
    # ADD THIS LINE IF IT IS MISSING
    managed_by = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
# 4. Sustainability Goal
class SustainabilityGoal(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    title = models.CharField(max_length=255)
    target_value = models.FloatField()
    current_value = models.FloatField(default=0.0)
    deadline = models.DateField()

# 5. Emission Log
class EmissionLog(models.Model):
    department = models.ForeignKey(Department, on_delete=models.CASCADE) # This works now!
    source_type = models.CharField(max_length=50)
    quantity = models.FloatField()
    calculated_co2 = models.FloatField()
    date_recorded = models.DateTimeField(auto_now_add=True)