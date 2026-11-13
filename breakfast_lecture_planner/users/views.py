from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.views import LoginView, PasswordChangeView
from django.http import HttpResponseForbidden
from django.shortcuts import redirect
from django.urls import reverse, reverse_lazy
from django.utils.decorators import method_decorator
from django.views.generic import CreateView, DeleteView, ListView, UpdateView
from django.views.generic.edit import CreateView, DeleteView

from .forms import CustomUserCreationForm, CustomUserEditForm


def is_admin(user):
    return user.groups.filter(name="Админ").exists()


def superuser_required(function):
    return user_passes_test(lambda u: u.is_superuser)(function)


class CustomLoginView(LoginView):
    def get_success_url(self):
        user = self.request.user
        if is_admin(user):
            return reverse("planner:cabinet")
        return reverse("planner:new")


@method_decorator(user_passes_test(is_admin), name="dispatch")
class CustomPasswordChangeView(PasswordChangeView):
    def form_valid(self, form):
        return super().form_valid(form)


@method_decorator(superuser_required, name="dispatch")
class UserCreateView(CreateView):
    model = get_user_model()
    template_name = "planner/add_person.html"
    form_class = CustomUserCreationForm
    success_url = reverse_lazy("users:user_list")
    extra_context = {"role": "администратора"}

    def form_valid(self, form):
        user = form.save()
        return super().form_valid(form)


@method_decorator(login_required, name="dispatch")
class UserUpdateView(UpdateView):
    model = get_user_model()
    template_name = "planner/add_person.html"
    form_class = CustomUserEditForm
    success_url = reverse_lazy("users:user_list")
    extra_context = {"role": "администратора", "edit": True}

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_superuser and request.user.pk != kwargs.get("pk"):
            return HttpResponseForbidden("Можно редактировать только собственный аккаунт.")
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["can_manage_groups"] = self.request.user.is_superuser
        return kwargs


@method_decorator(login_required, name="dispatch")
class UserListView(ListView):
    model = get_user_model()
    template_name = "planner/persons_list.html"
    context_object_name = "persons"
    extra_context = {
        "role_singular": "Администратора",
        "role_plural": "Администраторов",
        "path_delete": "users:user_delete",
        "path_add_person": "users:user_add",
        "path_edit": "users:user_update",
    }


@method_decorator(superuser_required, name="dispatch")
class UserDeleteView(DeleteView):
    model = get_user_model()
    template_name = "planner/delete_person.html"
    success_url = reverse_lazy("users:user_list")
    extra_context = {"role": "администратора", "path": "users:user_list"}

    def dispatch(self, request, *args, **kwargs):
        user = self.get_object()
        if user.is_superuser:
            return HttpResponseForbidden("Нельзя удалить суперпользователя.")
        return super().dispatch(request, *args, **kwargs)
