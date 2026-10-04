import django.db.models.deletion
import wagtail.fields
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("wagtailcore", "0094_alter_page_locale"),
    ]

    operations = [
        migrations.CreateModel(
            name="ConsentementCookies",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("actif", models.BooleanField(default=True, help_text="Désactivé : aucun bandeau n'est affiché et les contenus externes (cartes, vidéos) se chargent directement. À ne désactiver que si le site n'intègre aucun contenu de site tiers.", verbose_name="Activer le bandeau de consentement")),
                ("titre", models.CharField(default="Votre vie privée", max_length=120, verbose_name="Titre du bandeau")),
                ("texte", wagtail.fields.RichTextField(default="<p>Ce site utilise uniquement les cookies nécessaires à son fonctionnement. Certaines pages intègrent toutefois des contenus de sites tiers (cartes Google Maps, vidéos) qui peuvent déposer leurs propres cookies. Vous pouvez les accepter ou les refuser, et modifier votre choix à tout moment.</p>", verbose_name="Texte du bandeau")),
                ("duree_jours", models.PositiveSmallIntegerField(default=182, help_text="Au-delà, le bandeau est proposé à nouveau. 6 mois (182 jours) correspond aux recommandations des autorités de protection des données.", verbose_name="Durée de conservation du choix (jours)")),
                ("page_politique", models.ForeignKey(blank=True, help_text="Lien affiché dans le bandeau (recommandé).", null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+", to="wagtailcore.page", verbose_name="Page « Politique de confidentialité »")),
                ("site", models.OneToOneField(editable=False, on_delete=django.db.models.deletion.CASCADE, to="wagtailcore.site")),
            ],
            options={
                "verbose_name": "Consentement aux cookies",
            },
        ),
    ]
