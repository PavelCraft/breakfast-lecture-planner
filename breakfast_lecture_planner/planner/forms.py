from django import forms
from django.utils.translation import gettext_lazy as _
from django_ckeditor_5.widgets import CKEditor5Widget
from django_recaptcha.fields import ReCaptchaField
from django_recaptcha.widgets import ReCaptchaV3

from calendar_utils.utils import lunch_registration_deadline

from .models import DailySchedule, Feedback, HomeScene, Image, LunchParticipant, Post


class PostForm(forms.ModelForm):
    class Meta:
        model = Post
        fields = ["title", "content"]
        widgets = {
            "title": forms.TextInput(attrs={"class": "full-width full-height"}),
            "content": CKEditor5Widget(
                config_name="extends",
                attrs={"class": "full-width full-height"},
            ),
        }

    def __init__(self, *args, **kwargs):
        super(PostForm, self).__init__(*args, **kwargs)
        self.fields["content"].widget.attrs.update(
            {
                "rows": 50,  # Задайте нужное количество строк
                "cols": 80,  # (необязательно) Задайте нужное количество столбцов
            }
        )


class MainPostEditorForm(forms.ModelForm):
    class Meta:
        model = Post
        fields = ["content"]
        widgets = {
            "content": CKEditor5Widget(config_name="extends"),
        }


class DailyScheduleForm(forms.ModelForm):
    class Meta:
        model = DailySchedule
        fields = ["content"]
        widgets = {
            "content": CKEditor5Widget(config_name="extends"),
        }


class ImageUploadForm(forms.ModelForm):
    class Meta:
        model = Image
        fields = ["image"]


class HomeSceneForm(forms.ModelForm):
    class Meta:
        model = HomeScene
        fields = ["background", "object_image"]
        labels = {"background": "Фон", "object_image": "Объект"}

    def clean_background(self):
        background = self.cleaned_data.get("background")
        if not background and not self.instance.background:
            raise forms.ValidationError("Загрузите фон.")
        return background


class LunchParticipantForm(forms.ModelForm):
    # Скрытое от пользователей поле, предназначенное для заполнения роботами
    phone = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={"placeholder": _("Your phone number"), "style": "opacity:0;"}),
    )

    # Добавляем reCAPTCHA v3
    captcha = ReCaptchaField(widget=ReCaptchaV3(action="lunch_registration"))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.label = ""
        self.fields["portions"].initial = ""
        self.fields["portions"].choices = [("", _("Select the number of portions"))] + list(
            self.fields["portions"].choices
        )

    def clean(self):
        cleaned_data = super().clean()
        # Защита от спама роботов - проверка заполнения скрытого поля
        if "phone" in cleaned_data and cleaned_data["phone"]:
            print("Форму отравляет робот")
            cleaned_data.pop("phone")
            cleaned_data["robot"] = True
        # Логика вычисления даты
        # now = datetime.strptime("14.12.24 23:59:59", "%d.%m.%y %H:%M:%S")
        if lunch_registration_deadline() is None:
            cleaned_data["error_message"] = "Registration is over"
        return cleaned_data

    class Meta:
        model = LunchParticipant
        fields = [
            "phone",
            "name",
            "email",
            "portions",
            "comment",
        ]  # Поле date исключено
        widgets = {
            "comment": forms.Textarea(attrs={"rows": 4, "placeholder": _("Comment")}),
            "email": forms.EmailInput(
                attrs={"placeholder": _("Your email address. Required field")}
            ),
            "name": forms.TextInput(attrs={"placeholder": _("Your name")}),
            "portions": forms.Select(attrs={"style": "color: #757575;"}),
        }


class FeedbackForm(forms.ModelForm):
    phone = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={"placeholder": _("Your phone number"), "style": "opacity:0;"}),
    )

    captcha = ReCaptchaField(widget=ReCaptchaV3(action="feedback"))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.label = ""

    class Meta:
        model = Feedback
        fields = ["phone", "name", "email", "text"]
        widgets = {
            "text": forms.Textarea(attrs={"rows": 4, "placeholder": _("Message")}),
            "email": forms.EmailInput(
                attrs={"placeholder": _("Your email address. Required field")}
            ),
            "name": forms.TextInput(attrs={"placeholder": _("Your name")}),
        }
        labels = {
            "phone": _("Phone number"),
            "name": _("Name"),
            "email": "Email",
            "text": _("Message"),
        }

    def clean(self):
        cleaned_data = super().clean()
        # Защита от спама роботов - проверка заполнения скрытого поля
        if "phone" in cleaned_data and cleaned_data["phone"]:
            print("Форму отравляет робот")
            cleaned_data.pop("phone")
            cleaned_data["robot"] = True
        return cleaned_data

    def clean_text(self):
        text = self.cleaned_data.get("text")
        if not text:
            raise forms.ValidationError(_("This field cannot be empty."))
        return text


from django import forms

from .models import Text


class TextForm(forms.ModelForm):
    class Meta:
        model = Text
        fields = ["title", "text"]
