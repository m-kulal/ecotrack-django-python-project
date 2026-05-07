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


# ─────────────────────────────────────────────────────────────────
# 6. Activity Log  (Manager data-entry model)
#    The save() method auto-calculates emissions_amount from quantity
#    using the emission factors below — the manager never types CO₂.
# ─────────────────────────────────────────────────────────────────
class ActivityLog(models.Model):

    CATEGORY_CHOICES = [
        ('Electricity', 'Electricity'),
        ('Water',       'Water'),
        ('Petrol',      'Petrol'),
        ('Diesel',      'Diesel'),
        ('Travel',      'Travel'),
    ]

    # Emission factors (kg CO₂ per unit consumed)
    EMISSION_FACTORS = {
        'Electricity': 0.85,   # kg CO₂ per kWh
        'Water':       0.30,   # kg CO₂ per litre
        'Petrol':      2.31,   # kg CO₂ per litre
        'Diesel':      2.68,   # kg CO₂ per litre
        'Travel':      0.18,   # kg CO₂ per km
    }

    department    = models.ForeignKey(
        Department, on_delete=models.CASCADE, related_name='activity_logs'
    )
    logged_by     = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name='activity_logs'
    )
    category      = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    quantity      = models.FloatField(help_text="Units consumed (kWh / litres / km)")
    emissions_amount = models.FloatField(
        editable=False,
        help_text="Auto-calculated: quantity × emission factor"
    )
    activity_date = models.DateField()
    date_recorded = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-activity_date', '-date_recorded']

    def save(self, *args, **kwargs):
        """
        Auto-calculate emissions_amount before every save.
        Uses the EMISSION_FACTORS dict — defaults to 0 for unknown categories
        so the record is always safe to store.
        """
        factor = self.EMISSION_FACTORS.get(self.category, 0)
        self.emissions_amount = round(self.quantity * factor, 4)
        super().save(*args, **kwargs)

    def __str__(self):
        return (
            f"{self.department.name} | {self.category} | "
            f"{self.quantity} units | {self.emissions_amount} kg CO₂ | {self.activity_date}"
        )
    
