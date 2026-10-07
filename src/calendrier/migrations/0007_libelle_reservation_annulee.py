from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("calendrier", "0006_annulation_location"),
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
                    ("annulee", "Réservation annulée"),
                ],
                default="attente",
                max_length=10,
                verbose_name="Statut",
            ),
        ),
    ]
