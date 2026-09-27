from wagtail.admin.panels import FieldPanel
from wagtail.blocks import CharBlock, PageChooserBlock, RichTextBlock, StructBlock, URLBlock
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
        ],
        blank=True,
    )

    content_panels = Page.content_panels + [
        FieldPanel("body"),
    ]

    promote_panels = SeoMixin.seo_panels

    class Meta:
        verbose_name = "Page d'informations"
