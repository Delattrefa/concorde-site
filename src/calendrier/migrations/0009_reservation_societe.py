from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("calendrier", "0008_signature_et_mise_en_page"),
    ]

    operations = [
        migrations.AddField(
            model_name="reservation",
            name="type_client",
            field=models.CharField(
                choices=[("particulier", "Particulier"), ("societe", "Société")],
                default="particulier",
                max_length=12,
                verbose_name="Particulier ou société",
            ),
        ),
        migrations.AddField(
            model_name="reservation",
            name="nom_societe",
            field=models.CharField(blank=True, max_length=200, verbose_name="Nom de la société"),
        ),
        migrations.AddField(
            model_name="reservation",
            name="numero_tva",
            field=models.CharField(blank=True, help_text="Si la société est assujettie à la TVA. Ex : BE 0123.456.789", max_length=20, verbose_name="N° de TVA"),
        ),
    ]
