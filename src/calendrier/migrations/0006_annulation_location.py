from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("calendrier", "0005_contratlocation_suivi_paiements"),
    ]

    operations = [
        migrations.AlterField(
            model_name="reservation",
            name="statut",
            field=models.CharField(
                choices=[
                    ("attente", "En attente de traitement"),
                    ("validee", "Validée"),
                    ("refusee", "Refusée"),
                    ("annulee", "Annulée"),
                ],
                default="attente",
                max_length=10,
                verbose_name="Statut",
            ),
        ),
        migrations.AddField(
            model_name="contratlocation",
            name="annule",
            field=models.BooleanField(default=False, verbose_name="Location annulée"),
        ),
        migrations.AddField(
            model_name="contratlocation",
            name="date_annulation",
            field=models.DateField(blank=True, null=True, verbose_name="Date d'annulation"),
        ),
        migrations.AddField(
            model_name="contratlocation",
            name="loyer_rembourse",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=8, null=True, verbose_name="Loyer remboursé (€)"),
        ),
        migrations.AddField(
            model_name="contratlocation",
            name="caution_rendue_annulation",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=8, null=True, verbose_name="Caution remboursée à l'annulation (€)"),
        ),
        migrations.AddField(
            model_name="contratlocation",
            name="extrait_annulation",
            field=models.CharField(blank=True, max_length=30, verbose_name="N° d'extrait (remboursement d'annulation)"),
        ),
    ]
