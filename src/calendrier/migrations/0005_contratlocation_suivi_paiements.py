from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("calendrier", "0004_contrat_type_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="contratlocation",
            name="location_payee",
            field=models.BooleanField(default=False, verbose_name="Location payée"),
        ),
        migrations.AddField(
            model_name="contratlocation",
            name="caution_payee",
            field=models.BooleanField(default=False, verbose_name="Caution payée"),
        ),
        migrations.AddField(
            model_name="contratlocation",
            name="caution_remboursee",
            field=models.BooleanField(default=False, verbose_name="Caution remboursée"),
        ),
        migrations.AddField(
            model_name="contratlocation",
            name="date_paiement",
            field=models.DateField(blank=True, null=True, verbose_name="Date du paiement"),
        ),
        migrations.AddField(
            model_name="contratlocation",
            name="extrait_paiement",
            field=models.CharField(blank=True, max_length=30, verbose_name="N° d'extrait (paiement)"),
        ),
        migrations.AddField(
            model_name="contratlocation",
            name="date_remboursement_caution",
            field=models.DateField(blank=True, null=True, verbose_name="Date du remboursement de la caution"),
        ),
        migrations.AddField(
            model_name="contratlocation",
            name="extrait_remboursement",
            field=models.CharField(blank=True, max_length=30, verbose_name="N° d'extrait (remboursement)"),
        ),
    ]
