from django.core.exceptions import ValidationError
from django.db import models

from modelcluster.fields import ParentalKey

from wagtail.admin.panels import FieldPanel, InlinePanel, MultiFieldPanel
from wagtail.fields import RichTextField
from wagtail.models import Orderable, Page
from wagtail.search import index
from wagtailseo.models import SeoMixin

from .videos import PLATEFORMES, analyser_video


class MediaPage(SeoMixin, Page):
    """Page « Médias » : liste des albums (pages enfants GalleryAlbum),
    filtrable par année."""

    max_count = 1
    intro = RichTextField(blank=True)

    subpage_types = ["media_gallery.GalleryAlbum"]

    search_fields = Page.search_fields + [
        index.SearchField("intro"),
    ]

    content_panels = Page.content_panels + [
        FieldPanel("intro"),
    ]

    promote_panels = SeoMixin.seo_panels

    class Meta:
        verbose_name = "Page médias"

    def get_context(self, request, *args, **kwargs):
        context = super().get_context(request, *args, **kwargs)
        albums = (
            GalleryAlbum.objects.child_of(self).live().public()
            .order_by("-date", "-first_published_at")
        )
        annees = sorted({a.date.year for a in albums if a.date}, reverse=True)

        annee = request.GET.get("annee", "")
        if annee.isdigit() and int(annee) in annees:
            albums = albums.filter(date__year=int(annee))
            context["annee"] = int(annee)

        context["albums"] = albums.prefetch_related("gallery_images", "videos")
        context["annees"] = annees
        return context


class GalleryAlbum(SeoMixin, Page):
    """Un album (ex : une représentation, un événement) : photos et vidéos."""

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
        help_text="Photo de couverture affichée dans la liste des albums (sinon la première photo).",
    )

    search_fields = Page.search_fields + [
        index.SearchField("description"),
        index.RelatedFields("gallery_images", [index.SearchField("caption")]),
        index.RelatedFields("videos", [index.SearchField("titre")]),
    ]

    content_panels = Page.content_panels + [
        FieldPanel("date"),
        FieldPanel("description"),
        FieldPanel("cover_image"),
        InlinePanel("gallery_images", label="Photos de l'album"),
        InlinePanel(
            "videos",
            label="Vidéos de l'album",
            help_text="Liens vers des vidéos " + ", ".join(PLATEFORMES) + ".",
        ),
    ]

    promote_panels = SeoMixin.seo_panels

    class Meta:
        verbose_name = "Album photo"
        verbose_name_plural = "Albums photos"

    @property
    def couverture(self):
        """Image de couverture, ou à défaut la première photo, ou la
        vignette de la première vidéo."""
        if self.cover_image_id:
            return self.cover_image
        premiere = self.gallery_images.first()
        if premiere:
            return premiere.image
        video = self.videos.exclude(vignette=None).first()
        return video.vignette if video else None

    def get_context(self, request, *args, **kwargs):
        context = super().get_context(request, *args, **kwargs)

        # Navigation entre albums (du plus récent au plus ancien)
        albums = list(
            GalleryAlbum.objects.sibling_of(self, inclusive=True).live().public()
            .order_by("-date", "-first_published_at")
        )
        position = next((i for i, a in enumerate(albums) if a.pk == self.pk), None)
        if position is not None:
            context["album_precedent"] = albums[position - 1] if position > 0 else None
            context["album_suivant"] = albums[position + 1] if position + 1 < len(albums) else None
            context["position_album"] = position + 1
        context["tous_les_albums"] = albums

        context["photos"] = self.gallery_images.select_related("image").all()
        context["videos"] = [v for v in self.videos.select_related("vignette").all() if v.infos]
        return context


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


class GalleryVideo(Orderable):
    """Vidéo hébergée sur une autre plateforme (YouTube, Facebook...),
    intégrée dans l'album. Elle n'est chargée qu'avec l'accord du visiteur
    pour les contenus externes (bandeau de cookies)."""

    page = ParentalKey(GalleryAlbum, on_delete=models.CASCADE, related_name="videos")
    url = models.URLField(
        "Lien de la vidéo",
        max_length=500,
        help_text=(
            "Copiez l'adresse de la vidéo (barre d'adresse ou bouton « Partager ») : "
            + ", ".join(PLATEFORMES) + "."
        ),
    )
    titre = models.CharField("Titre", max_length=255, blank=True)
    vignette = models.ForeignKey(
        "wagtailimages.Image",
        verbose_name="Vignette (facultatif)",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        help_text="Image d'aperçu affichée dans l'album. Sans image, une vignette aux couleurs du site est utilisée.",
    )

    panels = [
        FieldPanel("url"),
        FieldPanel("titre"),
        FieldPanel("vignette"),
    ]

    class Meta(Orderable.Meta):
        verbose_name = "Vidéo"
        verbose_name_plural = "Vidéos"

    def __str__(self):
        return self.titre or self.url

    @property
    def infos(self):
        """Plateforme, adresse du lecteur intégrable, lien d'origine, format."""
        return analyser_video(self.url)

    def clean(self):
        super().clean()
        if self.url and not analyser_video(self.url):
            raise ValidationError({
                "url": "Lien non reconnu. Plateformes acceptées : " + ", ".join(PLATEFORMES)
                + ". Utilisez l'adresse de la vidéo elle-même (pas celle d'une chaîne ou d'une page)."
            })
