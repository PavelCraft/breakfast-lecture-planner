# from django.contrib.auth import get_user_model
# from django.contrib.auth.forms import UserCreationForm

# User = get_user_model()


# class CreationForm(UserCreationForm):
#     class Meta(UserCreationForm.Meta):
#         model = User
#         fields = ('first_name', 'last_name', 'username', 'email')


from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import Group

from .models import UserNotificationSettings


NOTIFICATION_LABEL = "Получать сообщения о регистрациях на обед и фидбеки на почту"


class NotificationPreferenceMixin:
    def _set_notification_initial(self):
        if self.instance and self.instance.pk:
            settings = UserNotificationSettings.objects.filter(
                user=self.instance
            ).first()
            self.fields["receive_email_notifications"].initial = (
                settings.receive_email_notifications if settings else True
            )

    def _save_notification_preference(self, user):
        UserNotificationSettings.objects.update_or_create(
            user=user,
            defaults={
                "receive_email_notifications": self.cleaned_data[
                    "receive_email_notifications"
                ]
            },
        )


class CustomUserCreationForm(NotificationPreferenceMixin, UserCreationForm):
    receive_email_notifications = forms.BooleanField(
        required=False,
        initial=True,
        label=NOTIFICATION_LABEL,
    )
    email = forms.EmailField(
        required=True, widget=forms.EmailInput(attrs={"class": "form-control"})
    )
    groups = forms.ModelMultipleChoiceField(
        queryset=Group.objects.all(),
        required=False,
        widget=forms.SelectMultiple(attrs={"class": "form-control"}),
    )

    class Meta:
        model = get_user_model()
        fields = (
            "username",
            "email",
            "groups",
            "receive_email_notifications",
            "password1",
            "password2",
        )
        widgets = {
            "username": forms.TextInput(attrs={"class": "form-control"}),
            "password1": forms.PasswordInput(attrs={"class": "form-control"}),
            "password2": forms.PasswordInput(attrs={"class": "form-control"}),
        }

    def save(self, commit=True):
        user = super().save(commit=False)
        if commit:
            user.save()
            user.groups.set(self.cleaned_data["groups"])
            self._save_notification_preference(user)
        return user


class CustomUserEditForm(NotificationPreferenceMixin, forms.ModelForm):
    receive_email_notifications = forms.BooleanField(
        required=False,
        initial=True,
        label=NOTIFICATION_LABEL,
    )
    email = forms.EmailField(
        required=True, widget=forms.EmailInput(attrs={"class": "form-control"})
    )
    groups = forms.ModelMultipleChoiceField(
        queryset=Group.objects.all(),
        required=False,
        widget=forms.SelectMultiple(attrs={"class": "form-control"}),
    )

    class Meta:
        model = get_user_model()
        fields = ("username", "email", "groups", "receive_email_notifications")
        widgets = {
            "username": forms.TextInput(attrs={"class": "form-control"}),
        }

    def __init__(self, *args, can_manage_groups=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.can_manage_groups = can_manage_groups
        if not can_manage_groups:
            self.fields.pop("groups")
        self._set_notification_initial()

    def save(self, commit=True):
        user = super().save(commit=False)
        if commit:
            user.save()
            if self.can_manage_groups:
                user.groups.set(self.cleaned_data["groups"])
            self._save_notification_preference(user)
        return user
