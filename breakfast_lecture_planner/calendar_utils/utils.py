from datetime import date, datetime, time, timedelta

from django.utils import timezone


def lunch_registration_deadline(now=None):
    """Return Friday 22:00 in Riga during the Sunday 04:00–Friday 22:00 window."""
    now = timezone.localtime(now or timezone.now())
    if (now.weekday() == 5 or
            (now.weekday() == 6 and now.time() < time(4, 0)) or
            (now.weekday() == 4 and now.time() >= time(22, 0))):
        return None
    local_now = now.replace(tzinfo=None)
    deadline = get_next_day_with_time({
        "target_day": 4,
        "target_time": (22, 0, 0),
        "current_weekday": local_now.weekday(),
        "current_date": local_now.date(),
        "now": local_now,
    })
    return timezone.make_aware(deadline, timezone.get_current_timezone())


def get_weeks_in_year(year):
    """Определяет количество недель в году. Если 1 января — пятница,
    суббота или воскресенье, то оно относится к предыдущему году,
    и первая неделя начинается с ближайшего понедельника."""
    first_day_of_year = date(year, 1, 1)
    first_weekday = first_day_of_year.weekday()

    if first_weekday <= 3:  # Если 1 января — понедельник-четверг
        start_of_first_week = first_day_of_year - timedelta(days=first_weekday)
    else:  # Если 1 января — пятница-воскресенье
        start_of_first_week = first_day_of_year + timedelta(days=7 - first_weekday)

    last_day_of_year = date(year, 12, 31)
    last_weekday = last_day_of_year.weekday()

    if last_weekday >= 3:
        # Если 31 декабря — среда и далее, год заканчивается в этом году
        end_of_last_week = last_day_of_year + timedelta(days=6 - last_weekday)
    else:
        # Если 31 декабря — понедельник-вторник,
        # последняя неделя относится к следующему году
        end_of_last_week = last_day_of_year - timedelta(days=last_weekday + 1)

    # Разница в днях между последней и первой неделями,
    # делённая на 7 даёт количество недель
    return (end_of_last_week - start_of_first_week).days // 7 + 1


def get_next_day_with_time(context: dict) -> datetime:
    """
    Возвращает объект datetime для ближайшего будущего указанного дня недели и времени.

    :param context: Словарь с данными:
        - target_day: Номер дня недели (0 - понедельник, 6 - воскресенье).
        - target_time: Время в формате (часы, минуты, секунды).
        - current_weekday: Номер текущего дня недели (0 - понедельник, 6 - воскресенье).
        - current_date: Текущая дата (объект date).
    :return: Объект datetime для ближайшего будущего дня и времени.
    """
    target_day = context["target_day"]
    target_time = context["target_time"]
    current_weekday = context["current_weekday"]
    current_date = context["current_date"]
    now = context["now"]

    # Разница в днях до ближайшего целевого дня
    days_until_target = (target_day - current_weekday) % 7
    target_date = current_date + timedelta(days=days_until_target)

    # Формируем целевую дату-время
    target_datetime = datetime.combine(target_date, datetime.min.time()) + timedelta(
        hours=target_time[0], minutes=target_time[1], seconds=target_time[2]
    )

    # Проверка, если целевой день и время уже прошли
    if days_until_target == 0 and now.time() >= target_datetime.time():
        target_datetime += timedelta(days=7)

    return target_datetime


now = datetime.strptime("13.12.24 17:59:59", "%d.%m.%y %H:%M:%S")  # datetime.now()
now = datetime.now()
current_weekday = now.weekday()
today = datetime.strptime("13.12.24", "%d.%m.%y")  # date.today()
today = date.today()
context = {
    "target_day": 4,
    "target_time": (17, 0, 0),
    "current_weekday": current_weekday,
    "current_date": today,
    "now": now,
}
this_friday_17 = get_next_day_with_time(context)
# print("this_friday_17 =", this_friday_17)
