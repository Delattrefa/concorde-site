"""
Consentement aux cookies (RGPD / directive ePrivacy).

Le site lui-même n'utilise que des cookies strictement nécessaires (session
de connexion, protection CSRF, mémorisation du choix de l'internaute), qui
ne demandent pas de consentement. En revanche, les contenus intégrés de
sites tiers (cartes Google Maps, vidéos YouTube, Vimeo, Facebook...) peuvent
déposer leurs propres cookies : ils sont bloqués tant que l'internaute ne
les a pas acceptés (voir middleware.py).

Les textes du bandeau se modifient dans l'admin Wagtail :
Paramètres > Consentement aux cookies.
"""
from django.db import models

from wagtail.admin.panels import FieldPanel, MultiFieldPanel
from wagtail.contrib.settings.models import BaseSiteSetting, register_setting
from wagtail.fields import RichTextField

NOM_COOKIE = "concorde_cookies"
VERSION_COOKIE = "v1"


@register_setting(icon="lock")
class ConsentementCookies(BaseSiteSetting):
    actif = models.BooleanField(
        "Activer le bandeau de consentement",
        default=True,
        help_text=(
            "Désactivé : aucun bandeau n'est affiché et les contenus externes "
            "(cartes, vidéos) se chargent directement. À ne désactiver que si "
            "le site n'intègre aucun contenu de site tiers."
        ),
    )
    titre = models.CharField("Titre du bandeau", max_length=120, default="Votre vie privée")
    texte = RichTextField(
        "Texte du bandeau",
        features=["bold", "italic", "link"],
        default=(
            "<p>Ce site utilise uniquement les cookies nécessaires à son "
            "fonctionnement. Certaines pages intègrent toutefois des contenus "
            "de sites tiers (cartes Google Maps, vidéos) qui peuvent déposer "
            "leurs propres cookies. Vous pouvez les accepter ou les refuser, "
            "et modifier votre choix à tout moment.</p>"
        ),
    )
    page_politique = models.ForeignKey(
        "wagtailcore.Page",
        verbose_name="Page « Politique de confidentialité »",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        help_text="Lien affiché dans le bandeau (recommandé).",
    )
    duree_jours = models.PositiveSmallIntegerField(
        "Durée de conservation du choix (jours)",
        default=182,
        help_text=(
            "Au-delà, le bandeau est proposé à nouveau. 6 mois (182 jours) "
            "correspond aux recommandations des autorités de protection des données."
        ),
    )

    panels = [
        FieldPanel("actif"),
        MultiFieldPanel(
            [FieldPanel("titre"), FieldPanel("texte"), FieldPanel("page_politique")],
            heading="Contenu du bandeau",
        ),
        FieldPanel("duree_jours"),
    ]

    class Meta:
        verbose_name = "Consentement aux cookies"


def contenus_externes_acceptes(request):
    """Vrai si l'internaute a accepté les contenus externes (cookie de choix)."""
    valeur = request.COOKIES.get(NOM_COOKIE, "")
    return valeur == f"{VERSION_COOKIE}_externes_1"
