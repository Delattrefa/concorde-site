"""
Blocs de contenu d'une newsletter (StreamField).

Le rendu e-mail n'utilise pas les gabarits de ces blocs : il est construit
par newsletter/rendu.py, qui produit un HTML à styles en ligne compatible
avec les messageries (Gmail, Outlook, Apple Mail).
"""
from django.core.exceptions import ValidationError

from wagtail import blocks
from wagtail.images.blocks import ImageChooserBlock

FONCTIONS_TEXTE = ["h3", "bold", "italic", "ol", "ul", "link", "document-link"]


class TexteBlock(blocks.RichTextBlock):
    def __init__(self, **kwargs):
        super().__init__(features=FONCTIONS_TEXTE, **kwargs)

    class Meta:
        icon = "pilcrow"
        label = "Texte"


class ImageNewsletterBlock(blocks.StructBlock):
    image = ImageChooserBlock(label="Image")
    alt = blocks.CharBlock(
        label="Texte alternatif",
        required=False,
        help_text="Décrit l'image pour les personnes qui ne la voient pas (images bloquées, "
        "lecteur d'écran). Vide : la description ou le titre de l'image est utilisé.",
    )
    legende = blocks.CharBlock(label="Légende (facultatif)", required=False)
    largeur = blocks.ChoiceBlock(
        label="Largeur",
        choices=[("pleine", "Toute la largeur"), ("moyenne", "Moyenne, centrée"), ("petite", "Petite, centrée")],
        default="pleine",
    )
    lien = blocks.URLBlock(label="Lien au clic (facultatif)", required=False)

    class Meta:
        icon = "image"
        label = "Image"


class BoutonBlock(blocks.StructBlock):
    texte = blocks.CharBlock(label="Texte du bouton", max_length=60)
    page = blocks.PageChooserBlock(label="Page du site", required=False)
    url = blocks.URLBlock(label="Ou adresse externe", required=False)
    style = blocks.ChoiceBlock(
        label="Couleur",
        choices=[("dore", "Doré (principal)"), ("bordeaux", "Bordeaux")],
        default="dore",
    )

    def clean(self, value):
        value = super().clean(value)
        if not value.get("page") and not value.get("url"):
            raise blocks.StructBlockValidationError(block_errors={
                "url": ValidationError("Choisissez une page du site ou indiquez une adresse."),
            })
        return value

    class Meta:
        icon = "link"
        label = "Bouton (appel à l'action)"


class ActualitesRecentesBlock(blocks.StructBlock):
    titre = blocks.CharBlock(label="Titre", default="Nos dernières actualités", required=False)
    nombre = blocks.IntegerBlock(label="Nombre d'actualités", default=3, min_value=1, max_value=6)

    class Meta:
        icon = "list-ul"
        label = "Actualités récentes (automatique)"
        help_text = "Les dernières actualités publiées sur le site, au moment de l'envoi."


class PageEnAvantBlock(blocks.StructBlock):
    page = blocks.PageChooserBlock(label="Page à mettre en avant")
    titre = blocks.CharBlock(label="Titre (vide : titre de la page)", required=False)
    texte = blocks.TextBlock(label="Texte (vide : résumé de la page)", required=False)
    image = ImageChooserBlock(label="Image (vide : image de la page s'il y en a une)", required=False)
    texte_bouton = blocks.CharBlock(label="Texte du bouton", default="En savoir plus")

    class Meta:
        icon = "doc-full"
        label = "Page ou publication mise en avant"


class EncadreBlock(blocks.StructBlock):
    titre = blocks.CharBlock(label="Titre", required=False)
    texte = TexteBlock(label="Texte")

    class Meta:
        icon = "info-circle"
        label = "Encadré"


class SeparateurBlock(blocks.StaticBlock):
    class Meta:
        icon = "horizontalrule"
        label = "Séparateur"
        admin_text = "Ligne de séparation"


CONTENU_NEWSLETTER = [
    ("titre", blocks.CharBlock(label="Titre", icon="title")),
    ("texte", TexteBlock()),
    ("image", ImageNewsletterBlock()),
    ("bouton", BoutonBlock()),
    ("actualites", ActualitesRecentesBlock()),
    ("page_en_avant", PageEnAvantBlock()),
    ("encadre", EncadreBlock()),
    ("separateur", SeparateurBlock()),
]
