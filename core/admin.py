from django.contrib import admin
from .models import Organization, UserProfile, Department, EmissionLog

# Register your models here so they appear in the Admin dashboard
admin.site.register(Organization)
admin.site.register(UserProfile)
admin.site.register(Department)
admin.site.register(EmissionLog)