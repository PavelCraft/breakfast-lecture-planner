from datetime import date, datetime, timedelta

from calendar_utils.utils import get_next_day_with_time
from django.db import models
from django.utils import timezone
from django_ckeditor_5.fields import CKEditor5Field


class Post(models.Model):
    title = models.CharField(null=True, blank=True, max_length=200)
    content = models.TextField()
    image = models.ForeignKey(
        "Image", null=True, blank=True, on_delete=models.SET_NULL
    )  # Поле для хранения изображения

    def __str__(self):
        return self.title


class Image(models.Model):
    image = models.ImageField(upload_to="images/")
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Image uploaded at {self.uploaded_at}"


def default_home_scene_layout():
    return {
        name: {"background_height": 520, "background_y": 0,
               "object_x": 75, "object_y": 0, "object_width": 220}
        for name in ("watch", "smartphone", "shovel", "tablet", "computer", "tv")
    }


class HomeScene(models.Model):
    """The published decorative layers and their responsive placement."""

    background = models.ImageField(upload_to="home_scene/backgrounds/", blank=True)
    object_image = models.ImageField(upload_to="home_scene/objects/", blank=True)
    layout = models.JSONField(default=default_home_scene_layout)
    updated_at = models.DateTimeField(auto_now=True)


class LunchParticipant(models.Model):
    name = models.CharField(max_length=100)
    email = models.EmailField()
    portions = models.PositiveIntegerField(
        choices=[(i, str(i)) for i in range(1, 16)], default=1
    )
    comment = models.TextField(blank=True, null=True)
    date = models.DateField()
    registration_date = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.date:
            print("self.date =", self.date)
            now = datetime.now()
            current_weekday = now.weekday()
            today = date.today()
            context = {
                "target_day": 4,
                "target_time": (17, 0, 0),
                "current_weekday": current_weekday,
                "current_date": today,
                "now": now,
            }
            # Получаем объект datetime ближайшей пятницы 17:00
            this_friday_17 = get_next_day_with_time(context)
            # print("метод save", "this_friday_17 =", this_friday_17)
            self.date = (this_friday_17 + timedelta(days=1)).date()
            # print(self.date)

        super().save(*args, **kwargs)

    class Meta:
        ordering = ["-pk"]

    def __str__(self):
        return self.name


class Feedback(models.Model):
    name = models.CharField(max_length=100)
    email = models.EmailField()
    text = models.TextField(blank=False)
    date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Обратная связь от {self.name} {self.date}"


class Text(models.Model):
    title = models.CharField("Title", max_length=200)
    text = CKEditor5Field("Text", config_name="extends")


class LastScheduleUpdate(models.Model):
    updated_at = models.DateTimeField(
        verbose_name="Дата и время последнего обновления расписания",
        default=timezone.now,
    )

    def __str__(self):
        return f"Последнее обновление: {self.updated_at}"


class DailySchedule(models.Model):
    date = models.DateField(unique=True)
    content = CKEditor5Field()
    updated_at = models.DateTimeField(auto_now=True)


class CalendarPeriod(models.Model):
    """Kartika bounds survive the weekly removal of old schedule text."""

    year = models.PositiveSmallIntegerField(unique=True)
    starts_on = models.DateField()
    ends_on = models.DateField(null=True, blank=True)

    class Meta:
        verbose_name = "Период Картики"
        verbose_name_plural = "Периоды Картики"


class ScheduleEditLock(models.Model):
    scope = models.CharField(max_length=16, default="schedule", unique=True)
    user = models.ForeignKey(
        "auth.User", on_delete=models.CASCADE, related_name="schedule_edit_locks"
    )
    token = models.CharField(max_length=64, unique=True)
    acquired_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    class Meta:
        verbose_name = "Блокировка редактирования расписания"
        verbose_name_plural = "Блокировки редактирования расписания"
