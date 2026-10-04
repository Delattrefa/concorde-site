import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("navigation", "0003_footerlink_ouvrir_nouvel_onglet"),
        ("wagtailcore", "0094_alter_page_locale"),
        ("wagtailimages", "0027_image_description"),
    ]

    operations = [
        migrations.CreateModel(
            name="IdentiteVisuelle",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("favicon", models.ForeignKey(blank=True, help_text="Image carrée, idéalement au format PNG de 512 × 512 pixels, sur fond uni ou transparent. Une image non carrée est recadrée autour de son point d'intérêt. Sans image, une icône « C » aux couleurs du site est utilisée.", null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+", to="wagtailimages.image", verbose_name="Icône de l'onglet (logo)")),
                ("site", models.OneToOneField(editable=False, on_delete=django.db.models.deletion.CASCADE, to="wagtailcore.site")),
            ],
            options={
                "verbose_name": "Identité visuelle (icône du site)",
            },
        ),
    ]
