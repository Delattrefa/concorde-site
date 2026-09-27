from wagtail.blocks import CharBlock, StructBlock, TextBlock


class QuoteBlock(StructBlock):
    text = TextBlock(required=True)
    attribution = CharBlock(required=False, help_text="Ex : nom de l'auteur, source…")

    class Meta:
        icon = "openquote"
        label = "Citation"
        template = "news/blocks/quote_block.html"
