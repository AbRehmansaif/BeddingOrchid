from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from .models import Address
from apps.core.utils import normalize_phone_pk

User = get_user_model()


class LoginForm(forms.Form):
    username = forms.CharField(
        label="Email or Mobile Number",
        widget=forms.TextInput(attrs={
            'placeholder': 'e.g. 03001234567 or you@example.com',
            'class': 'w-full px-4 py-3 rounded-lg border border-stone-300 focus:ring-2 focus:ring-navy focus:outline-none text-stone-900',
            'autocomplete': 'username',
            'required': True
        })
    )
    password = forms.CharField(
        label="Password",
        widget=forms.PasswordInput(attrs={
            'placeholder': 'Enter your password',
            'class': 'w-full px-4 py-3 rounded-lg border border-stone-300 focus:ring-2 focus:ring-navy focus:outline-none text-stone-900',
            'autocomplete': 'current-password',
            'required': True
        })
    )


class RegisterForm(forms.ModelForm):
    password = forms.CharField(
        label="Password",
        min_length=6,
        widget=forms.PasswordInput(attrs={
            'placeholder': 'Minimum 6 characters',
            'class': 'w-full px-4 py-3 rounded-lg border border-stone-300 focus:ring-2 focus:ring-navy focus:outline-none text-stone-900',
            'autocomplete': 'new-password',
            'required': True,
            'minlength': '6',
        })
    )
    password_confirm = forms.CharField(
        label="Confirm Password",
        widget=forms.PasswordInput(attrs={
            'placeholder': 'Repeat your password',
            'class': 'w-full px-4 py-3 rounded-lg border border-stone-300 focus:ring-2 focus:ring-navy focus:outline-none text-stone-900',
            'autocomplete': 'new-password',
            'required': True,
        })
    )

    class Meta:
        model = User
        fields = ['full_name', 'phone', 'email', 'marketing_opt_in']
        widgets = {
            'full_name': forms.TextInput(attrs={
                'placeholder': 'Your Full Name',
                'class': 'w-full px-4 py-3 rounded-lg border border-stone-300 focus:ring-2 focus:ring-navy focus:outline-none text-stone-900',
                'required': True
            }),
            'phone': forms.TextInput(attrs={
                'placeholder': '03001234567 (Pakistani mobile)',
                'class': 'w-full px-4 py-3 rounded-lg border border-stone-300 focus:ring-2 focus:ring-navy focus:outline-none text-stone-900',
                'required': True,
                'type': 'tel',
                'pattern': '0[0-9]{9,11}',
            }),
            'email': forms.EmailInput(attrs={
                'placeholder': 'yourname@example.com (optional)',
                'class': 'w-full px-4 py-3 rounded-lg border border-stone-300 focus:ring-2 focus:ring-navy focus:outline-none text-stone-900',
            }),
            'marketing_opt_in': forms.CheckboxInput(attrs={
                'class': 'h-4 w-4 text-navy rounded border-stone-300 focus:ring-navy'
            }),
        }

    def clean_full_name(self):
        name = self.cleaned_data.get('full_name', '').strip()
        if not name:
            raise ValidationError("Please enter your full name.")
        return name

    def clean_phone(self):
        phone = self.cleaned_data.get('phone', '').strip()
        if not phone:
            raise ValidationError("Mobile phone number is required.")
        norm_phone = normalize_phone_pk(phone)
        if len(norm_phone) < 11 or len(norm_phone) > 13:
            raise ValidationError("Please enter a valid Pakistani mobile number (e.g. 03001234567).")
        if User.objects.filter(phone=norm_phone).exists():
            raise ValidationError("An account with this phone number already exists. Please log in instead.")
        return norm_phone

    def clean_email(self):
        email = self.cleaned_data.get('email', '').strip()
        if not email:
            return None  # Email is optional
        email = email.lower()
        if User.objects.filter(email=email).exists():
            raise ValidationError("An account with this email already exists.")
        return email

    def clean_password(self):
        password = self.cleaned_data.get('password', '')
        if not password:
            raise ValidationError("Password is required.")
        if len(password) < 6:
            raise ValidationError("Password must be at least 6 characters long.")
        return password

    def clean(self):
        cleaned_data = super().clean()
        p1 = cleaned_data.get('password')
        p2 = cleaned_data.get('password_confirm')
        if p1 and p2 and p1 != p2:
            self.add_error('password_confirm', "Passwords do not match.")
        elif not p2 and p1:
            self.add_error('password_confirm', "Please confirm your password.")
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password'])
        if commit:
            user.save()
        return user


class AddressForm(forms.ModelForm):
    class Meta:
        model = Address
        fields = ['label', 'full_name', 'phone', 'address_line1', 'address_line2',
                  'city', 'province', 'postal_code', 'landmark', 'is_default']
        widgets = {
            'label': forms.Select(attrs={
                'class': 'w-full px-4 py-3 rounded-lg border border-stone-300 focus:ring-2 focus:ring-navy text-stone-900'
            }),
            'full_name': forms.TextInput(attrs={
                'placeholder': 'Receiver Name',
                'class': 'w-full px-4 py-3 rounded-lg border border-stone-300 focus:ring-2 focus:ring-navy text-stone-900',
                'required': True
            }),
            'phone': forms.TextInput(attrs={
                'placeholder': '03XXXXXXXXX',
                'class': 'w-full px-4 py-3 rounded-lg border border-stone-300 focus:ring-2 focus:ring-navy text-stone-900',
                'required': True,
                'type': 'tel',
            }),
            'address_line1': forms.TextInput(attrs={
                'placeholder': 'House #, Street name, Sector / Block',
                'class': 'w-full px-4 py-3 rounded-lg border border-stone-300 focus:ring-2 focus:ring-navy text-stone-900',
                'required': True
            }),
            'address_line2': forms.TextInput(attrs={
                'placeholder': 'Apartment, Suite, Unit, etc. (optional)',
                'class': 'w-full px-4 py-3 rounded-lg border border-stone-300 focus:ring-2 focus:ring-navy text-stone-900'
            }),
            'city': forms.TextInput(attrs={
                'placeholder': 'e.g. Lahore, Karachi, Islamabad',
                'class': 'w-full px-4 py-3 rounded-lg border border-stone-300 focus:ring-2 focus:ring-navy text-stone-900',
                'required': True
            }),
            'province': forms.TextInput(attrs={
                'placeholder': 'Province (e.g. Punjab, Sindh)',
                'class': 'w-full px-4 py-3 rounded-lg border border-stone-300 focus:ring-2 focus:ring-navy text-stone-900'
            }),
            'postal_code': forms.TextInput(attrs={
                'placeholder': 'Postal / Zip code (optional)',
                'class': 'w-full px-4 py-3 rounded-lg border border-stone-300 focus:ring-2 focus:ring-navy text-stone-900'
            }),
            'landmark': forms.TextInput(attrs={
                'placeholder': 'Nearby well-known landmark (optional)',
                'class': 'w-full px-4 py-3 rounded-lg border border-stone-300 focus:ring-2 focus:ring-navy text-stone-900'
            }),
            'is_default': forms.CheckboxInput(attrs={
                'class': 'h-4 w-4 text-navy rounded border-stone-300 focus:ring-navy'
            }),
        }
