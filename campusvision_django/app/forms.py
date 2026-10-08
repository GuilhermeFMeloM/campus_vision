from django import forms
from .models import User # Importe seu modelo User

class CustomUserCreationForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput)

    class Meta:
        model = User
        fields = ('email', 'name', 'is_admin', 'password')

    def save(self, commit=True): # sobrescreve o método save para usar o email como username
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        user.name = self.cleaned_data["name"]
        user.is_admin = self.cleaned_data["is_admin"]
        user.set_password(self.cleaned_data['password'])
        if commit:
            user.save()
        return user