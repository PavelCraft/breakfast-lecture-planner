import re

from django.db import migrations


def rename_creativity_page(apps, schema_editor):
    Post = apps.get_model("planner", "Post")
    post = Post.objects.filter(pk=21).first()
    if not post:
        return

    changed_fields = []
    if post.title in (None, "", "Šventyklos remonto darbai"):
        post.title = "Kūryba"
        changed_fields.append("title")

    updated_content = re.sub(
        r"(?im)^(#{1,3}[ \t]*)Šventyklos remonto darbai[ \t]*$",
        r"\1Kūryba",
        post.content,
        count=1,
    )
    updated_content = re.sub(
        r"(?is)(<h[1-3]\b[^>]*>\s*)Šventyklos remonto darbai(\s*</h[1-3]>)",
        r"\1Kūryba\2",
        updated_content,
        count=1,
    )
    if updated_content != post.content:
        post.content = updated_content
        changed_fields.append("content")

    if changed_fields:
        post.save(update_fields=changed_fields)


class Migration(migrations.Migration):
    dependencies = [("planner", "0007_scheduleeditlock_scope")]

    operations = [
        migrations.RunPython(rename_creativity_page, migrations.RunPython.noop),
    ]
