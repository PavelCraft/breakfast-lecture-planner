from django.db import migrations, models


def keep_one_schedule_lock(apps, schema_editor):
    Lock = apps.get_model("planner", "ScheduleEditLock")
    locks = Lock.objects.order_by("-acquired_at", "-pk")
    current = locks.first()
    if current:
        locks.exclude(pk=current.pk).delete()


class Migration(migrations.Migration):
    dependencies = [("planner", "0006_home_scene_presets")]

    operations = [
        migrations.AddField(
            model_name="scheduleeditlock",
            name="scope",
            field=models.CharField(default="schedule", max_length=16),
        ),
        migrations.RunPython(keep_one_schedule_lock, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="scheduleeditlock",
            name="scope",
            field=models.CharField(default="schedule", max_length=16, unique=True),
        ),
    ]
