from django.db import migrations


REPLACEMENTS = {
    "[Экадаши]": "#Ekadaši",
    "[Пост]": "#Pasninkas",
    "[Праздник]": "#Šventės",
    "[Дни святых]": "#ŠventųjųDienos",
    "[Картика: начало]": "#KartikaPradžia",
    "[Картика: конец]": "#KartikaPabaiga",
}


def convert_markers_to_hashtags(apps, schema_editor):
    Post = apps.get_model("planner", "Post")
    DailySchedule = apps.get_model("planner", "DailySchedule")
    for model in (Post, DailySchedule):
        for instance in model.objects.all().only("pk", "content"):
            updated = instance.content
            for old, new in REPLACEMENTS.items():
                updated = updated.replace(old, new)
            if updated != instance.content:
                instance.content = updated
                instance.save(update_fields=["content"])


class Migration(migrations.Migration):
    dependencies = [("planner", "0011_rename_principles_heading")]

    operations = [
        migrations.RunPython(convert_markers_to_hashtags, migrations.RunPython.noop),
    ]
