from django.urls import path
from . import views

urlpatterns = [
    # Public Pages
    path('', views.landing_page, name='landing_page'),
    path('register/', views.register_organization, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    # Admin Panel
    path('dashboard/', views.dashboard, name='dashboard'),
    path('dashboard/departments/', views.manage_departments, name='department_list'),
    path('dashboard/analytics/', views.admin_analytics, name='admin_analytics'),

    # ── FIXED: was path('dashboard/goals/', views.dashboard, name='goals')
    #           Old entry pointed to views.dashboard and shadowed goal_tracking.
    #           Renamed to 'dashboard/goals/tracking/' so there is no clash,
    #           AND the name is now 'goal_tracking' so {% url 'goal_tracking' %}
    #           resolves correctly everywhere.
    path('dashboard/goals/tracking/', views.goal_tracking, name='goal_tracking'),

    path('dashboard/export/', views.dashboard, name='export_center'),
    path('branch/dashboard/', views.branch_dashboard, name='branch_dashboard'),
    path('dashboard/departments/edit/<int:dept_id>/', views.edit_department, name='edit_department'),
    path('dashboard/departments/delete/<int:dept_id>/', views.delete_department, name='delete_department'),

    # Organisation settings
    path('dashboard/organization/edit/', views.edit_organization, name='edit_organization'),

    # Manager (Department Head) Module
    path('manager/dashboard/',    views.manager_dashboard, name='manager_dashboard'),
    path('manager/add-activity/', views.add_activity,      name='add_activity'),
    path('manager/analytics/',    views.manager_analytics, name='manager_analytics'),
    path('activity/<int:log_id>/edit/',   views.edit_activity,   name='edit_activity'),
    path('delete-activity/<int:log_id>/', views.delete_activity, name='delete_activity'),
    path('manager/export/',    views.export_csv,  name='export_csv'),
    path('manager/insights/',  views.eco_insights, name='eco_insights'),
    path('admin/department/<int:dept_id>/insights/', views.department_detail, name='department_detail'),
]