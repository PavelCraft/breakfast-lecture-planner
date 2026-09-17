from django.conf import settings
from django.conf.urls.static import static
from django.urls import path

from . import views

app_name = "planner"

urlpatterns = [
    path("old/", views.Planner.as_view(), name="planner"),
    # path('main/', views.Main.as_view(), name='main'),
    path("", views.CombinedView.as_view(), name="new"),
    path("cabinet", views.CabinetView.as_view(), name="cabinet"),
    path("schedule/edit-lock/", views.ScheduleEditLockView.as_view(), name="schedule_edit_lock"),
    path("schedule/unlock/", views.ScheduleEditUnlockView.as_view(), name="schedule_edit_unlock"),
    path("post/new/", views.PostCreateView.as_view(), name="post-create"),
    path("post/18/", views.DraftTextView.as_view(), name="draft_text"),
    path("draft_text/", views.DraftTextView.as_view(), name="draft_text"),
    path("post/<int:pk>/", views.PostDetailView.as_view(), name="post-detail"),
    path("post/<int:pk>/edit/", views.PostUpdateView.as_view(), name="post-edit"),
    path(
        "daily-schedule/",
        views.DailyScheduleView.as_view(),
        name="daily_schedule",
    ),
    path("contacts/", views.ContactsView.as_view(), name="contacts"),
    path("faq/", views.FaqView.as_view(), name="faq"),
    path("images/", views.ImageListView.as_view(), name="image_list"),
    path("images/scene-layout/", views.HomeSceneLayoutView.as_view(), name="home_scene_layout"),
    path("registracija/", views.LunchRegistrationView.as_view(), name="lunch_register"),
    path("lunch/success/", views.LunchSuccessView.as_view(), name="lunch_success"),
    path("lunch_closed/", views.LunchClosedView.as_view(), name="lunch_closed"),
    path(
        "lunch/participants/",
        views.LunchParticipantListView.as_view(),
        name="lunch_participants",
    ),
    path(
        "lunch/participants/all/",
        views.AllLunchParticipantListView.as_view(),
        name="all_lunch_participants",
    ),
    path(
        "lunch/participants/delete/<int:pk>/",
        views.LunchParticipantDeleteView.as_view(),
        name="delete_lunch_participant",
    ),
    path("feedback/", views.FeedbackView.as_view(), name="feedback"),
    path("remonto-darbai/", views.RenovationWork.as_view(), name="renovation_work"),
    path(
        "vaishnava-calendar/",
        views.VaishnavaCalendar.as_view(),
        name="vaishnava_calendar",
    ),
    path(
        "vaishnava-etiquette/",
        views.VaishnavaEtiquette.as_view(),
        name="vaishnava_etiquette",
    ),
    path(
        "cleanliness-standards/",
        views.CleanlinessStandards.as_view(),
        name="cleanliness_standards",
    ),
    path("philosophy/", views.Philosophy.as_view(), name="philosophy"),
    path("practice/", views.Practice.as_view(), name="practice"),
    path("principai/", views.IsdView.as_view(), name="principai"),
    path(
        "feedback/success/",
        views.FeedbackSuccessView.as_view(),
        name="feedback_success",
    ),
    path("nuorodos/", views.NuarodosView.as_view(), name="nuorodos"),
    path("archive/", views.ArchiveView.as_view(), name="archive"),
    path("text/new/", views.TextView.as_view(), name="text"),
    path("text/update/<int:pk>/", views.TextUpdateView.as_view(), name="text_update"),
    path("text/<int:pk>/", views.TextDetailView.as_view(), name="text_detail"),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
