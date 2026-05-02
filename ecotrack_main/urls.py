from django.contrib import admin
from django.urls import path, include  # 1. ADD 'include' HERE

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('core.urls')),     # 2. ADD THIS LINE
]