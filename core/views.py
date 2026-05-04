from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db import transaction
from django.db.models import Q
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required

from .models import UserProfile, Organization, Department
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

            # Department Manager → branch dashboard
            if Department.objects.filter(managed_by=user).exists():
                return redirect('branch_dashboard')

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


# ─────────────────────────────────────────────────────────────────
# 5. Admin Dashboard
# ─────────────────────────────────────────────────────────────────
@login_required
def dashboard(request):
    # Managers must go to their own dashboard
    if Department.objects.filter(managed_by=request.user).exists():
        return redirect('branch_dashboard')

    admin_profile = getattr(request.user, 'userprofile', None)
    return render(request, 'admin/dashboard.html', {'admin_profile': admin_profile})


# ─────────────────────────────────────────────────────────────────
# 6. Branch (Manager) Dashboard
# ─────────────────────────────────────────────────────────────────
@login_required
def branch_dashboard(request):
    dept = Department.objects.filter(managed_by=request.user).first()
    if not dept:
        return redirect('login')

    return render(request, 'branch/dashboard.html', {
        'department':   dept,
        'manager_name': request.user.username,
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