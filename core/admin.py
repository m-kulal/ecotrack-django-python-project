from django.contrib import admin
from .models import Organization, UserProfile

# Register your models here.
admin.site.register(Organization)
admin.site.register(UserProfile)