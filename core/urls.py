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
    path('branch/dashboard/', views.branch_dashboard, name='branch_dashboard'),
    path('dashboard/departments/edit/<int:dept_id>/', views.edit_department, name='edit_department'),
    path('dashboard/departments/delete/<int:dept_id>/', views.delete_department, name='delete_department'),

    # Organisation settings -- Admin can rename/update their org
    path('dashboard/organization/edit/', views.edit_organization, name='edit_organization'),

    # Manager (Department Head) Module
    path('manager/dashboard/',    views.manager_dashboard, name='manager_dashboard'),
    path('manager/add-activity/', views.add_activity,      name='add_activity'),
    path('manager/analytics/', views.manager_analytics, name='manager_analytics'),
]