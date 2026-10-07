import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("calendrier", "0007_libelle_reservation_annulee"),
        ("wagtailimages", "0027_image_description"),
    ]

    operations = [
        migrations.AddField(
            model_name="contratlocation",
            name="signature",
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                related_name="+", to="wagtailimages.image", verbose_name="Signature du délégué",
            ),
        ),
        migrations.CreateModel(
            name="MiseEnPageContrat",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("image_entete", models.ImageField(blank=True, help_text="Affichée en bandeau en haut de la première page, derrière le nom de l'ASBL. Format paysage conseillé (environ 2000 × 450 pixels).", upload_to="contrat_mise_en_page/", verbose_name="Image de fond de l'en-tête")),
                ("eclaircir_entete", models.BooleanField(default=True, verbose_name="Éclaircir l'image pour garder le texte lisible")),
                ("date_modification", models.DateTimeField(auto_now=True, verbose_name="Dernière modification")),
            ],
            options={
                "verbose_name": "Mise en page du contrat",
                "verbose_name_plural": "Mise en page du contrat",
            },
        ),
    ]
