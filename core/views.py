from django.shortcuts import render, redirect
from django.contrib import messages
from django.db import transaction

from django.contrib.auth.models import User
from .models import UserProfile, Organization
from .forms import UserRegistrationForm, OrganizationForm


def register_organization(request):
    """
    Handles registration of a new organization and its admin user.
    Both the User and Organization are created inside a single database
    transaction so that a failure in either step rolls back both.
    """
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

                    # Create UserProfile linking the user to the organization
                    # and assigning the ADMIN role
                    UserProfile.objects.create(
                        user=user,
                        organization=organization,
                        role="ADMIN",
                    )

                messages.success(
                    request,
                    "Organization registered successfully! You can now log in.",
                )
                return redirect("login")

            except Exception as exc:
                messages.error(
                    request,
                    f"An error occurred during registration. Please try again. ({exc})",
                )
    else:
        user_form = UserRegistrationForm()
        org_form = OrganizationForm()

    return render(
        request,
        "core/register.html",
        {
            "user_form": user_form,
            "org_form": org_form,
        },
    )
def landing_page(request):
    return render(request, 'core/landing.html')