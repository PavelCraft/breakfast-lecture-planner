import os

import requests
from celery import shared_task
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.db import transaction

from planner.services.schedule_archive import archive_previous_week


@shared_task(
    autoretry_for=(requests.RequestException,), retry_backoff=True, max_retries=3
)
def send_admin_notification(subject, message, reply_to=None):
    recipients = list(
        get_user_model().objects.exclude(email="").values_list("email", flat=True)
    )
    sender = reply_to or os.getenv("ADMIN_EMAIL") or None
    if recipients:
        send_mail(subject, message, sender, recipients)
    bot_token = os.getenv("BOT_TOKEN", "")
    chat_ids = [
        value.strip()
        for value in os.getenv("TELEGRAM_CHAT_IDS", "").split(",")
        if value.strip()
    ]
    if bot_token:
        for chat_id in chat_ids:
            response = requests.post(
                f"https://api.telegram.org/bot{bot_token}/sendMessage",
                data={"chat_id": chat_id, "text": f"{subject}\n\n{message}"},
                timeout=15,
            )
            response.raise_for_status()


def queue_admin_notification(subject, message, reply_to=None):
    transaction.on_commit(
        lambda: send_admin_notification.delay(subject, message, reply_to)
    )


@shared_task
def archive_previous_schedule_week():
    return archive_previous_week()
