import re

from django.db import migrations


NEW_TITLE = "ISKCON Lietuvoje: Pagrindiniai veiklos principai"


def rename_principles_heading(apps, schema_editor):
    Post = apps.get_model("planner", "Post")
    post = Post.objects.filter(pk=22).first()
    if not post:
        return

    changed_fields = []
    if not post.title or post.title.strip().casefold() == "isd":
        post.title = NEW_TITLE
        changed_fields.append("title")

    updated_content = re.sub(
        r"(?im)^(#{1,3}[ \t]*)isd[ \t]*$",
        rf"\1{NEW_TITLE}",
        post.content,
        count=1,
    )
    updated_content = re.sub(
        r"(?is)(<h[1-3]\b[^>]*>\s*)isd(\s*</h[1-3]>)",
        rf"\1{NEW_TITLE}\2",
        updated_content,
        count=1,
    )
    if updated_content != post.content:
        post.content = updated_content
        changed_fields.append("content")

    if changed_fields:
        post.save(update_fields=changed_fields)


class Migration(migrations.Migration):
    dependencies = [("planner", "0010_multiple_calendar_periods")]

    operations = [
        migrations.RunPython(rename_principles_heading, migrations.RunPython.noop),
    ]
