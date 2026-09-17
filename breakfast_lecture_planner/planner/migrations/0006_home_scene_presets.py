from django.db import migrations


def expand_presets(apps, schema_editor):
    HomeScene = apps.get_model("planner", "HomeScene")
    for scene in HomeScene.objects.all():
        old = scene.layout or {}
        if all(name in old for name in ("watch", "smartphone", "shovel", "tablet", "computer", "tv")):
            continue
        phone = old.get("phone") or old.get("smartphone") or {}
        tablet = old.get("tablet") or phone
        desktop = old.get("desktop") or old.get("computer") or tablet
        scene.layout = {
            "watch": old.get("watch", phone.copy()),
            "smartphone": old.get("smartphone", phone.copy()),
            "shovel": old.get("shovel", tablet.copy()),
            "tablet": tablet.copy(),
            "computer": old.get("computer", desktop.copy()),
            "tv": old.get("tv", desktop.copy()),
        }
        scene.save(update_fields=["layout"])


class Migration(migrations.Migration):
    dependencies = [("planner", "0005_homescene")]

    operations = [migrations.RunPython(expand_presets, migrations.RunPython.noop)]
