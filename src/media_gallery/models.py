from django.db import models

from modelcluster.fields import ParentalKey

from wagtail.admin.panels import FieldPanel, InlinePanel
from wagtail.fields import RichTextField
from wagtail.models import Orderable, Page
from wagtailseo.models import SeoMixin


class MediaPage(SeoMixin, Page):
    """Page 'Médias' : liste tous les albums photos (pages enfants GalleryAlbum)."""

    max_count = 1
    intro = RichTextField(blank=True)

    subpage_types = ["media_gallery.GalleryAlbum"]

    content_panels = Page.content_panels + [
        FieldPanel("intro"),
    ]

    promote_panels = SeoMixin.seo_panels

    class Meta:
        verbose_name = "Page médias"

    def get_context(self, request, *args, **kwargs):
        context = super().get_context(request, *args, **kwargs)
        context["albums"] = (
            GalleryAlbum.objects.child_of(self).live().order_by("-date")
        )
        return context


class GalleryAlbum(SeoMixin, Page):
    """Un album photo (ex : une représentation, un événement)."""

    parent_page_types = ["media_gallery.MediaPage"]
    subpage_types = []

    date = models.DateField(blank=True, null=True)
    description = RichTextField(blank=True)
    cover_image = models.ForeignKey(
        "wagtailimages.Image",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        help_text="Photo de couverture affichée dans la liste des albums.",
    )

    content_panels = Page.content_panels + [
        FieldPanel("date"),
        FieldPanel("description"),
        FieldPanel("cover_image"),
        InlinePanel("gallery_images", label="Photos de l'album"),
    ]

    promote_panels = SeoMixin.seo_panels

    class Meta:
        verbose_name = "Album photo"
        verbose_name_plural = "Albums photos"


class GalleryImage(Orderable):
    page = ParentalKey(
        GalleryAlbum, on_delete=models.CASCADE, related_name="gallery_images"
    )
    image = models.ForeignKey(
        "wagtailimages.Image",
        on_delete=models.CASCADE,
        related_name="+",
    )
    caption = models.CharField(max_length=255, blank=True)

    panels = [
        FieldPanel("image"),
        FieldPanel("caption"),
    ]
