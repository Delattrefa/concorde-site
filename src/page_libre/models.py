"""
Modèle de "page libre" : une page de contenu autonome, non rattachée au
menu principal du site (rien n'empêche un administrateur de l'y ajouter
manuellement s'il le souhaite, mais ce n'est pas automatique). Utile pour
une page ponctuelle liée depuis un article, une affiche, un QR code, une
campagne, etc. — n'importe où dans l'arborescence Wagtail.

Trois sections successives :
1. Logo + titres (en-tête de la page).
2. Une ou plusieurs sections en défilement, au choix pour chacune : mise en
   page simple (image + texte + liens) ou en colonnes (1 à 3, chacune avec
   image + texte, liens communs à la section) — même système que la page
   d'accueil (voir home.models.SectionDefilementAbstraite).
3. Une galerie de miniatures sur 4 colonnes, chaque miniature ouvrant
   l'image en grand format dans une boîte de type "album photo" (lightbox),
   comme pour l'application media_gallery.
"""
from django.db import models

from modelcluster.fields import ParentalKey

from wagtail.admin.panels import FieldPanel, InlinePanel, MultiFieldPanel
from wagtail.models import Orderable, Page
from wagtailseo.models import SeoMixin

from home.models import SectionDefilementAbstraite


class PageLibre(SeoMixin, Page):
    """Page de contenu autonome, créable n'importe où dans l'arborescence
    du site, sans lien automatique avec le menu principal."""

    # --- Section 1 : logo + titres -----------------------------------------
    logo = models.ForeignKey(
        "wagtailimages.Image",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        verbose_name="Logo",
    )
    titre_affiche = models.CharField(
        "Titre affiché",
        max_length=255,
        blank=True,
        help_text="Facultatif : si laissé vide, le titre de la page (ci-dessus) est utilisé.",
    )
    sous_titre = models.CharField("Sous-titre", max_length=255, blank=True)

    # --- Section 3 : galerie de miniatures (titre facultatif) ---------------
    titre_galerie = models.CharField(
        "Titre de la galerie de miniatures",
        max_length=255,
        blank=True,
        help_text="Facultatif : laissez vide pour n'afficher aucune galerie.",
    )

    content_panels = Page.content_panels + [
        MultiFieldPanel(
            [
                FieldPanel("logo"),
                FieldPanel("titre_affiche"),
                FieldPanel("sous_titre"),
            ],
            heading="Logo et titres",
        ),
        InlinePanel(
            "sections",
            label="Section (mise en page simple ou en colonnes)",
        ),
        MultiFieldPanel(
            [
                FieldPanel("titre_galerie"),
                InlinePanel("galerie_images", label="Miniatures de la galerie"),
            ],
            heading="Galerie de miniatures (4 colonnes, ouverture en grand format)",
        ),
    ]

    promote_panels = SeoMixin.seo_panels

    # Nom de fichier de template explicite : évite toute ambiguïté avec la
    # résolution automatique de Wagtail (qui utiliserait "pagelibre.html",
    # sans séparateur, à partir du nom de classe).
    template = "page_libre/page_libre.html"

    class Meta:
        verbose_name = "Page libre"
        verbose_name_plural = "Pages libres"

    def get_context(self, request, *args, **kwargs):
        context = super().get_context(request, *args, **kwargs)
        # Évite d'exécuter deux fois la requête des miniatures (une pour le
        # test {% if %}, une pour la boucle {% for %}) dans le template.
        context["galerie_images"] = list(self.galerie_images.all())
        return context


class PageLibreSection(SectionDefilementAbstraite):
    """Section en défilement d'une page libre (voir SectionDefilementAbstraite
    pour le détail des champs communs, partagés avec HomePageSection)."""

    page = ParentalKey(
        PageLibre, on_delete=models.CASCADE, related_name="sections"
    )


class PageLibreImage(Orderable):
    """Une miniature de la galerie photo d'une page libre."""

    page = ParentalKey(
        PageLibre, on_delete=models.CASCADE, related_name="galerie_images"
    )
    image = models.ForeignKey(
        "wagtailimages.Image",
        on_delete=models.CASCADE,
        related_name="+",
    )
    legende = models.CharField("Légende (facultative)", max_length=255, blank=True)

    panels = [
        FieldPanel("image"),
        FieldPanel("legende"),
    ]
