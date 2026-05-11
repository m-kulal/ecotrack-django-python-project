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
    
# ═══════════════════════════════════════════════════════════════════
#  ADD THIS CLASS to models.py (below the existing ActivityLog model)
#
#  DashboardActivity is a lightweight event log written by your
#  Django code whenever something notable happens (new department,
#  goal updated, data submitted, etc.).  It replaces the hardcoded
#  skeleton rows in the "Activity Log" card on the admin dashboard.
#
#  HOW TO WRITE AN EVENT from any view:
#
#      from .models import DashboardActivity
#      DashboardActivity.objects.create(
#          organization = org,
#          description  = f"New department '{dept.name}' created.",
#      )
#
#  The 5 most-recent rows are passed to the dashboard template as
#  {{ recent_activities }}, where each object exposes:
#      .description  — human-readable event text
#      .timestamp    — DateTimeField (auto_now_add)
# ═══════════════════════════════════════════════════════════════════

class DashboardActivity(models.Model):
    """
    Lightweight event log for the Admin Dashboard "Activity Log" card.

    Each row represents one notable system event scoped to an
    Organisation.  The dashboard view fetches the 5 most recent
    rows and passes them to the template as `recent_activities`.
    """
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='dashboard_activities',
    )
    description = models.CharField(
        max_length=300,
        help_text="Human-readable event description shown in the dashboard."
    )
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']
        verbose_name        = 'Dashboard Activity'
        verbose_name_plural = 'Dashboard Activities'

    def __str__(self):
        return f"[{self.timestamp:%Y-%m-%d %H:%M}] {self.description}"


# ─────────────────────────────────────────────────────────────────
#  HELPER — call this utility function from any view to record
#  events without duplicating the import / create pattern everywhere.
# ─────────────────────────────────────────────────────────────────
def log_dashboard_event(organization, description: str) -> None:
    """
    Create a DashboardActivity row.  Silently swallows errors so
    a logging failure never breaks the primary operation.

    Usage:
        from .models import log_dashboard_event
        log_dashboard_event(org, f"Manager '{user.username}' submitted data.")
    """
    try:
        DashboardActivity.objects.create(
            organization=organization,
            description=description[:300],
        )
    except Exception:
        pass   # logging must never crash the caller
    
# ═══════════════════════════════════════════════════════════════════
#  ADD THIS CLASS to models.py — paste it after DashboardActivity
# ═══════════════════════════════════════════════════════════════════

class CarbonGoal(models.Model):
    """
    An organisation-level emission reduction target.

    The admin sets a `target_kg` (kg CO₂) over a date range.
    The view calculates progress as:
        progress_pct = (total_actual_kg / target_kg) × 100

    A value below 100 % is good (under target).
    A value above 100 % means the organisation has exceeded the cap.
    """

    STATUS_CHOICES = [
        ('ACTIVE',    'Active'),
        ('ACHIEVED',  'Achieved'),
        ('FAILED',    'Failed'),
        ('UPCOMING',  'Upcoming'),
    ]

    organization = models.ForeignKey(
        'Organization',
        on_delete=models.CASCADE,
        related_name='carbon_goals',
    )
    title = models.CharField(
        max_length=200,
        help_text="Short goal name shown in the dashboard (e.g. 'Q3 2025 Reduction Target').",
    )
    description = models.TextField(
        blank=True, null=True,
        help_text="Optional longer description / notes.",
    )
    target_kg = models.FloatField(
        help_text="Maximum allowable CO₂ in kg for the entire goal period.",
    )
    start_date = models.DateField(
        help_text="First day of the measurement window.",
    )
    end_date = models.DateField(
        help_text="Last day of the measurement window.",
    )
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default='ACTIVE',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-start_date']
        verbose_name        = 'Carbon Goal'
        verbose_name_plural = 'Carbon Goals'

    def __str__(self):
        return f"{self.organization.name} — {self.title} ({self.start_date} → {self.end_date})"