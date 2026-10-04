from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("page_libre", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="pagelibresection",
            name="taille_image",
            field=models.CharField(
                choices=[("petit", "Petite"), ("moyen", "Moyenne"), ("grand", "Grande")],
                default="moyen",
                help_text="S'applique à l'image (à gauche ou à droite) ou aux images des colonnes. Sans effet pour une image en pleine largeur (fond). Une image n'est jamais agrandie au-delà de sa taille d'origine.",
                max_length=6,
                verbose_name="Taille des images",
            ),
        ),
    ]
