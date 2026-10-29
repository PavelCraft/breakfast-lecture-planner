from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("planner", "0009_rename_bhaktu_perliukai_page"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="calendarperiod",
            name="year",
        ),
        migrations.AlterField(
            model_name="calendarperiod",
            name="starts_on",
            field=models.DateField(unique=True),
        ),
        migrations.AddConstraint(
            model_name="calendarperiod",
            constraint=models.CheckConstraint(
                condition=models.Q(ends_on__isnull=True) | models.Q(ends_on__gt=models.F("starts_on")),
                name="kartika_end_after_start",
            ),
        ),
    ]
