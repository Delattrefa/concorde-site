import html
import re

from django.core.exceptions import ValidationError
from django.db import models
from django.utils.text import slugify
from modelcluster.fields import ParentalKey
from wagtail.admin.panels import FieldPanel, InlinePanel
from wagtail.blocks import (
    CharBlock,
    ChoiceBlock,
    IntegerBlock,
    ListBlock,
    PageChooserBlock,
    RichTextBlock,
    StreamBlock,
    StructBlock,
    StructBlockValidationError,
    StructValue,
    TextBlock,
    URLBlock,
)
from wagtail.fields import StreamField
from wagtail.images.blocks import ImageChooserBlock
from wagtail.models import Orderable, Page
from wagtail.search import index
from wagtailseo.models import SeoMixin

from home.models import LienBlock, SectionDefilementAbstraite

MAX_ONGLETS = 8


class CalloutBlock(StructBlock):
    """Encart mis en avant (ex : horaires, tarifs, condition d'accès)."""

    title = CharBlock(required=False)
    text = RichTextBlock(required=False)

    class Meta:
        icon = "help"
        label = "Encart"
        template = "info/blocks/callout_block.html"


class LinkBlock(StructBlock):
    """Un lien utile : soit vers une page du site (n'importe laquelle,
    choisie via le sélecteur de page), soit vers une adresse externe. Si
    une page est choisie, elle est prioritaire sur l'URL externe."""

    title = CharBlock()
    page = PageChooserBlock(
        required=False,
        label="Page du site",
        help_text="Choisissez une page du site (prioritaire sur l'URL ci-dessous).",
    )
    url = URLBlock(
        required=False,
        label="Ou URL externe",
        help_text="Utilisée seulement si aucune page n'est choisie ci-dessus.",
    )

    class Meta:
        icon = "link"
        label = "Lien utile"
        template = "info/blocks/link_block.html"


_RE_SRC = re.compile(r"""src\s*=\s*["']([^"']+)["']""", re.IGNORECASE)
_PREFIXES_GOOGLE_MAPS = (
    "https://www.google.com/maps/embed",
    "https://maps.google.com/maps",
    "https://www.google.com/maps?",
)


def extraire_url_google_maps(code):
    """Renvoie l'adresse d'intégration Google Maps contenue dans le code
    collé (balise <iframe> complète, ou simple adresse), ou None si ce
    n'est pas une carte Google Maps intégrable."""
    code = html.unescape((code or "").strip())
    correspondance = _RE_SRC.search(code)
    url = correspondance.group(1).strip() if correspondance else code
    if url.startswith("http://"):
        url = "https://" + url[len("http://"):]
    if not url.startswith(_PREFIXES_GOOGLE_MAPS):
        return None
    if url.startswith("https://www.google.com/maps/embed"):
        return url
    # Anciennes adresses maps.google.com : intégrables avec output=embed.
    return url if "output=embed" in url else None


class CarteBlock(StructBlock):
    """Carte Google Maps intégrée. On colle le code fourni par Google Maps
    (Partager > Intégrer une carte > COPIER LE CODE HTML) : seule l'adresse
    de la carte en est extraite, le reste du code est ignoré."""

    title = CharBlock(required=False, label="Titre (facultatif)")
    code = TextBlock(
        label="Code d'intégration Google Maps",
        help_text=(
            "Dans Google Maps : Partager > Intégrer une carte > COPIER LE CODE HTML, "
            "puis collez ici le code complet (<iframe ...></iframe>). "
            "Un lien de partage (maps.app.goo.gl) ne fonctionne pas."
        ),
        rows=3,
    )
    height = IntegerBlock(
        label="Hauteur (pixels)", default=400, min_value=200, max_value=900,
    )

    def clean(self, value):
        value = super().clean(value)
        url = extraire_url_google_maps(value.get("code"))
        if not url:
            raise StructBlockValidationError(block_errors={
                "code": ValidationError(
                    "Code non reconnu. Collez le code HTML fourni par Google Maps dans "
                    "Partager > Intégrer une carte (il commence par <iframe src=\"https://www.google.com/maps/embed...)."
                ),
            })
        # On ne conserve que l'adresse de la carte, jamais le HTML collé.
        value["code"] = url
        return value

    def get_context(self, value, parent_context=None):
        contexte = super().get_context(value, parent_context=parent_context)
        contexte["url_carte"] = extraire_url_google_maps(value.get("code"))
        return contexte

    class Meta:
        icon = "site"
        label = "Carte Google Maps"
        template = "info/blocks/carte_block.html"


class EnteteOngletBlock(StructBlock):
    """Logo et titres en tête d'un onglet (comme l'en-tête d'une page libre)."""

    logo = ImageChooserBlock(required=False, label="Logo")
    titre = CharBlock(required=False, label="Titre")
    sous_titre = CharBlock(required=False, label="Sous-titre")

    class Meta:
        icon = "title"
        label = "Logo et titres"


class SectionNormaleValue(StructValue):
    type_section = SectionDefilementAbstraite.TYPE_NORMAL


class SectionNormaleBlock(StructBlock):
    """Image + texte : même rendu qu'une section d'une page libre
    (includes/section_defilement.html, d'où les mêmes noms de champs)."""

    title = CharBlock(required=False, label="Titre")
    text = RichTextBlock(required=False, label="Texte")
    image = ImageChooserBlock(required=False, label="Image")
    image_position = ChoiceBlock(
        choices=SectionDefilementAbstraite.IMAGE_POSITION_CHOICES, default="left", label="Position de l'image",
    )
    taille_image = ChoiceBlock(
        choices=SectionDefilementAbstraite.TAILLE_IMAGE_CHOICES,
        default=SectionDefilementAbstraite.TAILLE_MOYENNE, label="Taille de l'image",
    )
    liens = StreamBlock([("lien", LienBlock())], required=False, label="Liens")

    class Meta:
        icon = "image"
        label = "Section image + texte"
        value_class = SectionNormaleValue


class SectionColonnesValue(StructValue):
    type_section = SectionDefilementAbstraite.TYPE_COLONNES

    @property
    def nombre_colonnes(self):
        return len(self["colonnes"])


class SectionColonnesBlock(StructBlock):
    """1 à 3 colonnes : même rendu qu'une section en colonnes d'une page libre."""

    titre_colonnes = CharBlock(required=False, label="Titre de la section")
    image_fond_colonnes = ImageChooserBlock(required=False, label="Image de fond (facultatif)")
    taille_image = ChoiceBlock(
        choices=SectionDefilementAbstraite.TAILLE_IMAGE_CHOICES,
        default=SectionDefilementAbstraite.TAILLE_MOYENNE, label="Taille des images",
    )
    colonnes = ListBlock(
        StructBlock([
            ("titre", CharBlock(required=False, label="Titre")),
            ("texte", RichTextBlock(required=False, label="Texte")),
            ("image", ImageChooserBlock(required=False, label="Image")),
        ], label="Colonne"),
        min_num=1, max_num=3, label="Colonnes",
    )
    liens = StreamBlock([("lien", LienBlock())], required=False, label="Liens")

    class Meta:
        icon = "table"
        label = "Section en colonnes"
        value_class = SectionColonnesValue


class GalerieBlock(StructBlock):
    """Miniatures sur 4 colonnes, ouvertes en grand dans la visionneuse."""

    titre = CharBlock(required=False, label="Titre de la galerie")
    images = ListBlock(
        StructBlock([
            ("image", ImageChooserBlock(label="Image")),
            ("legende", CharBlock(required=False, label="Légende (facultative)")),
        ], label="Miniature"),
        label="Miniatures",
    )

    class Meta:
        icon = "image"
        label = "Galerie de miniatures"


BLOCS_INFO = [
    ("heading", CharBlock(icon="title", form_classname="title", label="Titre")),
    ("paragraph", RichTextBlock(icon="pilcrow", label="Texte")),
    ("image", ImageChooserBlock(icon="image", label="Image")),
    ("callout", CalloutBlock()),
    ("useful_link", LinkBlock()),
    ("map", CarteBlock()),
]


class InfoPage(SeoMixin, Page):
    """Page 'Infos pratiques' : contenu libre construit par blocs (texte,
    images, encarts, liens utiles, FAQ…), suivi de 8 onglets au plus."""

    body = StreamField(BLOCS_INFO, blank=True, verbose_name="Introduction (au-dessus des onglets)")

    search_fields = Page.search_fields + [
        index.SearchField("body"),
        index.RelatedFields("onglets", [index.SearchField("titre"), index.SearchField("contenu")]),
    ]

    content_panels = Page.content_panels + [
        FieldPanel("body"),
        InlinePanel(
            "onglets", label="Onglet", max_num=MAX_ONGLETS,
            heading=f"Onglets ({MAX_ONGLETS} au maximum)",
            help_text="Chaque onglet présente une information. Sans onglet, la page affiche seulement l'introduction.",
        ),
    ]

    promote_panels = SeoMixin.seo_panels

    class Meta:
        verbose_name = "Page d'informations"

    def get_context(self, request, *args, **kwargs):
        context = super().get_context(request, *args, **kwargs)
        onglets = list(self.onglets.all())
        for onglet, ancre in zip(onglets, ancres_onglets(o.titre for o in onglets)):
            onglet.ancre = ancre
        context["onglets"] = onglets
        context["a_galerie"] = any(b.block_type == "galerie" for o in onglets for b in o.contenu)
        return context


def ancres_onglets(titres):
    """Ancres d'URL des onglets (/info/#onglet-historique), toutes distinctes."""
    ancres = []
    for titre in titres:
        base = f"onglet-{slugify(titre) or len(ancres) + 1}"
        ancre, suite = base, 2
        while ancre in ancres:
            ancre, suite = f"{base}-{suite}", suite + 1
        ancres.append(ancre)
    return ancres


class InfoOnglet(Orderable):
    """Un onglet de la page d'informations : une information, avec les
    mêmes possibilités de contenu que la page et qu'une page libre."""

    page = ParentalKey(InfoPage, on_delete=models.CASCADE, related_name="onglets")
    titre = models.CharField("Titre de l'onglet", max_length=60)
    contenu = StreamField(
        BLOCS_INFO + [
            ("entete", EnteteOngletBlock()),
            ("section", SectionNormaleBlock()),
            ("colonnes", SectionColonnesBlock()),
            ("galerie", GalerieBlock()),
        ],
        blank=True, verbose_name="Contenu",
    )

    panels = [FieldPanel("titre"), FieldPanel("contenu")]

    class Meta(Orderable.Meta):
        verbose_name = "Onglet"
