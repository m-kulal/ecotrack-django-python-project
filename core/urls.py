from django.urls import path
from . import views

urlpatterns = [
    path('register/', views.register_organization, name='register'),
    # Add this line below:
    path('login/', views.register_organization, name='login'), 
    path('', views.landing_page, name='landing'), # The Home Page
    path('register/', views.register_organization, name='register'),
]