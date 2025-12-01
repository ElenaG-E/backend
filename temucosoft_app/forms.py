# temucosoft_app/forms.py

from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.core.exceptions import ValidationError
from .models import CustomUser
from .utils import is_valid_rut, clean_rut # Necesario para la validación RUT

# Formulario personalizado para la creación de AdminCliente por SuperAdmin
class AdminClienteCreationForm(forms.Form):
    # Campos de la Compañía (Tenant)
    company_name = forms.CharField(max_length=100, label="Nombre de la Compañía/Tenant", 
                                   widget=forms.TextInput(attrs={'class': 'form-control'}))
    company_rut = forms.CharField(max_length=12, label="RUT de la Compañía",
                                  widget=forms.TextInput(attrs={'class': 'form-control'}))
    
    # Campos del Administrador (CustomUser)
    username = forms.CharField(max_length=150, widget=forms.TextInput(attrs={'class': 'form-control'}))
    email = forms.EmailField(widget=forms.EmailInput(attrs={'class': 'form-control'}))
    password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control'}))
    admin_rut = forms.CharField(max_length=12, label="RUT del Administrador",
                                widget=forms.TextInput(attrs={'class': 'form-control'}))

    def clean_company_rut(self):
        rut = self.cleaned_data['company_rut']
        rut_limpio = clean_rut(rut)
        if not rut_limpio or not is_valid_rut(rut_limpio):
            raise ValidationError("El RUT de la Compañía no es válido.")
        return rut_limpio

    def clean_admin_rut(self):
        rut = self.cleaned_data['admin_rut']
        rut_limpio = clean_rut(rut)
        if not rut_limpio or not is_valid_rut(rut_limpio):
            raise ValidationError("El RUT del Administrador no es válido.")
        return rut_limpio

    def clean(self):
        super().clean()
        # Puedes añadir lógica adicional, como verificar si el username/email ya existen.
        return self.cleaned_data


# Formulario para el login por Sesión (opción requerida)
class SessionLoginForm(AuthenticationForm):
    # Hereda username y password. Solo se ajusta la clase CSS
    username = forms.CharField(widget=forms.TextInput(attrs={'class': 'form-control'}))
    password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control'}))
