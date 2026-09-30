import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("calendrier", "0002_contratlocation"),
    ]

    operations = [
        migrations.CreateModel(
            name="ArticleContrat",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("ordre", models.PositiveIntegerField(default=0, help_text="Les articles sont imprimés du plus petit au plus grand numéro d'ordre.", verbose_name="Ordre d'affichage")),
                ("titre", models.CharField(help_text="Ex : ARTICLE 5 bis", max_length=100, verbose_name="Titre")),
                ("texte", models.TextField(verbose_name="Texte de l'article")),
                ("actif", models.BooleanField(default=True, help_text="Décocher pour retirer l'article des prochains contrats sans le supprimer.", verbose_name="Inclure dans le contrat")),
                ("date_modification", models.DateTimeField(auto_now=True, verbose_name="Dernière modification")),
            ],
            options={
                "verbose_name": "Article du contrat-type",
                "verbose_name_plural": "Articles du contrat-type",
                "ordering": ["ordre", "pk"],
            },
        ),
        migrations.CreateModel(
            name="AnnexeContrat",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("ordre", models.PositiveIntegerField(default=0, help_text="Les annexes sont ajoutées au contrat dans cet ordre.", verbose_name="Ordre d'affichage")),
                ("titre", models.CharField(help_text="Ex : Annexe III — Conditions particulières", max_length=150, verbose_name="Titre")),
                ("fichier", models.FileField(upload_to="annexes_contrat/", validators=[django.core.validators.FileExtensionValidator(["pdf"])], verbose_name="Fichier PDF")),
                ("actif", models.BooleanField(default=True, help_text="Décocher pour ne plus joindre cette annexe aux prochains contrats.", verbose_name="Joindre au contrat")),
                ("date_modification", models.DateTimeField(auto_now=True, verbose_name="Dernière modification")),
            ],
            options={
                "verbose_name": "Annexe du contrat-type",
                "verbose_name_plural": "Annexes du contrat-type",
                "ordering": ["ordre", "pk"],
            },
        ),
    ]
