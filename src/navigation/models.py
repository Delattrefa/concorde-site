"""
Modèles de navigation :
- MainMenuItem : liens affichés dans le menu principal du site
- FooterLink   : liens affichés dans le pied de page
- SocialSettings : coordonnées & réseaux sociaux (paramètre de site global)

Tout est éditable depuis l'admin Wagtail, sans toucher au code.
"""
from django.db import models

from modelcluster.fields import ParentalKey
from modelcluster.models import ClusterableModel

from wagtail.admin.panels import FieldPanel, InlinePanel
from wagtail.contrib.settings.models import BaseSiteSetting, register_setting
from wagtail.models import Orderable
from wagtail.snippets.models import register_snippet


@register_snippet
class MainMenu(ClusterableModel):
    """Un seul menu principal, avec ses éléments ordonnés (InlinePanel)."""

    name = models.CharField(max_length=100, default="Menu principal")

    panels = [
        FieldPanel("name"),
        InlinePanel("items", label="Éléments du menu"),
    ]

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Menu principal"


class MainMenuItem(Orderable):
    menu = ParentalKey(
        MainMenu, on_delete=models.CASCADE, related_name="items"
    )
    link_title = models.CharField(max_length=50)
    link_page = models.ForeignKey(
        "wagtailcore.Page",
        null=True,
        blank=True,
        related_name="+",
        on_delete=models.CASCADE,
        help_text="Choisir une page du site (prioritaire sur l'URL ci-dessous).",
    )
    link_url = models.CharField(
        max_length=500,
        blank=True,
        help_text="Ou une URL externe / ancre, si aucune page n'est choisie.",
    )

    panels = [
        FieldPanel("link_title"),
        FieldPanel("link_page"),
        FieldPanel("link_url"),
    ]

    @property
    def url(self):
        if self.link_page:
            return self.link_page.url
        return self.link_url

    def __str__(self):
        return self.link_title


@register_snippet
class FooterMenu(ClusterableModel):
    name = models.CharField(max_length=100, default="Pied de page")

    panels = [
        FieldPanel("name"),
        InlinePanel("links", label="Liens"),
    ]

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Liens du pied de page"


class FooterLink(Orderable):
    menu = ParentalKey(
        FooterMenu, on_delete=models.CASCADE, related_name="links"
    )
    link_title = models.CharField(max_length=50)
    link_page = models.ForeignKey(
        "wagtailcore.Page",
        null=True,
        blank=True,
        related_name="+",
        on_delete=models.CASCADE,
    )
    link_url = models.CharField(max_length=500, blank=True)
    ouvrir_nouvel_onglet = models.BooleanField(
        "Ouvrir dans un nouvel onglet", default=False
    )

    panels = [
        FieldPanel("link_title"),
        FieldPanel("link_page"),
        FieldPanel("link_url"),
        FieldPanel("ouvrir_nouvel_onglet"),
    ]

    @property
    def url(self):
        if self.link_page:
            return self.link_page.url
        return self.link_url

    def __str__(self):
        return self.link_title


@register_setting
class SocialSettings(ClusterableModel, BaseSiteSetting):
    """Coordonnées et réseaux sociaux, affichés dans le pied de page.

    Les réseaux sociaux sont une liste de liens (InlinePanel) plutôt que
    des champs fixes un-par-réseau : on peut ainsi ajouter plusieurs liens
    pour le même réseau (ex : deux pages Facebook différentes), ou aucun."""

    address = models.CharField("Adresse", max_length=255, blank=True)
    phone = models.CharField("Téléphone", max_length=50, blank=True)
    email = models.EmailField("E-mail", blank=True)

    panels = [
        FieldPanel("address"),
        FieldPanel("phone"),
        FieldPanel("email"),
        InlinePanel("liens_reseaux_sociaux", label="Liens vers les réseaux sociaux"),
    ]

    class Meta:
        verbose_name = "Coordonnées & réseaux sociaux"


class ReseauSocialLien(Orderable):
    """Un lien vers un réseau social. Plusieurs liens peuvent être ajoutés
    pour le même réseau (ex : une page Facebook et un groupe Facebook)."""

    RESEAU_FACEBOOK = "facebook"
    RESEAU_INSTAGRAM = "instagram"
    RESEAU_YOUTUBE = "youtube"
    RESEAU_AUTRE = "autre"
    RESEAU_CHOICES = [
        (RESEAU_FACEBOOK, "Facebook"),
        (RESEAU_INSTAGRAM, "Instagram"),
        (RESEAU_YOUTUBE, "YouTube"),
        (RESEAU_AUTRE, "Autre"),
    ]

    settings = ParentalKey(
        SocialSettings, on_delete=models.CASCADE, related_name="liens_reseaux_sociaux"
    )
    reseau = models.CharField(
        "Réseau social", max_length=20, choices=RESEAU_CHOICES, default=RESEAU_FACEBOOK
    )
    libelle = models.CharField(
        "Libellé (facultatif)",
        max_length=100,
        blank=True,
        help_text="Ex : 'Page principale', 'Groupe des bénévoles'. Utile surtout si "
        "plusieurs liens sont ajoutés pour le même réseau.",
    )
    url = models.URLField("Adresse du lien")

    panels = [
        FieldPanel("reseau"),
        FieldPanel("libelle"),
        FieldPanel("url"),
    ]

    class Meta:
        verbose_name = "Lien vers un réseau social"
        verbose_name_plural = "Liens vers les réseaux sociaux"

    def __str__(self):
        return f"{self.get_reseau_display()} — {self.libelle or self.url}"


@register_setting(icon="image")
class IdentiteVisuelle(BaseSiteSetting):
    """Icône du site affichée dans l'onglet du navigateur (favicon), dans
    les favoris et sur l'écran d'accueil des smartphones."""

    favicon = models.ForeignKey(
        "wagtailimages.Image",
        verbose_name="Icône de l'onglet (logo)",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        help_text=(
            "Image carrée, idéalement au format PNG de 512 × 512 pixels, "
            "sur fond uni ou transparent. Une image non carrée est recadrée "
            "autour de son point d'intérêt. Sans image, une icône « C » aux "
            "couleurs du site est utilisée."
        ),
    )

    panels = [
        FieldPanel("favicon"),
    ]

    class Meta:
        verbose_name = "Identité visuelle (icône du site)"
