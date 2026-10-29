import re

from django.db import migrations


def rename_bhaktu_perliukai_page(apps, schema_editor):
    Post = apps.get_model("planner", "Post")
    post = Post.objects.filter(pk=21).first()
    if not post:
        return

    changed_fields = []
    if post.title in (None, "", "Kūryba", "Šventyklos remonto darbai"):
        post.title = "Bhaktų perliukai"
        changed_fields.append("title")

    legacy_titles = r"(?:Kūryba|Šventyklos remonto darbai)"
    updated_content = re.sub(
        rf"(?im)^(#{{1,3}}[ \t]*){legacy_titles}[ \t]*$",
        r"\1Bhaktų perliukai",
        post.content,
        count=1,
    )
    updated_content = re.sub(
        rf"(?is)(<h[1-3]\b[^>]*>\s*){legacy_titles}(\s*</h[1-3]>)",
        r"\1Bhaktų perliukai\2",
        updated_content,
        count=1,
    )
    if updated_content != post.content:
        post.content = updated_content
        changed_fields.append("content")

    if changed_fields:
        post.save(update_fields=changed_fields)


class Migration(migrations.Migration):
    dependencies = [("planner", "0008_rename_creativity_page")]

    operations = [
        migrations.RunPython(rename_bhaktu_perliukai_page, migrations.RunPython.noop),
    ]
