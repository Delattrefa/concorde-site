from django.db import migrations


def creer(apps, schema_editor):
    apps.get_model("planning", "Canal").objects.get_or_create(
        nom="Général", evenement=None,
        defaults={"description": "Discussions ouvertes à tous les membres de l'ASBL."},
    )


class Migration(migrations.Migration):
    dependencies = [("planning", "0001_initial")]

    operations = [migrations.RunPython(creer, migrations.RunPython.noop)]
