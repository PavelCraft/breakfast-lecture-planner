import html
import re
from datetime import date, datetime, time, timedelta
from math import pi

from calendar_utils.utils import get_next_day_with_time
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db import models, transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.utils.translation import gettext as _
from django.views import View
from django.views.generic import DeleteView, DetailView, ListView
from django.views.generic.edit import CreateView, UpdateView
from markdown import markdown

from .forms import (
    FeedbackForm,
    ImageUploadForm,
    LunchParticipantForm,
    MainPostEditorForm,
    DailyScheduleForm,
    PostForm,
)
from .models import CalendarPeriod, DailySchedule, Image, LunchParticipant, Post, ScheduleEditLock
from .services.calendar_markers import categories_in_html, decorated_main_content, public_day_content
from .services.schedule_parser import ScheduleStructureError, parse_schedule
from .services.schedule_sync import sync_daily_schedules, sync_day_to_main_schedule
from .tasks import queue_admin_notification

def is_admin(user):
    return user.groups.filter(name="Админ").exists()


LOCK_LIFETIME = timedelta(hours=2)


def _active_schedule_lock():
    ScheduleEditLock.objects.filter(expires_at__lte=timezone.now()).delete()
    return ScheduleEditLock.objects.select_related("user").first()


def _owns_schedule_lock(request):
    token = request.POST.get("edit_lock_token", "")
    lock = _active_schedule_lock()
    return bool(lock and lock.token == token and lock.user_id == request.user.id)


class ContactsView(View):
    template_name = "planner/contacts.html"

    def get(self, request):
        return render(request, self.template_name)


@method_decorator(login_required, name="dispatch")
class FaqView(View):
    template_name = "planner/FAQ.html"

    def get(self, request):
        return render(request, self.template_name)


class CombinedView(DetailView):
    model = Post
    template_name = "planner/combined.html"

    def get_object(self, queryset=None):
        return get_object_or_404(Post, pk=12)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        post = self.get_object()

        # Получаем текущий день недели на литовском
        days_of_week = [
            "Pirmadienis",  # Понедельник
            "Antradienis",  # Вторник
            "Trečiadienis",  # Среда
            "Ketvirtadienis",  # Четверг
            "Penktadienis",  # Пятница
            "Šeštadienis",  # Суббота
            "Sekmadienis",  # Воскресенье
        ]
        local_today = timezone.localdate()
        current_day = days_of_week[local_today.weekday()]
        current_date_heading = f"{local_today.day} d. {current_day}"
        current_week_friday = local_today + timedelta(days=4 - local_today.weekday())
        current_friday_heading = f"{current_week_friday.day} d. Penktadienis"

        # Разделяем контент на строки
        lines = post.content.splitlines()
        is_ckeditor_html = bool(
            re.search(r"<h[1-6]\b", post.content, flags=re.IGNORECASE)
        )

        # Обрамляем строку с текущим днем и добавляем ссылку только для первой недели
        highlighted_lines = []
        user_content_lines = []
        data = {"not_schedule_text": []}
        key = None

        # Получаем URL для регистрации
        registration_url = reverse("planner:lunch_register")

        for line in lines:
            if "savaitė" in line:
                if key:
                    data[key].extend(highlighted_lines)
                    user_content_lines.extend(highlighted_lines)
                    highlighted_lines = []
                key = line
                data[key] = []
            if key in data:
                if line == key:
                    continue
                highlighted_lines.append(line)
            else:
                data["not_schedule_text"].append(line)
        if key and key in data:
            data[key].extend(highlighted_lines)
            user_content_lines.extend(highlighted_lines)

        # Соединяем строки обратно в один текст
        highlighted_content = "\n".join(user_content_lines)

        context["title"] = _("Home")
        context["content"] = markdown(
            post.content if is_ckeditor_html else highlighted_content
        )
        context["image"] = post.image

        not_schedule_text = data["not_schedule_text"]
        del data["not_schedule_text"]

        data = {
            markdown(key): (
                markdown("\n".join(value))
                if isinstance(value, list)
                else markdown(value)
            )
            for key, value in data.items()
        }
        if is_ckeditor_html:
            # HTML CKEditor не нужно повторно делить на недели как Markdown.
            # Иначе вся однострочная разметка становится ключом data, и шаблон
            # выводит её до того, как добавлены today и Registracija.
            data = {}

        # CKEditor может добавлять атрибуты и вложенные теги в заголовок.
        # Сравниваем только его текст, а сохранённое содержимое поста не меняем.
        heading_pattern = re.compile(r"<h6\b[^>]*>.*?</h6>", re.IGNORECASE | re.DOTALL)
        today_anchor_added = False
        registration_link_added = False
        registration_link = (
            '<span style="color: red; font-weight: bold;">'
            f'<a href="{registration_url}" style="color: red;">Registracija</a>'
            "</span>"
        )

        def decorate_schedule_heading(match):
            nonlocal today_anchor_added, registration_link_added

            heading_html = match.group(0)
            heading_text = re.sub(r"<[^>]+>", "", heading_html)
            heading_text = " ".join(html.unescape(heading_text).split())
            heading_without_registration = re.sub(
                r"\s+Registracija\s*$", "", heading_text, flags=re.IGNORECASE
            )

            if (
                not registration_link_added
                and heading_without_registration.casefold()
                == current_friday_heading.casefold()
            ):
                if heading_text == heading_without_registration:
                    heading_html = re.sub(
                        r"</h6>\s*$",
                        f" {registration_link}</h6>",
                        heading_html,
                        count=1,
                        flags=re.IGNORECASE,
                    )
                registration_link_added = True

            if (
                not today_anchor_added
                and heading_without_registration.casefold()
                == current_date_heading.casefold()
            ):
                heading_html = f'<div id="today">{heading_html}</div>'
                today_anchor_added = True

            return heading_html

        # CKEditor обычно сохраняет весь HTML без переводов строк. В этом случае
        # старый разбор по неделям оставляет data пустым, и шаблон выводит content.
        context["content"] = heading_pattern.sub(
            decorate_schedule_heading, context["content"]
        )
        marker_display = decorated_main_content if self.request.user.is_authenticated else public_day_content
        context["content"] = marker_display(context["content"])

        for key, value in data.items():
            data[key] = marker_display(heading_pattern.sub(decorate_schedule_heading, value))

        if not_schedule_text and not is_ckeditor_html:
            data["not_schedule_text"] = markdown("\n".join(not_schedule_text))

        context["data"] = data

        countdown = [
            {"value": 0, "label": _("days"), "degrees": 0},
            {"value": 0, "label": _("hours"), "degrees": 0},
            {"value": 0, "label": _("min"), "degrees": 0},
            {"value": 0, "label": _("sec"), "degrees": 0},
        ]

        now = datetime.strptime("13.12.24 17:59:59", "%d.%m.%y %H:%M:%S")
        now = datetime.now()
        current_weekday = now.weekday()
        today = datetime.strptime("13.12.24", "%d.%m.%y")
        today = date.today()

        if not (
            current_weekday == 4 and now.time() > time(17, 0) or (current_weekday == 5)
        ):

            context.update(
                {
                    "target_day": 4,
                    "target_time": (17, 0, 0),
                    "current_weekday": current_weekday,
                    "current_date": today,
                    "now": now,
                }
            )

            next_friday_17 = get_next_day_with_time(context)
            # print(next_friday_17, type(next_friday_17))
            context["next_friday_17"] = (
                next_friday_17.year,
                next_friday_17.month,
                next_friday_17.day,
                next_friday_17.hour,
                next_friday_17.minute,
                next_friday_17.second,
            )

            riga_now = timezone.localtime(timezone.now())
            print("riga_now =", riga_now)
            context["now_tuple"] = (
                riga_now.year,
                riga_now.month,
                riga_now.day,
                riga_now.hour,
                riga_now.minute,
                riga_now.second,
            )
            # context["now_tuple"] = (2025, 3, 13, 2, 59, 45)
            # context["now_tuple"] = (2025, 3, 13, 16, 58, 55)
            delta = next_friday_17 - now
            print(delta, type(delta))
            print(delta.days, delta.seconds)
            days = delta.days
            hours = delta.seconds // 3600
            minutes = (delta.seconds % 3600) // 60
            seconds = delta.seconds % 60

        #     countdown[0]["value"] = days
        #     countdown[0]["degrees"] = 360 - (days / 7 * 360)
        #     print('Угол дня countdown[0]["degrees"] =', countdown[0]["degrees"])

        #     for index, time_element in enumerate(countdown[1:]):

        #         value = [hours, minutes, seconds][index]
        #         print(value)
        #         countdown[index + 1]["value"] = value
        #         countdown[index + 1]["degrees"] = 360 - (value / 60 * 360)

        # # Радиус окружности
        # radius = 41
        # # Длина окружности (2 * π * радиус)
        # circumference = 2 * pi * radius

        # # Добавляем в каждый элемент списка расчёт значения для stroke-dasharray
        # for unit in countdown:
        #     # Рассчитываем длину дуги для текущего прогресса
        #     unit['stroke_dasharray'] = (unit['degrees'] / 360) * circumference

        # Отправляем в контекст
        context["countdown"] = countdown
        # Добавляем список групп, которым будет разрешено редактирование страницы
        context["allowed_groups"] = ["Админ"]
        if self.request.user.is_authenticated and is_admin(self.request.user):
            context["editor_form"] = MainPostEditorForm(instance=post)
            context["daily_schedule_form"] = DailyScheduleForm(prefix="daily")
            context["unified_editor"] = True
        print("/n---------------/n")
        # print(context["now_tuple"])
        print("/n------------/n")
        print("/n---------------/n")
        print(context.keys())
        print("/n------------/n")
        return context


class DailyScheduleView(View):
    def get(self, request):
        date_value = request.GET.get("date", "")
        try:
            schedule_date = date.fromisoformat(date_value)
        except ValueError:
            return JsonResponse({"error": "Некорректная дата"}, status=400)

        current_monday = timezone.localdate() - timedelta(days=timezone.localdate().weekday())
        schedule = DailySchedule.objects.filter(date=schedule_date).first()
        if schedule_date < current_monday and not request.user.is_authenticated:
            schedule = None
        period = CalendarPeriod.objects.filter(
            starts_on__lte=schedule_date
        ).filter(
            models.Q(ends_on__gte=schedule_date) | models.Q(ends_on__isnull=True)
        ).order_by("-starts_on").first()
        editing_period = CalendarPeriod.objects.filter(
            year__in=(schedule_date.year - 1, schedule_date.year)
        ).order_by("-starts_on").first()
        raw_content = schedule.content if schedule else ""
        response = JsonResponse(
            {
                "date": schedule_date.isoformat(),
                "content": public_day_content(raw_content),
                "raw_content": raw_content if request.user.is_authenticated and is_admin(request.user) else "",
                "categories": categories_in_html(raw_content),
                "kartika": period is not None,
                "kartika_start": editing_period.starts_on.isoformat() if editing_period else None,
                "kartika_end": editing_period.ends_on.isoformat() if editing_period and editing_period.ends_on else None,
                "exists": schedule is not None,
            }
        )
        response["Cache-Control"] = "no-store, private"
        return response

    def post(self, request):
        if not request.user.is_authenticated or not is_admin(request.user):
            return JsonResponse({"error": "Недостаточно прав"}, status=403)
        if not _owns_schedule_lock(request):
            return JsonResponse(
                {"error": "Блокировка редактирования истекла или принадлежит другой вкладке."}, status=409
            )

        date_value = request.POST.get("date", "")
        try:
            schedule_date = date.fromisoformat(date_value)
        except ValueError:
            return JsonResponse({"error": "Некорректная дата"}, status=400)

        schedule = DailySchedule.objects.filter(date=schedule_date).first()
        form = DailyScheduleForm(request.POST, instance=schedule, prefix="daily")
        if not form.is_valid():
            return JsonResponse({"errors": form.errors.get_json_data()}, status=400)

        try:
            schedule, post = sync_day_to_main_schedule(
                schedule_date, form.cleaned_data["content"]
            )
        except ScheduleStructureError as error:
            queue_admin_notification(
                "Ошибка синхронизации дневного расписания",
                f"Дата: {schedule_date:%d.%m.%Y}\n\n{error}",
            )
            return JsonResponse({"error": str(error)}, status=400)
        return JsonResponse(
            {
                "date": schedule.date.isoformat(),
                "content": public_day_content(schedule.content),
                "raw_content": schedule.content,
                "categories": categories_in_html(schedule.content),
                "main_content": decorated_main_content(markdown(post.content)),
                "updated_at": schedule.updated_at.isoformat(),
            }
        )


@method_decorator(login_required, name="dispatch")
@method_decorator(user_passes_test(is_admin), name="dispatch")
class ScheduleEditLockView(View):
    def post(self, request):
        action = request.POST.get("action")
        token = request.POST.get("token", "")
        if not token:
            return JsonResponse({"error": "Не передан идентификатор вкладки."}, status=400)
        with transaction.atomic():
            Post.objects.select_for_update().get(pk=12)
            lock = _active_schedule_lock()
            if action == "acquire":
                if lock and (lock.token != token or lock.user_id != request.user.id):
                    return JsonResponse({
                        "error": f"Расписание уже редактирует {lock.user.get_username()}. Дождитесь сохранения или выхода из режима редактирования.",
                        "locked_by": lock.user.get_username(),
                    }, status=409)
                if lock:
                    lock.expires_at = timezone.now() + LOCK_LIFETIME
                    lock.save(update_fields=["expires_at"])
                else:
                    ScheduleEditLock.objects.create(user=request.user, token=token, expires_at=timezone.now() + LOCK_LIFETIME)
                return JsonResponse({"acquired": True})
            if action == "release":
                ScheduleEditLock.objects.filter(token=token, user=request.user).delete()
                return JsonResponse({"released": True})
        return JsonResponse({"error": "Неизвестное действие."}, status=400)


@method_decorator(login_required, name="dispatch")
@method_decorator(user_passes_test(is_admin), name="dispatch")
class ScheduleEditUnlockView(View):
    template_name = "planner/schedule_edit_unlock.html"

    def get(self, request):
        return render(request, self.template_name, {"edit_lock": _active_schedule_lock()})

    def post(self, request):
        ScheduleEditLock.objects.all().delete()
        return render(request, self.template_name, {"edit_lock": None, "unlocked": True})


class Main(View):
    template_name = "planner/main.html"

    def get(self, request):
        countdown = [
            {"value": 0, "label": "days", "degrees": 0},
            {"value": 0, "label": "hours", "degrees": 0},
            {"value": 0, "label": "min", "degrees": 0},
            {"value": 0, "label": "sec", "degrees": 0},
        ]

        now = datetime.strptime("13.12.24 17:59:59", "%d.%m.%y %H:%M:%S")
        now = datetime.now()
        current_weekday = now.weekday()
        today = datetime.strptime("13.12.24", "%d.%m.%y")
        today = date.today()

        if not (
            current_weekday == 4 and now.time() > time(17, 0) or (current_weekday == 5)
        ):

            context = {
                "target_day": 4,
                "target_time": (17, 0, 0),
                "current_weekday": current_weekday,
                "current_date": today,
                "now": now,
            }
            next_friday_17 = get_next_day_with_time(context)
            print(next_friday_17)
            delta = next_friday_17 - now
            print(delta, type(delta))
            print(delta.days, delta.seconds)
            days = delta.days
            hours = delta.seconds // 3600
            minutes = (delta.seconds % 3600) // 60
            seconds = delta.seconds % 60

            countdown[0]["value"] = days
            countdown[0]["degrees"] = 360 - (days / 7 * 360)

            for index, time_element in enumerate(countdown[1:]):

                value = [hours, minutes, seconds][index]
                print(value)
                countdown[index + 1]["value"] = value
                countdown[index + 1]["degrees"] = 360 - (value / 60 * 360)

        # Радиус окружности
        radius = 41
        # Длина окружности (2 * π * радиус)
        circumference = 2 * pi * radius

        # Добавляем в каждый элемент списка расчёт значения для stroke-dasharray
        for unit in countdown:
            # Рассчитываем длину дуги для текущего прогресса
            unit["stroke_dasharray"] = (unit["degrees"] / 360) * circumference

        # Отправляем в контекст
        context = {
            "countdown": countdown,
        }
        return render(request, self.template_name, context)


@method_decorator(login_required, name="dispatch")
@method_decorator(user_passes_test(is_admin), name="dispatch")
class CabinetView(View):
    template_name = "planner/cabinet.html"

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name)


class Planner(DetailView):
    model = Post
    template_name = "planner/post.html"

    def get(self, request, *args, **kwargs):
        return redirect("planner:new")

    def get_object(self, queryset=None):
        return get_object_or_404(Post, pk=12)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        post = self.get_object()

        # Получаем текущий день недели на литовском
        days_of_week = [
            "Pirmadienis",  # Понедельник
            "Antradienis",  # Вторник
            "Trečiadienis",  # Среда
            "Ketvirtadienis",  # Четверг
            "Penktadienis",  # Пятница
            "Šeštadienis",  # Суббота
            "Sekmadienis",  # Воскресенье
        ]
        current_day = days_of_week[datetime.now().weekday()]

        # Разделяем контент на строки
        lines = post.content.splitlines()

        # Обрамляем строку с текущим днем и добавляем ссылку только для первой недели
        highlighted_lines = []
        user_content_lines = []
        current_day_found = False
        saturday_found = False
        data = {"not_schedule_text": []}
        key = None

        # Получаем URL для регистрации
        registration_url = reverse("planner:lunch_register")

        for line in lines:
            if "savaitė" in line:
                if key:
                    data[key].extend(highlighted_lines)
                    user_content_lines.extend(highlighted_lines)
                    highlighted_lines = []
                key = line
                data[key] = []
            if key in data:
                if line == key:
                    continue
                if "Šeštadienis" in line and not saturday_found:
                    path = '{% url "planner:lunch_register" %}'
                    registration_link = (
                        '<span style="color: red; font-weight: bold;">'
                        f'<a href="{registration_url}">Registracija</a>'
                        "</span>"
                    )
                    line = line.replace(line, f"{line} {registration_link}")
                    saturday_found = True
                # Обрабатываем строку с текущим днем
                if current_day in line and not current_day_found:
                    highlighted_line = (
                        f'<div id="today"">'
                        f'<h6>{line.replace("#", "").strip()}</h6>'
                        f"</div>"
                    )
                    highlighted_lines.append(highlighted_line)
                    current_day_found = True
                else:
                    highlighted_lines.append(line)
            else:
                data["not_schedule_text"].append(line)
        data[key].extend(highlighted_lines)
        user_content_lines.extend(highlighted_lines)

        # Соединяем строки обратно в один текст
        highlighted_content = "\n".join(user_content_lines)

        context["content"] = markdown(highlighted_content)
        context["title"] = "Tvarkaraštis"
        context["image"] = post.image

        not_schedule_text = data["not_schedule_text"]
        del data["not_schedule_text"]

        data = {
            markdown(key): (
                markdown("\n".join(value))
                if isinstance(value, list)
                else markdown(value)
            )
            for key, value in data.items()
        }

        if not_schedule_text:  # Проверяем, что значение не пустое
            data["not_schedule_text"] = markdown("\n".join(not_schedule_text))

        context["data"] = data
        context["allowed_groups"] = ["Админ"]
        return context


@method_decorator(login_required, name="dispatch")
@method_decorator(user_passes_test(is_admin), name="dispatch")
class PostCreateView(CreateView):
    model = Post
    form_class = PostForm
    template_name = "planner/post_form.html"

    def get_success_url(self):
        return reverse_lazy("planner:post-detail", kwargs={"pk": self.object.pk})


class PostDetailView(DetailView):
    model = Post
    template_name = "planner/combined.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        post = self.get_object()
        context["content"] = markdown(post.content)
        countdown = [
            {"value": 0, "label": "days", "degrees": 0},
            {"value": 0, "label": "hours", "degrees": 0},
            {"value": 0, "label": "min", "degrees": 0},
            {"value": 0, "label": "sec", "degrees": 0},
        ]

        now = datetime.strptime("13.12.24 17:59:59", "%d.%m.%y %H:%M:%S")
        now = datetime.now()
        current_weekday = now.weekday()
        today = datetime.strptime("13.12.24", "%d.%m.%y")
        today = date.today()

        if not (
            current_weekday == 4 and now.time() > time(17, 0) or (current_weekday == 5)
        ):

            context.update(
                {
                    "target_day": 4,
                    "target_time": (17, 0, 0),
                    "current_weekday": current_weekday,
                    "current_date": today,
                    "now": now,
                }
            )

            next_friday_17 = get_next_day_with_time(context)
            context["next_friday_17"] = (
                next_friday_17.year,
                next_friday_17.month,
                next_friday_17.day,
                next_friday_17.hour,
                next_friday_17.minute,
                next_friday_17.second,
            )

            riga_now = timezone.localtime(timezone.now())
            context["now_tuple"] = (
                riga_now.year,
                riga_now.month,
                riga_now.day,
                riga_now.hour,
                riga_now.minute,
                riga_now.second,
            )

        # Отправляем в контекст
        context["countdown"] = countdown
        context["allowed_groups"] = ["Админ"]
        return context


@method_decorator(login_required, name="dispatch")
@method_decorator(user_passes_test(is_admin), name="dispatch")
class PostUpdateView(UpdateView):
    model = Post
    form_class = MainPostEditorForm
    template_name = "planner/post_form.html"

    def get(self, request, *args, **kwargs):
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            post = self.get_object()
            try:
                day_dates = [day.date.isoformat() for day in parse_schedule(post.content, reference_date=timezone.localdate()).days]
            except ScheduleStructureError:
                day_dates = []
            period = CalendarPeriod.objects.order_by("-starts_on").first()
            response = JsonResponse(
                {
                    "id": post.pk,
                    "content": post.content,
                    "day_dates": day_dates,
                    "kartika_start": period.starts_on.isoformat() if period else None,
                    "kartika_end": period.ends_on.isoformat() if period and period.ends_on else None,
                }
            )
            response["Cache-Control"] = "no-store, private"
            return response
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        if self.kwargs.get("pk") == 12 and not _owns_schedule_lock(request):
            return JsonResponse(
                {"error": "Блокировка редактирования истекла или принадлежит другой вкладке."}, status=409
            )
        self.object = self.get_object()
        form = self.get_form()

        if form.is_valid():
            self.object = form.save()
            warning = None
            if self.object.pk == 12:
                try:
                    sync_daily_schedules(self.object)
                except ScheduleStructureError as error:
                    warning = str(error)
                    queue_admin_notification(
                        "Ошибка разбора большого расписания",
                        f"Большое текстовое поле сохранено, но дневные расписания не обновлены.\n\n{error}",
                    )
            return JsonResponse({"content": decorated_main_content(markdown(self.object.content)), "warning": warning})

        return JsonResponse({"error": "Invalid form"}, status=400)


class NuarodosView(PostDetailView):
    def get_object(self, queryset=None):
        # Возвращаем объект с pk=15
        return Post.objects.get(pk=15)


class VaishnavaCalendar(PostDetailView):
    extra_context = {"title": "Vaišnavų kalendorius"}

    def get_object(self, queryset=None):
        return Post.objects.get(pk=14)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["allowed_groups"] = ["Админ", "Энтузиаст"]
        return context


class VaishnavaEtiquette(PostDetailView):
    extra_context = {"title": "Vaišnavų etiketas"}

    def get_object(self, queryset=None):
        return Post.objects.get(pk=20)


class RenovationWork(PostDetailView):
    extra_context = {"title": "Šventyklos remonto darbai"}

    def get_object(self, queryset=None):
        return Post.objects.get(pk=21)


class IsdView(PostDetailView):
    extra_context = {"title": "isd"}

    def get_object(self, queryset=None):
        return Post.objects.get(pk=22)


class CleanlinessStandards(PostDetailView):
    extra_context = {"title": "Švaros standartai"}

    def get_object(self, queryset=None):
        return Post.objects.get(pk=23)


class Philosophy(PostDetailView):
    extra_context = {"title": "filosofija"}

    def get_object(self, queryset=None):
        return Post.objects.get(pk=24)


class Practice(PostDetailView):
    extra_context = {"title": "praktika"}

    def get_object(self, queryset=None):
        return Post.objects.get(pk=25)


@method_decorator(login_required, name="dispatch")
class ArchiveView(PostDetailView):
    def get_object(self, queryset=None):
        return Post.objects.get(pk=17)


class ImageListView(View):
    def get(self, request):
        images = Image.objects.all()  # Получаем все изображения
        context = {"images": images}
        return render(request, "planner/image_list.html", context)


class ImageUploadView(View):
    def get(self, request):
        form = ImageUploadForm()
        return render(request, "planner/image_upload.html", {"form": form})

    def post(self, request):
        form = ImageUploadForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            return redirect(
                "planner:image_list"
            )  # Перенаправление на страницу со списком изображений
        return render(request, "planner/image_upload.html", {"form": form})


class DeleteImageView(View):
    def get(self, request, image_id):
        image = get_object_or_404(Image, id=image_id)
        image.delete()
        return redirect("planner:image_list")


class AddToHomeView(View):
    def get(self, request, image_id):
        image = get_object_or_404(Image, id=image_id)
        post = get_object_or_404(Post, pk=12)  # Получаем пост с pk=12
        post.image = image  # Устанавливаем изображение
        post.save()  # Сохраняем изменения
        return JsonResponse(
            {"success": True, "message": "Изображение добавлено на главную!"}
        )


class LunchRegistrationView(View):
    template_name = "planner/registration_or_feedback.html"

    def get(self, request):
        # Логика вычисления даты
        # now = datetime.strptime("20.12.24 17:00:01", "%d.%m.%y %H:%M:%S")
        now = datetime.now()
        current_weekday = now.weekday()

        if current_weekday == 4 and now.time() > time(17, 0) or (current_weekday == 5):
            error_message = "Registration is over"
            return redirect(
                f"{reverse('planner:lunch_closed')}?message={error_message}"
            )

        form = LunchParticipantForm()
        return render(
            request,
            self.template_name,
            {
                "form": form,
                "title": _("Saturday lunch registration"),
                "register_lunch": True,
                "header_title": _("Saturday lunch registration"),
                "text": _("Dear guests of Sri Sri Nitai Gaurasundara Temple! To make sure there is enough prasadam for everyone, please tell us in advance how many lunch portions you would like."),
            },
        )

    def post(self, request):
        form = LunchParticipantForm(request.POST)
        print("Мы в методе post")

        # Защита от спама роботов
        if form.is_valid():
            if form.cleaned_data.get("robot"):
                print("Это робот")
                return redirect("planner:lunch_success")
            if not form.cleaned_data.get("error_message"):
                participant = form.save()

                # Формируем текст уведомления
                subject = (
                    f"{participant.name} зарегистрировался на обед {participant.date}"
                )
                message = (
                    f"Пользователь по имени {participant.name} с email {participant.email},\n"
                    f"зарегистрировался на субботний обед, который состоится: {participant.date}.\n"
                    f"Количество порций: {participant.portions}"
                )
                if participant.comment:
                    message += f",\nКомментарий: {participant.comment}"

                queue_admin_notification(subject, message, participant.email)

                return redirect("planner:lunch_success")

        print("Форма не валидна")
        if form.cleaned_data.get("error_message"):
            error_message = form.cleaned_data.get("error_message")
            return redirect(
                f"{reverse('planner:lunch_closed')}?message={error_message}"
            )

        return render(
            request,
            self.template_name,
            {
                "form": form,
                "title": _("Lunch registration"),
                "errors": form.errors,  # Можно передать ошибки в контекст для отображения на странице
            },
        )


class LunchSuccessView(View):
    template_name = "planner/success.html"

    def get(self, request):
        return render(
            request,
            self.template_name,
            context={"title": _("You are registered!"), "form": "lunch"},
        )


class LunchClosedView(View):
    template_name = "planner/success.html"

    def get(self, request):
        message = request.GET.get("message")
        context = {
            "title": _("Registration failed"),
            "form": "registration_failed",
            "message": message,
        }
        return render(request, self.template_name, context=context)


class LunchParticipantListView(ListView):
    template_name = "planner/lunch_participants.html"

    def get(self, request):
        one_day_ago = timezone.now() - timedelta(days=1)
        participants = LunchParticipant.objects.filter(date__gte=one_day_ago)
        context = {
            "participants": participants,
        }

        return render(request, self.template_name, context)


class AllLunchParticipantListView(ListView):
    model = LunchParticipant
    template_name = "planner/lunch_participants.html"
    context_object_name = "participants"


class FeedbackView(View):
    template_name = "planner/registration_or_feedback.html"  # Универсальное название

    def get_context_data(self):
        return {"title": _("Feedback"), "header_title": _("Feedback")}

    def get(self, request):
        context = self.get_context_data()
        form = FeedbackForm()
        context["form"] = form
        return render(request, self.template_name, context)

    def post(self, request):
        form = FeedbackForm(request.POST)
        if form.is_valid():
            if form.cleaned_data.get("robot"):
                print("Это робот")
                return redirect("planner:feedback_success")

            feedback = form.save()

            subject = f"Обратная связь от {feedback.name}"
            message = f"Пользователь по имени {feedback.name} с email {feedback.email}, оставил обратную связь:\n{feedback.text}"
            queue_admin_notification(subject, message, feedback.email)

            return redirect(
                "planner:feedback_success"
            )  # Перенаправление на страницу успеха

        context = self.get_context_data()
        context["form"] = form
        return render(request, self.template_name, context)


class FeedbackSuccessView(View):
    template_name = "planner/success.html"

    def get(self, request):
        return render(
            request,
            self.template_name,
            context={"title": _("Message sent!"), "form": "feedback"},
        )


@method_decorator(login_required, name="dispatch")
@method_decorator(user_passes_test(is_admin), name="dispatch")
class LunchParticipantDeleteView(DeleteView):
    model = LunchParticipant
    template_name = "planner/delete_person.html"
    success_url = reverse_lazy("planner:lunch_participants")
    extra_context = {"path": "planner:lunch_participants"}


class PageNotFoundView(View):
    def get(self, request, *args, **kwargs):
        return render(request, "planner/404.html", {"path": request.path}, status=404)


from django.shortcuts import render
from django.views import View

from .forms import TextForm
from .models import Text


@method_decorator(login_required, name="dispatch")
@method_decorator(user_passes_test(is_admin), name="dispatch")
class TextView(View):
    template_name = "planner/text.html"

    def get(self, request, *args, **kwargs):
        form = TextForm()
        return render(
            request,
            self.template_name,
            {"myform": form, "editor_open": True},
        )

    def post(self, request, *args, **kwargs):
        form = TextForm(request.POST)
        if form.is_valid():
            text = form.save()
            return redirect("planner:text_detail", pk=text.pk)
        return render(
            request,
            self.template_name,
            {"myform": form, "editor_open": True},
        )


class TextDetailView(DetailView):
    model = Text
    template_name = (
        "planner/text_detail.html"  # Укажи свой шаблон для отображения текста
    )
    context_object_name = "text"

    def get_object(self):
        # Получаем объект текста по pk
        return get_object_or_404(Text, pk=self.kwargs["pk"])


@method_decorator(login_required, name="dispatch")
@method_decorator(user_passes_test(is_admin), name="dispatch")
class TextUpdateView(UpdateView):
    model = Text
    form_class = TextForm
    template_name = "planner/text.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["myform"] = context["form"]
        return context

    def get_success_url(self):
        return reverse_lazy("planner:text_detail", kwargs={"pk": self.object.pk})


@method_decorator(login_required, name="dispatch")
@method_decorator(user_passes_test(is_admin), name="dispatch")
class DraftTextView(DetailView):
    template_name = "planner/post.html"
    extra_context = {"title": "Черновик"}

    def get_object(self, queryset=None):
        return Post.objects.get(pk=18)
