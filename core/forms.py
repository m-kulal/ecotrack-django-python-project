from django import forms
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from .models import Organization


class UserRegistrationForm(forms.Form):
    first_name = forms.CharField(
        max_length=30,
        required=True,
        widget=forms.TextInput(attrs={"placeholder": "First Name"}),
    )
    last_name = forms.CharField(
        max_length=30,
        required=True,
        widget=forms.TextInput(attrs={"placeholder": "Last Name"}),
    )
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={"placeholder": "Email Address"}),
    )
    username = forms.CharField(
        max_length=150,
        required=True,
        widget=forms.TextInput(attrs={"placeholder": "Username"}),
    )
    password = forms.CharField(
        min_length=8,
        required=True,
        widget=forms.PasswordInput(attrs={"placeholder": "Password"}),
    )
    confirm_password = forms.CharField(
        required=True,
        widget=forms.PasswordInput(attrs={"placeholder": "Confirm Password"}),
    )

    def clean_username(self):
        username = self.cleaned_data.get("username")
        if User.objects.filter(username=username).exists():
            raise ValidationError("A user with this username already exists.")
        return username

    def clean_email(self):
        email = self.cleaned_data.get("email")
        if User.objects.filter(email=email).exists():
            raise ValidationError("A user with this email already exists.")
        return email

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        confirm_password = cleaned_data.get("confirm_password")
        if password and confirm_password and password != confirm_password:
            raise ValidationError("Passwords do not match.")
        return cleaned_data


class OrganizationForm(forms.ModelForm):
    class Meta:
        model = Organization
        fields = ["name", "industry", "country", "description"]
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "Organization Name"}),
            "industry": forms.TextInput(attrs={"placeholder": "Industry (e.g. Technology, Manufacturing)"}),
            "country": forms.TextInput(attrs={"placeholder": "Country"}),
            "description": forms.Textarea(
                attrs={"placeholder": "Brief description of your organization", "rows": 3}
            ),
        }

    def clean_name(self):
        name = self.cleaned_data.get("name")
        if Organization.objects.filter(name__iexact=name).exists():
            raise ValidationError("An organization with this name already exists.")
        return name