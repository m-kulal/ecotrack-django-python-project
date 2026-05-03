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
def login_view(request):
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                return redirect('dashboard') # Redirects to our new starting point
            else:
                messages.error(request, "Invalid username or password.")
        else:
            messages.error(request, "Invalid username or password.")
    
    form = AuthenticationForm()
    return render(request, 'core/login.html', {'form': form})

# 4. Logout Logic
def logout_view(request):
    logout(request)
    return redirect('landing_page')

# 5. DASHBOARD STARTING POINT
@login_required
def dashboard(request):
    profile = request.user.userprofile
    org = profile.organization
    
    # Let's give it some realistic "Dummy Data" so the UI looks alive
    context = {
        'org_name': org.name,
        'total_emissions': "84.20",  # Matches the note in your screenshot
        'limit_percentage': 72,      # Matches the note
        'limit_bar_width': "72%",    # Used for the CSS progress bar
        'limit_bar_color': "#39ff14", # Neon Green
        'active_depts': org.department_set.count(),
        'new_depts_this_month': 1,
        'show_limit_warning': False,
    }
    return render(request, 'admin/dashboard.html', context)

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