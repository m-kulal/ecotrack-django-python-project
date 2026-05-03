from django.urls import path
from . import views

urlpatterns = [
    # Public Pages
    path('', views.landing_page, name='landing_page'), # This is your http://127.0.0.1:8000/
    path('register/', views.register_organization, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    
    # Admin Panel
    path('dashboard/', views.dashboard, name='dashboard'),
    
    path('dashboard/departments/', views.manage_departments, name='department_list'),
    path('dashboard/analytics/', views.dashboard, name='analytics'),
    path('dashboard/goals/', views.dashboard, name='goals'),
    path('dashboard/export/', views.dashboard, name='export_center'),
]