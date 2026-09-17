from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("planner", "0003_scheduleeditlock"),
    ]

    operations = [
        migrations.CreateModel(
            name="CalendarPeriod",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("year", models.PositiveSmallIntegerField(unique=True)),
                ("starts_on", models.DateField()),
                ("ends_on", models.DateField(blank=True, null=True)),
            ],
            options={
                "verbose_name": "Период Картики",
                "verbose_name_plural": "Периоды Картики",
            },
        ),
    ]
