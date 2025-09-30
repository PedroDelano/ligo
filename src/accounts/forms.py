from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User


class PublicSignUpForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "usable_password" in self.fields:
            self.fields["usable_password"].widget = forms.HiddenInput()
            self.fields["usable_password"].initial = True
