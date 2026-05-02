from django.db import models
from django.contrib.auth.models import User

# 1. The Organization (Tenant)
class Organization(models.Model):
    name = models.CharField(max_length=255)
    industry = models.CharField(max_length=100)
    # ADD THESE TWO LINES:
    description = models.TextField(blank=True, null=True)
    country = models.CharField(max_length=100, blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

# 2. User Profile (Linking Users to an Org and Role)
class UserProfile(models.Model):
    ROLE_CHOICES = (
        ('ADMIN', 'Organization Admin'),
        ('STAFF', 'Department Head'),
    )
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)

# 3. Departments (Created by Admin)
class Department(models.Model):
    name = models.CharField(max_length=100)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.name} ({self.organization.name})"

# 4. Emission Logs (The Carbon Data)
class EmissionLog(models.Model):
    department = models.ForeignKey(Department, on_delete=models.CASCADE)
    source_type = models.CharField(max_length=50) # Electricity, Fuel, etc.
    quantity = models.FloatField()
    calculated_co2 = models.FloatField()
    date_recorded = models.DateField(auto_now_add=True)