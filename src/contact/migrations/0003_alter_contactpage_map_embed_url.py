from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("contact", "0002_contactpage_canonical_url_contactpage_og_image"),
    ]

    operations = [
        migrations.AlterField(
            model_name="contactpage",
            name="map_embed_url",
            field=models.TextField(
                blank=True,
                help_text=(
                    "Dans Google Maps : Partager > Intégrer une carte > COPIER LE CODE HTML, "
                    "puis collez ici le code complet (<iframe ...></iframe>). "
                    "Un lien de partage (maps.app.goo.gl) ne fonctionne pas."
                ),
                verbose_name="Carte Google Maps",
            ),
        ),
    ]
