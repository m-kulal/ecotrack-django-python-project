# At the top of views.py, add to the existing import block:
import json
from datetime import date
from dateutil.relativedelta import relativedelta
from django.db.models.functions import TruncMonth
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db import transaction
from django.db.models import Q, Sum
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.utils import timezone

from .models import UserProfile, Organization, Department, ActivityLog
from .forms import UserRegistrationForm, OrganizationForm


# ─────────────────────────────────────────────────────────────────
# 1. Landing Page
# ─────────────────────────────────────────────────────────────────
def landing_page(request):
    return render(request, 'core/landing.html')


# ─────────────────────────────────────────────────────────────────
# 2. Registration Logic (Admin + Org Creation)
# ─────────────────────────────────────────────────────────────────
def register_organization(request):
    if request.method == "POST":
        user_form = UserRegistrationForm(request.POST)
        org_form  = OrganizationForm(request.POST)

        if user_form.is_valid() and org_form.is_valid():
            try:
                with transaction.atomic():
                    organization = org_form.save()

                    cd   = user_form.cleaned_data
                    user = User.objects.create_user(
                        username   = cd["username"],
                        email      = cd["email"],
                        password   = cd["password"],
                        first_name = cd["first_name"],
                        last_name  = cd["last_name"],
                    )

                    UserProfile.objects.create(
                        user         = user,
                        organization = organization,
                        role         = "ADMIN",
                    )

                messages.success(request, "Organisation registered! You can now log in.")
                return redirect("login")

            except Exception as exc:
                messages.error(request, f"Registration error: {exc}")
    else:
        user_form = UserRegistrationForm()
        org_form  = OrganizationForm()

    return render(request, "core/register.html", {
        "user_form": user_form,
        "org_form":  org_form,
    })


# ─────────────────────────────────────────────────────────────────
# 3. Login
# ─────────────────────────────────────────────────────────────────
def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user     = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)

            # Admin / Superuser → full dashboard
            if (hasattr(user, 'userprofile') and user.userprofile.role == 'ADMIN') \
                    or user.is_superuser:
                return redirect('dashboard')

            # Department Manager → manager dashboard
            if Department.objects.filter(managed_by=user).exists():
                return redirect('manager_dashboard')

            # Fallback
            return redirect('dashboard')
        else:
            messages.error(request, "Invalid username or password.")

    return render(request, 'core/login.html')


# ─────────────────────────────────────────────────────────────────
# 4. Logout
# ─────────────────────────────────────────────────────────────────
def logout_view(request):
    logout(request)
    return redirect('landing_page')


# ═══════════════════════════════════════════════════════════════════
#  PASTE THESE ADDITIONS INTO views.py
#
#  1. Replace the existing `dashboard` function entirely.
#  2. Add the `department_detail` function below the existing views.
#  3. Ensure `DashboardActivity` model is added to models.py (see
#     models_addition.py).
#  4. Add the new URL to urls.py (see urls_addition.py).
# ═══════════════════════════════════════════════════════════════════

# ── New top-level imports to ADD (merge with existing import block) ──
# from django.core.cache import cache            ← already present
# from .utils import get_gemini_recommendations  ← already present
# import os                                      ← add this
# from dateutil.relativedelta import relativedelta ← already present

import os   # add to the import block at top of views.py


# ─────────────────────────────────────────────────────────────────
# 5. Admin Dashboard  ← REPLACE the existing dashboard() function
#    with this version.
#
#    New additions vs the old stub:
#      • total_emissions  — real sum from ActivityLog
#      • emissions_change — month-on-month % delta with arrow prefix
#      • limit_* fields   — computed against SustainabilityGoal
#      • chart_labels / chart_co2 / chart_energy — 6-month JSON
#        series for the Chart.js graph in dashboard.html
#      • dept.emissions / dept.submitted — annotated onto each dept
#      • recent_activities — last 5 DashboardActivity rows
# ─────────────────────────────────────────────────────────────────
@login_required
def dashboard(request):
    # Managers must go to their own dashboard
    if Department.objects.filter(managed_by=request.user).exists():
        return redirect('manager_dashboard')

    admin_profile = getattr(request.user, 'userprofile', None)
    org_name      = admin_profile.organization.name if admin_profile else "EcoTrack"
    org           = admin_profile.organization       if admin_profile else None

    now = timezone.now()

    # ── Scoped queryset ───────────────────────────────────────────
    if org:
        org_logs = ActivityLog.objects.filter(department__organization=org)
    else:
        org_logs = ActivityLog.objects.none()

    # ── Card 1: Total Emissions (all-time, tCO₂) ─────────────────
    total_emissions_kg = (
        org_logs.aggregate(t=Sum('emissions_amount'))['t'] or 0.0
    )
    total_emissions = round(total_emissions_kg / 1000, 2)   # kg → tCO₂

    # ── Card 1b: Month-on-month % change ─────────────────────────
    current_month_kg = (
        org_logs
        .filter(activity_date__year=now.year, activity_date__month=now.month)
        .aggregate(t=Sum('emissions_amount'))['t'] or 0.0
    )
    last_month_dt = now - relativedelta(months=1)
    last_month_kg = (
        org_logs
        .filter(
            activity_date__year=last_month_dt.year,
            activity_date__month=last_month_dt.month,
        )
        .aggregate(t=Sum('emissions_amount'))['t'] or 0.0
    )

    if last_month_kg > 0:
        delta_pct = round(((current_month_kg - last_month_kg) / last_month_kg) * 100, 1)
        arrow     = '↓' if delta_pct <= 0 else '↑'
        sign      = abs(delta_pct)
        # Positive delta = more emissions = bad (shown in danger colour via template tag)
        emissions_change     = f"{arrow} {sign}% from last month"
        emissions_change_good = delta_pct <= 0   # True → accent green, False → danger red
    else:
        emissions_change      = "No prior month data"
        emissions_change_good = True

    # ── Card 2: Carbon Limit (from SustainabilityGoal) ────────────
    # Use the most recent goal for this org as the monthly cap.
    from .models import SustainabilityGoal   # local import to avoid circular
    goal = (
        SustainabilityGoal.objects
        .filter(organization=org)
        .order_by('-deadline')
        .first()
        if org else None
    )

    if goal and goal.target_value > 0:
        limit_kg         = goal.target_value * 1000   # tCO₂ → kg
        limit_pct_raw    = (current_month_kg / limit_kg) * 100
        limit_percentage = min(round(limit_pct_raw, 1), 100)
        limit_bar_width  = f"{limit_percentage}%"
        limit_bar_color  = '#ff4444' if limit_pct_raw >= 90 else (
                           '#ffaa00' if limit_pct_raw >= 70 else '#39ff14')
        limit_text_color = ('var(--danger)' if limit_pct_raw >= 90 else
                            '#ffaa00'       if limit_pct_raw >= 70 else 'var(--accent)')
        show_limit_warning = limit_pct_raw >= 90
        carbon_limit_label = f"{round(goal.target_value, 1)} tCO₂ / mo cap"
    else:
        limit_percentage   = 0
        limit_bar_width    = '0%'
        limit_bar_color    = '#39ff14'
        limit_text_color   = 'var(--accent)'
        show_limit_warning = False
        carbon_limit_label = 'No goal set'

    # ── Card 3: Active Departments ────────────────────────────────
    dept_qs = (
        Department.objects.filter(organization=org)
        if org else Department.objects.none()
    )
    dept_count = dept_qs.count()

    # ── Chart: 6-month CO₂ time-series ───────────────────────────
    chart_labels = []
    chart_co2    = []    # monthly total kg CO₂

    for offset in range(5, -1, -1):
        point = now - relativedelta(months=offset)
        label = point.strftime('%b %Y')
        total = (
            org_logs
            .filter(activity_date__year=point.year, activity_date__month=point.month)
            .aggregate(t=Sum('emissions_amount'))['t'] or 0.0
        )
        chart_labels.append(label)
        chart_co2.append(round(total, 2))

    # ── Departments table: annotate emissions + submitted flag ────
    # "submitted" = department has at least one log in the current month
    current_month_dept_ids = set(
        org_logs
        .filter(activity_date__year=now.year, activity_date__month=now.month)
        .values_list('department_id', flat=True)
        .distinct()
    )

    dept_emissions = (
        org_logs
        .values('department_id')
        .annotate(total=Sum('emissions_amount'))
    )
    dept_emissions_map = {
        row['department_id']: round(row['total'] / 1000, 2)
        for row in dept_emissions
    }

    departments_display = []
    for dept in dept_qs.order_by('name'):
        dept.emissions  = dept_emissions_map.get(dept.id)
        dept.submitted  = dept.id in current_month_dept_ids
        departments_display.append(dept)

    # ── Activity Log: last 5 DashboardActivity rows ───────────────
    from .models import DashboardActivity   # local import
    recent_activities = DashboardActivity.objects.filter(
        organization=org
    ).order_by('-timestamp')[:5] if org else []

    return render(request, 'admin/dashboard.html', {
        'admin_profile':         admin_profile,
        'org_name':              org_name,
        'departments':           departments_display,

        # Stat cards
        'total_emissions':       total_emissions,
        'emissions_change':      emissions_change,
        'emissions_change_good': emissions_change_good,
        'dept_count':            dept_count,

        # Carbon limit card
        'limit_percentage':      limit_percentage,
        'limit_bar_width':       limit_bar_width,
        'limit_bar_color':       limit_bar_color,
        'limit_text_color':      limit_text_color,
        'show_limit_warning':    show_limit_warning,
        'carbon_limit_label':    carbon_limit_label,

        # Chart.js data — use |safe in template
        'chart_labels':          json.dumps(chart_labels),
        'chart_co2':             json.dumps(chart_co2),

        # Activity log
        'recent_activities':     recent_activities,
    })


# ─────────────────────────────────────────────────────────────────
# NEW: Department Detail + Gemini AI Insight
#      URL: /admin/department/<id>/insights/
#      Access: admin only (UserProfile.role == ADMIN or is_superuser)
#
#      Template: admin/department_detail.html
# ─────────────────────────────────────────────────────────────────
@login_required
def department_detail(request, dept_id):
    """
    Detailed analytics for a single department, plus a Gemini AI
    sustainability recommendation.

    Security:
    - The view is restricted to org admins / superusers.
    - The department must belong to the admin's own organisation.

    Data pipeline:
    1. Resolve admin's org; 404 if dept not in that org.
    2. Compute 6-month rolling emissions totals (for the chart).
    3. Compute current-month category breakdown.
    4. Build a plain-text stats summary.
    5. Fetch Gemini insight (cached 6 h per dept).
    6. Render department_detail.html.
    """

    # ── Guard: admins only ────────────────────────────────────────
    admin_profile = getattr(request.user, 'userprofile', None)
    is_admin = (
        request.user.is_superuser
        or (admin_profile and admin_profile.role == 'ADMIN')
    )
    if not is_admin:
        messages.error(request, "Admin access required.")
        return redirect('dashboard')

    # ── Resolve department — must belong to admin's org ───────────
    org = admin_profile.organization if admin_profile else None
    dept = get_object_or_404(Department, id=dept_id, organization=org)

    org_name = org.name if org else "EcoTrack"
    now      = timezone.now()

    # ── Base queryset: only this department's logs ────────────────
    dept_logs = ActivityLog.objects.filter(department=dept)

    # ── 6-month rolling chart data ────────────────────────────────
    chart_labels = []
    chart_co2    = []
    for offset in range(5, -1, -1):
        point = now - relativedelta(months=offset)
        total = (
            dept_logs
            .filter(activity_date__year=point.year, activity_date__month=point.month)
            .aggregate(t=Sum('emissions_amount'))['t'] or 0.0
        )
        chart_labels.append(point.strftime('%b %Y'))
        chart_co2.append(round(total, 2))

    # ── Category breakdown (current month) ───────────────────────
    categories = ['Electricity', 'Water', 'Petrol', 'Diesel', 'Travel']
    current_logs = dept_logs.filter(
        activity_date__year=now.year, activity_date__month=now.month
    )
    category_totals = {}
    for cat in categories:
        s = current_logs.filter(category=cat).aggregate(
            t=Sum('emissions_amount')
        )['t'] or 0.0
        category_totals[cat] = round(s, 2)

    top_category     = max(category_totals, key=category_totals.get)
    top_category_val = category_totals[top_category]

    # ── Month-on-month delta ──────────────────────────────────────
    last_month_dt = now - relativedelta(months=1)
    current_m_kg  = chart_co2[-1] if chart_co2 else 0.0
    last_m_kg     = chart_co2[-2] if len(chart_co2) >= 2 else 0.0

    if last_m_kg > 0:
        delta_pct = round(((current_m_kg - last_m_kg) / last_m_kg) * 100, 1)
        arrow     = '↓' if delta_pct <= 0 else '↑'
        delta_str = f"{arrow} {abs(delta_pct)}% from {last_month_dt.strftime('%B')}"
        delta_good = delta_pct <= 0
    else:
        delta_str  = "No prior month data"
        delta_good = True

    # ── All-time totals ───────────────────────────────────────────
    all_time_kg = (
        dept_logs.aggregate(t=Sum('emissions_amount'))['t'] or 0.0
    )
    all_time_tco2 = round(all_time_kg / 1000, 2)

    # ── AI Insight — cached per-department for 6 hours ───────────
    cache_key = f"dept_ai_insight_{dept.id}"

    if request.GET.get('refresh') == '1':
        cache.delete(cache_key)

    ai_insight = cache.get(cache_key)

    if ai_insight is None:
        has_data = any(v > 0 for v in chart_co2)
        if has_data:
            stats_text = (
                f"Organisation: {org_name}\n"
                f"Department: {dept.name}\n"
                f"Location: {dept.location or 'N/A'}\n"
                f"Report month: {now.strftime('%B %Y')}\n\n"
                f"Current month total: {current_m_kg} kg CO₂\n"
                f"Previous month total: {last_m_kg} kg CO₂\n"
                f"Month-on-month change: {delta_str}\n\n"
                f"Top emitting category: {top_category} ({top_category_val} kg CO₂)\n\n"
                f"Category breakdown (current month):\n"
                + "\n".join(
                    f"  • {cat}: {val} kg CO₂"
                    for cat, val in category_totals.items()
                )
                + f"\n\nLast 6 months (oldest → newest):\n"
                + "\n".join(
                    f"  • {lbl}: {val} kg CO₂"
                    for lbl, val in zip(chart_labels, chart_co2)
                )
            )
            ai_insight = get_gemini_recommendations(stats_text)
        else:
            ai_insight = (
                "No emissions data has been recorded for this department yet. "
                "Ask the department manager to log activity data, then return "
                "here for AI-powered sustainability recommendations."
            )
        cache.set(cache_key, ai_insight, timeout=21_600)

    # ── Recent logs ───────────────────────────────────────────────
    recent_logs = dept_logs.order_by('-activity_date', '-date_recorded')[:10]

    return render(request, 'admin/department_detail.html', {
        'admin_profile':    admin_profile,
        'org_name':         org_name,
        'dept':             dept,

        # Chart
        'chart_labels':     json.dumps(chart_labels),
        'chart_co2':        json.dumps(chart_co2),

        # Stat cards
        'all_time_tco2':    all_time_tco2,
        'current_m_kg':     round(current_m_kg, 2),
        'delta_str':        delta_str,
        'delta_good':       delta_good,
        'top_category':     top_category,
        'top_category_val': top_category_val,

        # Category table
        'category_totals':  category_totals,

        # AI
        'ai_insight':       ai_insight,

        # Log table
        'recent_logs':      recent_logs,
    })

# ─────────────────────────────────────────────────────────────────
# 6. Branch (Manager) Dashboard — legacy redirect kept for safety
# ─────────────────────────────────────────────────────────────────
@login_required
def branch_dashboard(request):
    """
    Legacy entry point.  All new code redirects to manager_dashboard.
    Kept so any bookmarked /branch/dashboard/ URLs still work.
    """
    return redirect('manager_dashboard')


# ─────────────────────────────────────────────────────────────────
# 11. Manager Dashboard
#     Shows the manager's own department data only.
#     Computes current-month total emissions for the summary card.
# ─────────────────────────────────────────────────────────────────
@login_required
def manager_dashboard(request):
    # Resolve this manager's department
    dept = Department.objects.filter(managed_by=request.user).first()
    if not dept:
        # Not a manager — send them to the admin area
        return redirect('dashboard')

    # ── Branding: org name for header chip ────────────────────────
    # Managers don't have a UserProfile, so we walk through the dept.
    org_name = dept.organization.name if dept.organization else "EcoTrack"

    # ── All activity logs for this department ─────────────────────
    all_logs = ActivityLog.objects.filter(department=dept)

    # ── Current-month totals ──────────────────────────────────────
    now               = timezone.now()
    monthly_logs      = all_logs.filter(
        activity_date__year  = now.year,
        activity_date__month = now.month,
    )
    monthly_emissions = monthly_logs.aggregate(
        total=Sum('emissions_amount')
    )['total'] or 0.0

    # ── Per-category breakdown (current month) ────────────────────
    categories = ['Electricity', 'Water', 'Petrol', 'Diesel', 'Travel']
    category_totals = {}
    for cat in categories:
        cat_total = monthly_logs.filter(category=cat).aggregate(
            total=Sum('emissions_amount')
        )['total'] or 0.0
        category_totals[cat] = round(cat_total, 2)

    # ── Last 10 entries for the activity table ────────────────────
    recent_logs = all_logs[:10]

    return render(request, 'manager/dashboard.html', {
        'dept':              dept,
        'org_name':          org_name,
        'manager_name':      request.user.username,
        'monthly_emissions': round(monthly_emissions, 2),
        'log_count':         all_logs.count(),
        'monthly_count':     monthly_logs.count(),
        'category_totals':   category_totals,
        'recent_logs':       recent_logs,
        'current_month':     now.strftime('%B %Y'),
    })


# ─────────────────────────────────────────────────────────────────
# 12. Add Activity Log
#     Handles the data-entry form POST.
#     Validates quantity > 0; emissions_amount is auto-calculated
#     by ActivityLog.save() — the view never touches that field.
# ─────────────────────────────────────────────────────────────────
@login_required
def add_activity(request):
    dept = Department.objects.filter(managed_by=request.user).first()
    if not dept:
        return redirect('dashboard')

    org_name = dept.organization.name if dept.organization else "EcoTrack"

    if request.method == 'POST':
        category      = request.POST.get('category', '').strip()
        quantity_raw  = request.POST.get('quantity', '').strip()
        activity_date = request.POST.get('activity_date', '').strip()

        # ── Validation ────────────────────────────────────────────
        valid_categories = ['Electricity', 'Water', 'Petrol', 'Diesel', 'Travel']
        errors = []

        if not category or category not in valid_categories:
            errors.append("Please select a valid category.")

        if not activity_date:
            errors.append("Activity date is required.")

        quantity = None
        if not quantity_raw:
            errors.append("Quantity is required.")
        else:
            try:
                quantity = float(quantity_raw)
                if quantity <= 0:
                    errors.append("Quantity must be a positive number greater than zero.")
            except ValueError:
                errors.append("Quantity must be a valid number.")

        if errors:
            for err in errors:
                messages.error(request, err)
        else:
            # ── Save — emissions_amount auto-set by model.save() ──
            ActivityLog.objects.create(
                department    = dept,
                logged_by     = request.user,
                category      = category,
                quantity      = quantity,
                activity_date = activity_date,
            )
            messages.success(
                request,
                f"Activity logged: {quantity} units of {category} — "
                f"CO₂ calculated automatically."
            )
            return redirect('manager_dashboard')

    return render(request, 'manager/add_activity.html', {
        'dept':     dept,
        'org_name': org_name,
        'categories': ['Electricity', 'Water', 'Petrol', 'Diesel', 'Travel'],
    })


# ─────────────────────────────────────────────────────────────────
# 7. Manage Departments  (list + add)
#
#    BUG FIXES applied here:
#    a) Removed the duplicate function definition that was shadowing
#       this one (Python silently uses the LAST definition, so the
#       first, broken version was never called — but it caused
#       confusion and unpredictable behaviour).
#    b) request.POST.get('email') now matches name="email" in HTML.
#    c) request.POST.get('password') matches name="password" in HTML.
#    d) Added an explicit empty-value guard before touching the DB.
#       Django's create_user raises "The given username must be set"
#       when username="" — this guard shows a clear message instead.
#    e) transaction.atomic() ensures User + Department are committed
#       together; if Department.create() fails, the orphan User is
#       also rolled back automatically.
#    f) Search/filter GET params are now read AND passed back to the
#       template so search_query / location_query variables work.
# ─────────────────────────────────────────────────────────────────
@login_required
def manage_departments(request):
    # Retrieve admin profile — show a clear error if it's missing
    try:
        admin_profile = request.user.userprofile
    except UserProfile.DoesNotExist:
        messages.error(request, "Your account has no UserProfile. Please create one in Admin.")
        return redirect('dashboard')

    # ── POST: Create department + manager account ──────────────────
    if request.method == 'POST':
        name     = request.POST.get('name', '').strip()
        location = request.POST.get('location', '').strip()

        # FIX (b): read 'email' — matches name="email" in the HTML form
        email    = request.POST.get('email', '').strip()

        # FIX (c): read 'password' — matches name="password" in the HTML form
        password = request.POST.get('password', '').strip()

        # FIX (d): Guard — validate all fields before any DB call
        missing = []
        if not name:     missing.append("Department Name")
        if not location: missing.append("Location")
        if not email:    missing.append("Manager Email")
        if not password: missing.append("Manager Password")

        if missing:
            messages.error(request, f"Missing required fields: {', '.join(missing)}")
        else:
            # ── Duplicate-email guard ──────────────────────────────
            # Prevents "UNIQUE constraint failed" crash when the email
            # is already used as a Django username by another manager.
            if User.objects.filter(username=email).exists():
                messages.error(
                    request,
                    f"This email is already registered. "
                    f"Please use a different email address for the manager account."
                )
            else:
                try:
                    # FIX (e): Atomic transaction — both records save or neither does
                    with transaction.atomic():
                        # Create the manager login account
                        # create_user() hashes the password correctly (FIX for login readiness)
                        # username = email so the manager logs in with their email address
                        new_user = User.objects.create_user(
                            username = email,   # FIX (a+b): was receiving "" because the
                            email    = email,   #            HTML sent 'manager_username', not 'email'
                            password = password,
                        )

                        # Create the department, linked to the manager and organisation
                        Department.objects.create(
                            name         = name,
                            location     = location,
                            organization = admin_profile.organization,
                            managed_by   = new_user,
                        )

                    messages.success(request, f"Department '{name}' and manager account created!")
                    return redirect('department_list')

                except Exception as e:
                    # Shows the real Django/DB error in the UI during development
                    messages.error(request, f"Database Error: {e}")

    # ── GET: Search / Filter ───────────────────────────────────────
    # FIX (f): read params AND pass them back so {{ search_query }} works in template
    search_query   = request.GET.get('search', '').strip()
    location_query = request.GET.get('location', '').strip()

    departments = Department.objects.filter(
        organization = admin_profile.organization
    )

    if search_query:
        departments = departments.filter(
            Q(name__icontains=search_query) |
            Q(managed_by__username__icontains=search_query)
        )

    if location_query:
        departments = departments.filter(location__icontains=location_query)

    return render(request, 'admin/departments.html', {
        'departments':    departments,
        'search_query':   search_query,   # keeps value in search box after reload
        'location_query': location_query, # keeps value in location box after reload
        'org_name':       admin_profile.organization.name,  # branding in sidebar/header
    })


# ─────────────────────────────────────────────────────────────────
# 8. Edit Department
# ─────────────────────────────────────────────────────────────────
@login_required
def edit_department(request, dept_id):
    dept = get_object_or_404(
        Department,
        id           = dept_id,
        organization = request.user.userprofile.organization,
    )

    if request.method == 'POST':
        dept.name     = request.POST.get('name', dept.name).strip()
        dept.location = request.POST.get('location', dept.location).strip()
        dept.save()
        messages.success(request, f"'{dept.name}' updated successfully!")
        return redirect('department_list')

    return render(request, 'admin/edit_department.html', {'dept': dept})


# ─────────────────────────────────────────────────────────────────
# 9. Delete Department
# ─────────────────────────────────────────────────────────────────
@login_required
def delete_department(request, dept_id):
    dept = get_object_or_404(
        Department,
        id           = dept_id,
        organization = request.user.userprofile.organization,
    )

    if request.method == 'POST':
        dept_name = dept.name
        # CASCADE: deleting the linked User also removes their login access
        if dept.managed_by:
            dept.managed_by.delete()
        dept.delete()
        messages.success(request, f"Deleted '{dept_name}' and its manager account.")
        return redirect('department_list')

    return render(request, 'admin/delete_confirm.html', {'dept': dept})


# ─────────────────────────────────────────────────────────────────
# 10. Edit Organisation
#     Allows the logged-in Admin to update their Organisation's
#     name and country/location field.
# ─────────────────────────────────────────────────────────────────
@login_required
def edit_organization(request):
    try:
        admin_profile = request.user.userprofile
    except UserProfile.DoesNotExist:
        messages.error(request, "No UserProfile found for your account.")
        return redirect('dashboard')

    org = admin_profile.organization   # the Organisation this admin owns

    if request.method == 'POST':
        new_name     = request.POST.get('name', '').strip()
        new_country  = request.POST.get('country', '').strip()
        new_industry = request.POST.get('industry', '').strip()

        if not new_name:
            messages.error(request, "Organisation name cannot be empty.")
        else:
            org.name     = new_name
            org.country  = new_country
            org.industry = new_industry
            org.save()
            messages.success(request, f"Organisation updated to '{org.name}'.")
            return redirect('dashboard')

    return render(request, 'admin/edit_organization.html', {
        'org':      org,
        'org_name': org.name,   # keeps sidebar consistent even before save
    })

# views.py  (add this alongside your existing manager views)

# ─────────────────────────────────────────────────────────────────
# 12. Manager Analytics
#     Shows emission charts scoped to the logged-in manager's dept.
#     Managers are NOT guaranteed to have a UserProfile, so org is
#     resolved through the Department → Organization FK instead.
# ─────────────────────────────────────────────────────────────────
import json
from datetime import date
from dateutil.relativedelta import relativedelta   # pip install python-dateutil

from django.db.models.functions import TruncMonth

@login_required
def manager_analytics(request):
    """
    Analytics page.
 
    • Normal path  → department manager views their own department.
    • Admin path   → org admin / superuser passes ?dept_id=<id> to view
                     any department within their organisation.
 
    Context variable `viewed_by_admin` (bool) lets the template hide
    manager-specific navigation elements for admin visitors.
    """
 
    # ── Detect admin bypass ────────────────────────────────────────
    admin_profile  = getattr(request.user, 'userprofile', None)
    is_org_admin   = bool(admin_profile and admin_profile.role == 'ADMIN')
    viewed_by_admin = request.user.is_superuser or is_org_admin
 
    if viewed_by_admin:
        # Admin must supply ?dept_id=<id> in the URL; if missing, bounce
        # to the admin dashboard with a helpful message.
        dept_id = request.GET.get('dept_id')
        if not dept_id:
            messages.error(request, "No department specified. Click a row in the dashboard.")
            return redirect('dashboard')
 
        # Scope to admin's own organisation (security: no cross-org peek)
        org = admin_profile.organization if admin_profile else None
        dept = get_object_or_404(Department, id=dept_id, organization=org)
        org_name = org.name if org else "EcoTrack"
 
    else:
        # Normal manager path — look up by managed_by
        dept = Department.objects.select_related('organization').filter(
            managed_by=request.user
        ).first()
 
        if not dept:
            return redirect('dashboard')
 
        org_name = dept.organization.name
 
    # ── Scope the queryset to this single department ───────────────
    qs       = ActivityLog.objects.filter(department=dept)
    has_data = qs.exists()
 
    # ── Dataset A: total emissions per category (Doughnut) ─────────
    category_qs = (
        qs.values('category')
          .annotate(total=Sum('emissions_amount'))
          .order_by('category')
    )
    category_labels = [row['category']        for row in category_qs]
    category_values = [round(row['total'], 2) for row in category_qs]
 
    # ── Dataset B: monthly totals — last 6 months (Line) ───────────
    today   = date.today()
    six_ago = today.replace(day=1) - relativedelta(months=5)
 
    monthly_qs = (
        qs.filter(activity_date__gte=six_ago)
          .annotate(month=TruncMonth('activity_date'))
          .values('month')
          .annotate(total=Sum('emissions_amount'))
          .order_by('month')
    )
 
    month_map = {
        row['month'].replace(day=1): round(row['total'], 2)
        for row in monthly_qs
    }
    month_labels = []
    month_values = []
    for i in range(6):
        bucket = (six_ago + relativedelta(months=i)).replace(day=1)
        month_labels.append(bucket.strftime('%b %Y'))
        month_values.append(month_map.get(bucket, 0))
 
    context = {
        'org_name':         org_name,
        'dept':             dept,
        'has_data':         has_data,
        'total_emissions':  round(
            qs.aggregate(t=Sum('emissions_amount'))['t'] or 0, 1
        ),
        'category_count':   len(category_labels),
        'entry_count':      qs.count(),
        'category_labels':  json.dumps(category_labels),
        'category_data':    json.dumps(category_values),
        'month_labels':     json.dumps(month_labels),
        'month_data':       json.dumps(month_values),
        # Template guard — hides manager-only nav links when True
        'viewed_by_admin':  viewed_by_admin,
    }
    return render(request, 'manager/analytics.html', context)

# ─────────────────────────────────────────────────────────────────
# 13. Edit Activity Log
#     Only the owning manager may edit their own department's log.
#     emissions_amount is never touched here — ActivityLog.save()
#     recalculates it automatically from the new quantity/category.
# ─────────────────────────────────────────────────────────────────
@login_required
def edit_activity(request, log_id):
    # Resolve the manager's department first
    dept = Department.objects.filter(managed_by=request.user).first()
    if not dept:
        messages.error(request, "Only department managers can edit activity logs.")
        return redirect('dashboard')

    # Fetch the log — 404 if it doesn't exist OR belongs to another dept
    log = get_object_or_404(ActivityLog, id=log_id, department=dept)

    VALID_CATEGORIES = ['Electricity', 'Water', 'Petrol', 'Diesel', 'Travel']

    if request.method == 'POST':
        category     = request.POST.get('category', '').strip()
        quantity_raw = request.POST.get('quantity', '').strip()
        date_raw     = request.POST.get('activity_date', '').strip()

        errors = []

        if not category or category not in VALID_CATEGORIES:
            errors.append("Please select a valid category.")

        if not date_raw:
            errors.append("Activity date is required.")

        quantity = None
        if not quantity_raw:
            errors.append("Quantity is required.")
        else:
            try:
                quantity = float(quantity_raw)
                if quantity <= 0:
                    errors.append("Quantity must be greater than zero.")
            except ValueError:
                errors.append("Quantity must be a valid number.")

        if errors:
            for err in errors:
                messages.error(request, err)
        else:
            # Update fields — save() auto-recalculates emissions_amount
            log.category      = category
            log.quantity      = quantity
            log.activity_date = date_raw
            log.save()
            messages.success(
                request,
                f"Log updated: {quantity} units of {category} — "
                f"CO₂ recalculated to {log.emissions_amount} kg."
            )
            return redirect('manager_dashboard')

    return render(request, 'manager/edit_activity.html', {
        'log':        log,
        'dept':       dept,
        'org_name':   dept.organization.name,
        'categories': VALID_CATEGORIES,
    })


# ─────────────────────────────────────────────────────────────────
# 14. Delete Activity Log
#     GET  → returns JSON {category, quantity, emissions_amount}
#            so the Bootstrap modal can show a confirmation summary
#            without a full page load.
#     POST → deletes the record and redirects with a flash message.
#     Security: the get_object_or_404 scopes to dept so a manager
#     can never delete another department's logs.
# ─────────────────────────────────────────────────────────────────
from django.http import JsonResponse
@login_required
def delete_activity(request, log_id):
    dept = Department.objects.filter(managed_by=request.user).first()
    if not dept:
        if request.method == 'GET':
            return JsonResponse({'error': 'Forbidden'}, status=403)
        messages.error(request, "Only department managers can delete activity logs.")
        return redirect('dashboard')

    log = get_object_or_404(ActivityLog, id=log_id, department=dept)

    if request.method == 'POST':
        summary = f"{log.category} · {log.quantity} units · {log.activity_date}"
        log.delete()
        messages.success(request, f"Deleted: {summary}")
        return redirect('manager_dashboard')

    # GET — return log details as JSON for the modal
    return JsonResponse({
        'id':               log.id,
        'category':         log.category,
        'quantity':         log.quantity,
        'emissions_amount': log.emissions_amount,
        'activity_date':    str(log.activity_date),
    })
# ─────────────────────────────────────────────────────────────────
# 15. Export CSV  (Org-scoped Environmental Audit Report)
#
#     Access rules
#     ────────────
#     • Manager  → resolves org via their Department.organization FK
#                  (managers never have a UserProfile)
#     • Admin    → resolves org via UserProfile.organization
#
#     Both roles land at the same queryset: all ActivityLog rows
#     whose department belongs to the resolved organisation.
#
#     CSV structure
#     ─────────────
#     Row 1  Title block
#     Row 2  Meta  (org name + generation date)
#     Row 3  Blank spacer
#     Row 4  Column headers
#     …      One data row per ActivityLog entry (date-desc order)
#     Last   TOTAL EMISSIONS footer
# ─────────────────────────────────────────────────────────────────
import csv
from django.http import HttpResponse

@login_required
def export_csv(request):

    UNITS = {
        'Electricity': 'kWh',
        'Water':       'L',
        'Petrol':      'L',
        'Diesel':      'L',
        'Travel':      'km',
    }

    # ── 1. Resolve organisation ──────────────────────────────────
    # Managers have no UserProfile — resolve org through their dept.
    # Admins have a UserProfile — resolve org directly.
    org      = None
    org_name = 'Unknown'

    dept_as_manager = Department.objects.select_related('organization').filter(
        managed_by=request.user
    ).first()

    if dept_as_manager:
        # Caller is a department manager
        org      = dept_as_manager.organization
        org_name = org.name
    elif hasattr(request.user, 'userprofile'):
        # Caller is an org admin
        org      = request.user.userprofile.organization
        org_name = org.name
    else:
        messages.error(request, "Your account is not linked to any organisation.")
        return redirect('dashboard')

    # ── 2. Fetch all logs for every department in this org ───────
    # Using department__organization scopes the query to the org
    # without a separate Department lookup.
    logs = (
        ActivityLog.objects
        .filter(department__organization=org)
        .select_related('department', 'logged_by')
        .order_by('-activity_date', '-date_recorded')
    )

    # ── 3. Pre-compute total for the footer row ──────────────────
    total_emissions = round(
        logs.aggregate(t=Sum('emissions_amount'))['t'] or 0, 4
    )

    # ── 4. Build dynamic filename ────────────────────────────────
    # Sanitise org name: keep alphanumerics, replace everything else
    # with underscores so the filename is safe on all OS/browsers.
    safe_org = "".join(c if c.isalnum() else "_" for c in org_name)
    filename = f"EcoTrack_Report_{safe_org}_{date.today().isoformat()}.csv"

    # ── 5. Stream directly into HttpResponse ────────────────────
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    writer = csv.writer(response)

    # Row 1 — Report title
    writer.writerow(['EcoTrack Environmental Audit Report'])

    # Row 2 — Meta: org name + generation date
    writer.writerow([
        'Organization:', org_name,
        'Generated:',    date.today().strftime('%Y-%m-%d'),
    ])

    # Row 3 — Blank spacer (improves readability when opened in Excel)
    writer.writerow([])

    # Row 4 — Column headers
    writer.writerow([
        'Date',
        'Department',
        'Category',
        'Quantity',
        'Unit',
        'Emissions (kg CO2)',
    ])

    # Data rows
    for row in logs:
        writer.writerow([
            row.activity_date.strftime('%Y-%m-%d'),   # explicit strftime avoids AttributeError
            row.department.name,
            row.category,
            row.quantity,
            UNITS.get(row.category, 'units'),
            row.emissions_amount,
        ])

    # Footer row — total emissions across all rows
    writer.writerow(['TOTAL EMISSIONS', '', '', '', '', total_emissions])

    return response
# ─────────────────────────────────────────────────────────────────
# eco_insights  —  Insights & Recommendations (Manager)
#
# Paste this function block into views.py.
# Also add this import at the top of views.py (with the other imports):
#
#   from django.core.cache import cache
#   from .utils import get_gemini_recommendations
#
# ─────────────────────────────────────────────────────────────────

from django.core.cache import cache
from .utils import get_gemini_recommendations

@login_required
def eco_insights(request):
    """
    Insights & Recommendations page.

    • Manager path  — resolves dept via managed_by=request.user
    • Admin path    — resolves dept via ?dept_id= query param
    """

    # ── 1. Resolve department (admin bypass or manager lookup) ────
    admin_profile   = getattr(request.user, 'userprofile', None)
    is_org_admin    = bool(admin_profile and admin_profile.role == 'ADMIN')
    viewed_by_admin = request.user.is_superuser or is_org_admin

    if viewed_by_admin:
        dept_id = request.GET.get('dept_id')
        if not dept_id:
            messages.error(request, "No department selected. Click a row in the dashboard.")
            return redirect('dashboard')
        org  = admin_profile.organization if admin_profile else None
        dept = get_object_or_404(Department, id=dept_id, organization=org)
    else:
        dept = Department.objects.filter(managed_by=request.user).first()
        if not dept:
            return redirect('dashboard')

    org_name = dept.organization.name if dept.organization else "EcoTrack"
    now      = timezone.now()

    # ── 2. Six-month rolling window ───────────────────────────────
    months = []
    for offset in range(5, -1, -1):
        point = now - relativedelta(months=offset)
        months.append((point.year, point.month, point.strftime('%b %Y')))

    monthly_data = []
    for year, month, label in months:
        total = (
            ActivityLog.objects
            .filter(
                department=dept,
                activity_date__year=year,
                activity_date__month=month,
            )
            .aggregate(total=Sum('emissions_amount'))['total'] or 0.0
        )
        monthly_data.append({'label': label, 'total': round(total, 2)})

    # ── 3. Top emitting category — current month ──────────────────
    categories = ['Electricity', 'Water', 'Petrol', 'Diesel', 'Travel']
    current_month_logs = ActivityLog.objects.filter(
        department=dept,
        activity_date__year=now.year,
        activity_date__month=now.month,
    )

    category_totals_raw = {}
    for cat in categories:
        cat_sum = (
            current_month_logs.filter(category=cat)
            .aggregate(total=Sum('emissions_amount'))['total'] or 0.0
        )
        category_totals_raw[cat] = round(cat_sum, 2)

    top_category     = max(category_totals_raw, key=category_totals_raw.get)
    top_category_val = category_totals_raw[top_category]

    # ── 4. Month-on-month delta ───────────────────────────────────
    last_month   = now - relativedelta(months=1)
    last_m_total = (
        ActivityLog.objects
        .filter(
            department=dept,
            activity_date__year=last_month.year,
            activity_date__month=last_month.month,
        )
        .aggregate(total=Sum('emissions_amount'))['total'] or 0.0
    )
    current_m_total = monthly_data[-1]['total']
    delta_kg        = round(current_m_total - last_m_total, 2)
    delta_pct       = (
        round((delta_kg / last_m_total) * 100, 1)
        if last_m_total > 0 else None
    )

    # ── 5. Prepare AI summary ─────────────────────────────────────
    has_data = any(item['total'] > 0 for item in monthly_data)

    if has_data:
        stats_summary = (
            f"Organisation: {org_name}\n"
            f"Department: {dept.name}\n"
            f"Report month: {now.strftime('%B %Y')}\n\n"
            f"Current month total emissions: {current_m_total} kg CO₂\n"
            f"Previous month total emissions: {round(last_m_total, 2)} kg CO₂\n"
            f"Month-on-month change: {delta_kg:+.2f} kg CO₂"
            + (f" ({delta_pct:+.1f}%)" if delta_pct is not None else "") + "\n\n"
            f"Top emitting category this month: {top_category} "
            f"({top_category_val} kg CO₂)\n\n"
            f"Category breakdown (current month):\n"
            + "\n".join(
                f"  • {cat}: {val} kg CO₂"
                for cat, val in category_totals_raw.items()
            )
            + f"\n\nLast 6 months totals (oldest → newest):\n"
            + "\n".join(
                f"  • {item['label']}: {item['total']} kg CO₂"
                for item in monthly_data
            )
        )
    else:
        stats_summary = "No data available."

    # ── 6. Cache — keyed per department, not per user ─────────────
    cache_key = f"ai_insight_dept_{dept.id}"

    if request.GET.get('refresh') == '1':
        cache.delete(cache_key)

    ai_insight = cache.get(cache_key)

    if ai_insight is None:
        if has_data:
            ai_insight = get_gemini_recommendations(stats_summary)
        else:
            ai_insight = (
                "No emissions data has been recorded yet. "
                "Log some activity data and return to this page for personalised "
                "AI-powered sustainability recommendations."
            )
        cache.set(cache_key, ai_insight, timeout=21_600)

    # ── 7. Render ─────────────────────────────────────────────────
    return render(request, 'manager/insights.html', {
        'dept':             dept,
        'org_name':         org_name,
        'monthly_data':     json.dumps(monthly_data),
        'monthly_labels':   [m['label'] for m in monthly_data],
        'monthly_totals':   [m['total'] for m in monthly_data],
        'top_category':     top_category,
        'top_category_val': top_category_val,
        'category_totals':  category_totals_raw,
        'current_m_total':  current_m_total,
        'last_m_total':     round(last_m_total, 2),
        'delta_kg':         delta_kg,
        'delta_pct':        delta_pct,
        'current_month':    now.strftime('%B %Y'),
        'last_month_label': last_month.strftime('%B %Y'),
        'ai_insight':       ai_insight,
        'has_data':         has_data,
        'viewed_by_admin':  viewed_by_admin,
        'refresh_url': (
            f"{request.path}?dept_id={dept.id}&refresh=1"
            if viewed_by_admin
            else f"{request.path}?refresh=1"
        ),
    })
# ─────────────────────────────────────────────────────────────────
# admin_analytics  —  Global Analytics (Admin)
#
# ADD this function to views.py (alongside your existing views).
# All imports used here already exist at the top of your views.py.
# ─────────────────────────────────────────────────────────────────

@login_required
def admin_analytics(request):
    """
    Global Analytics page for Org Admins.

    Datasets passed to the template as JSON:
      1. dept_labels / dept_data   → League table (bar chart)
      2. cat_labels  / cat_data    → Category breakdown (doughnut)
      3. trend_labels / trend_data → 6-month org-wide trend (line)
    """

    # ── Guard: must be an Admin ───────────────────────────────────
    # Redirect plain managers to their own dashboard.
    if Department.objects.filter(managed_by=request.user).exists():
        return redirect('manager_dashboard')

    admin_profile = getattr(request.user, 'userprofile', None)
    org = admin_profile.organization if admin_profile else None
    org_name = org.name if org else "EcoTrack"

    # Base queryset — all logs that belong to this organisation
    if org:
        org_logs = ActivityLog.objects.filter(department__organization=org)
    else:
        org_logs = ActivityLog.objects.none()

    # ── Dataset 1: League Table — total emissions per department ──
    dept_qs = (
        org_logs
        .values('department__name')
        .annotate(total=Sum('emissions_amount'))
        .order_by('-total')
    )
    dept_labels = [row['department__name'] for row in dept_qs]
    dept_data   = [round(row['total'], 2) for row in dept_qs]

    # ── Dataset 2: Category Breakdown ────────────────────────────
    CATEGORIES = ['Electricity', 'Water', 'Petrol', 'Diesel', 'Travel']
    cat_qs = (
        org_logs
        .values('category')
        .annotate(total=Sum('emissions_amount'))
        .order_by('category')
    )
    # Build ordered lists matching CATEGORIES (fill 0 if category absent)
    cat_map = {row['category']: round(row['total'], 2) for row in cat_qs}
    cat_labels = CATEGORIES
    cat_data   = [cat_map.get(cat, 0.0) for cat in CATEGORIES]

    # ── Dataset 3: 6-Month Org-wide Trend ────────────────────────
    now = timezone.now()
    trend_labels = []
    trend_data   = []

    for offset in range(5, -1, -1):           # oldest → newest
        point = now - relativedelta(months=offset)
        label = point.strftime('%b %Y')
        total = (
            org_logs
            .filter(
                activity_date__year=point.year,
                activity_date__month=point.month,
            )
            .aggregate(total=Sum('emissions_amount'))['total'] or 0.0
        )
        trend_labels.append(label)
        trend_data.append(round(total, 2))

    # ── Summary stats for the stat-row cards ─────────────────────
    total_org_emissions = round(
        org_logs.aggregate(total=Sum('emissions_amount'))['total'] or 0.0, 2
    )
    total_departments = Department.objects.filter(organization=org).count() if org else 0
    total_logs        = org_logs.count()

    # Top emitting department (for the highlight card)
    top_dept = dept_labels[0] if dept_labels else "—"
    top_dept_val = dept_data[0] if dept_data else 0.0

    return render(request, 'admin/analytics.html', {
        'admin_profile':       admin_profile,
        'org_name':            org_name,

        # Chart data — safe JSON strings
        'dept_labels':         json.dumps(dept_labels),
        'dept_data':           json.dumps(dept_data),
        'cat_labels':          json.dumps(cat_labels),
        'cat_data':            json.dumps(cat_data),
        'trend_labels':        json.dumps(trend_labels),
        'trend_data':          json.dumps(trend_data),

        # Summary cards
        'total_org_emissions': total_org_emissions,
        'total_departments':   total_departments,
        'total_logs':          total_logs,
        'top_dept':            top_dept,
        'top_dept_val':        top_dept_val,

        # Empty-state flag — JS will check this before rendering
        'has_data':            total_logs > 0,
    })
