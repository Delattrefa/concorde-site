import html
import re

from django.core.exceptions import ValidationError
from wagtail.admin.panels import FieldPanel
from wagtail.blocks import (
    CharBlock,
    IntegerBlock,
    PageChooserBlock,
    RichTextBlock,
    StructBlock,
    StructBlockValidationError,
    TextBlock,
    URLBlock,
)
from wagtail.fields import StreamField
from wagtail.images.blocks import ImageChooserBlock
from wagtail.models import Page
from wagtailseo.models import SeoMixin


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


class InfoPage(SeoMixin, Page):
    """Page 'Infos pratiques' : contenu libre construit par blocs
    (texte, images, encarts, liens utiles, FAQ…)."""

    body = StreamField(
        [
            ("heading", CharBlock(icon="title", form_classname="title")),
            ("paragraph", RichTextBlock(icon="pilcrow")),
            ("image", ImageChooserBlock(icon="image")),
            ("callout", CalloutBlock()),
            ("useful_link", LinkBlock()),
            ("map", CarteBlock()),
        ],
        blank=True,
    )

    content_panels = Page.content_panels + [
        FieldPanel("body"),
    ]

    promote_panels = SeoMixin.seo_panels

    class Meta:
        verbose_name = "Page d'informations"
