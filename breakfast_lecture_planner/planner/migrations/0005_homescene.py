from django.db import migrations, models
import planner.models


class Migration(migrations.Migration):
    dependencies = [("planner", "0004_calendarperiod")]

    operations = [
        migrations.CreateModel(
            name="HomeScene",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("background", models.ImageField(blank=True, upload_to="home_scene/backgrounds/")),
                ("object_image", models.ImageField(blank=True, upload_to="home_scene/objects/")),
                ("layout", models.JSONField(default=planner.models.default_home_scene_layout)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
        ),
    ]
