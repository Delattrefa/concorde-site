from wagtail.blocks import CharBlock, ChoiceBlock, StructBlock, TextBlock
from wagtail.images.blocks import ImageChooserBlock


class QuoteBlock(StructBlock):
    text = TextBlock(required=True)
    attribution = CharBlock(required=False, help_text="Ex : nom de l'auteur, source…")

    class Meta:
        icon = "openquote"
        label = "Citation"
        template = "news/blocks/quote_block.html"


POSITIONS_IMAGE = [
    ("pleine", "Pleine largeur"),
    ("gauche", "À gauche (le texte l'entoure)"),
    ("droite", "À droite (le texte l'entoure)"),
]


class ImagePositionneeBlock(StructBlock):
    """Photo placée dans le texte de l'article : en pleine largeur, ou à
    gauche / à droite avec le texte qui l'entoure (sur téléphone, toujours
    en pleine largeur)."""

    image = ImageChooserBlock()
    position = ChoiceBlock(choices=POSITIONS_IMAGE, default="pleine")
    legende = CharBlock(label="Légende", required=False)

    class Meta:
        icon = "image"
        label = "Image positionnée"
        template = "news/blocks/image_positionnee.html"
