from django.contrib.auth import login
from django.contrib.auth.views import LoginView, LogoutView
from django.urls import reverse_lazy
from django.views.generic import FormView

from .forms import PublicSignUpForm


class CustomLoginView(LoginView):
    template_name = "registration/login.html"


class SignUpView(FormView):
    template_name = "registration/signup.html"
    form_class = PublicSignUpForm
    success_url = reverse_lazy("game:index")

    def form_valid(self, form):
        user = form.save()
        login(self.request, user)
        return super().form_valid(form)


class CustomLogoutView(LogoutView):
    next_page = reverse_lazy("main_page:index")
