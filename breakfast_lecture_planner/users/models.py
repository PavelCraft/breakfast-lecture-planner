from django.conf import settings
from django.db import models


class UserNotificationSettings(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notification_settings",
    )
    receive_email_notifications = models.BooleanField(default=True)

    class Meta:
        verbose_name = "настройки уведомлений пользователя"
        verbose_name_plural = "настройки уведомлений пользователей"

    def __str__(self):
        return f"Уведомления для {self.user}"
