from django.shortcuts import render, redirect
from django.contrib import messages
from django.db import transaction
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from .models import UserProfile, Organization
from .forms import UserRegistrationForm, OrganizationForm

# 1. Landing Page
def landing_page(request):
    return render(request, 'core/landing.html')

# 2. Registration Logic (Handles Admin + Org Creation)
def register_organization(request):
    if request.method == "POST":
        user_form = UserRegistrationForm(request.POST)
        org_form = OrganizationForm(request.POST)

        if user_form.is_valid() and org_form.is_valid():
            try:
                with transaction.atomic():
                    # Create the Organization first
                    organization = org_form.save()

                    # Extract validated user data
                    cd = user_form.cleaned_data
                    user = User.objects.create_user(
                        username=cd["username"],
                        email=cd["email"],
                        password=cd["password"],
                        first_name=cd["first_name"],
                        last_name=cd["last_name"],
                    )

                    # Create UserProfile linking the user to the organization as ADMIN
                    UserProfile.objects.create(
                        user=user,
                        organization=organization,
                        role="ADMIN",
                    )

                messages.success(request, "Organization registered successfully! You can now log in.")
                return redirect("login")

            except Exception as exc:
                messages.error(request, f"An error occurred during registration: {exc}")
    else:
        user_form = UserRegistrationForm()
        org_form = OrganizationForm()

    return render(request, "core/register.html", {"user_form": user_form, "org_form": org_form})

# 3. Login Logic
from django.contrib.auth import authenticate, login
from core.models import Department

from django.contrib import messages
from core.models import Department

def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            login(request, user)
            
            # 1. ADMIN CHECK (Check for UserProfile or Superuser status)
            if hasattr(user, 'userprofile') and user.userprofile.role == 'ADMIN' or user.is_superuser:
                return redirect('dashboard')
            
            # 2. MANAGER CHECK (Check if they are linked to a Department)
            elif Department.objects.filter(managed_by=user).exists():
                return redirect('branch_dashboard')
            
            # 3. DEFAULT FALLBACK
            return redirect('dashboard')
        else:
            messages.error(request, "Invalid username or password")
            
    return render(request, 'core/login.html')
# 4. Logout Logic
def logout_view(request):
    logout(request)
    return redirect('landing_page')

# 5. DASHBOARD STARTING POINT
@login_required
def dashboard(request):
    # If the user is a manager, they MUST go to the branch dashboard
    if Department.objects.filter(managed_by=request.user).exists():
        return redirect('branch_dashboard')

    # If the code reaches here, it means the user is an ADMIN or Superuser
    try:
        # Get profile or set to None for Superusers without profiles
        admin_profile = getattr(request.user, 'userprofile', None)
        return render(request, 'admin/dashboard.html', {
            'admin_profile': admin_profile
        })
    except Exception as e:
        # Only redirect to login if there is a critical system error
        print(f"Dashboard Error: {e}")
        return render(request, 'core/dashboard.html')

from django.shortcuts import render, redirect
from django.contrib.auth.models import User
from .models import Department, UserProfile

from django.contrib import messages

@login_required
def manage_departments(request):
    admin_profile = request.user.userprofile
    departments = Department.objects.filter(organization=admin_profile.organization)
    
    if request.method == 'POST':
        name = request.POST.get('name')
        location = request.POST.get('location')
        uname = request.POST.get('manager_username')
        pword = request.POST.get('manager_password')
        
        # DEBUG: Check if we are actually getting data from the form
        if not all([name, location, uname, pword]):
            messages.error(request, "Missing fields! Check your form input names.")
        else:
            try:
                # Create the user first
                user = User.objects.create_user(username=uname, password=pword)
                
                # Create the department
                Department.objects.create(
                    name=name,
                    location=location,
                    organization=admin_profile.organization,
                    managed_by=user
                )
                messages.success(request, f"Successfully created {name}!")
                return redirect('department_list')
                
            except Exception as e:
                # This will tell you EXACTLY why it didn't save
                messages.error(request, f"Database Error: {e}")
                print(f"Detailed Error: {e}")

    return render(request, 'admin/departments.html', {'departments': departments})

from core.models import Department

@login_required
def branch_dashboard(request):
    # 1. Fetch the department by querying the table directly
    # This avoids using the 'request.user.managed_department' attribute
    dept = Department.objects.filter(managed_by=request.user).first()

    # 2. Safety check: If they aren't actually a manager, send them away
    if not dept:
        return redirect('login')

    # 3. Pass the 'dept' object to your template
    return render(request, 'branch/dashboard.html', {
        'department': dept,
        'manager_name': request.user.username
    })