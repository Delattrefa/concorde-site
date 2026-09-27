from django.db import models

from modelcluster.fields import ParentalKey

from wagtail.admin.panels import FieldPanel, InlinePanel, MultiFieldPanel
from wagtail.blocks import CharBlock, StructBlock, URLBlock
from wagtail.fields import RichTextField, StreamField
from wagtail.models import Orderable, Page
from wagtailseo.models import SeoMixin


class LienBlock(StructBlock):
    """Un lien (texte + adresse), utilisé pour la liste de liens d'une
    section en défilement (page d'accueil ou page libre). Une section peut
    en contenir autant que voulu (au moins deux, mais aucune limite haute)."""

    texte = CharBlock(label="Texte du lien", max_length=50)
    url = URLBlock(label="Adresse du lien")

    class Meta:
        icon = "link"
        label = "Lien"


class SectionDefilementAbstraite(Orderable):
    """Classe abstraite : un bloc de contenu affiché en défilement continu
    avec effet de fondu/ouverture (voir static/js/scroll-effects.js).
    Réutilisée à la fois par la page d'accueil (HomePageSection) et par les
    pages libres (page_libre.PageLibreSection).

    Chaque section a un TYPE au choix :
    - 'normal'   : image + texte, image à gauche/droite/pleine largeur ;
    - 'colonnes' : 1 à 3 colonnes, chacune avec son propre titre/texte/image.

    Les deux jeux de champs coexistent sur le même modèle (comme
    'image_position' existait déjà pour le type normal) : seuls les champs
    correspondant au type choisi sont réellement utilisés au rendu. Ce choix
    évite d'imbriquer un InlinePanel dans un InlinePanel, mal supporté par
    Wagtail, tout en gardant un seul et même InlinePanel dans l'admin, avec
    un ordre unique et mélangeable entre sections normales et en colonnes.

    Classe abstraite : chaque sous-classe concrète doit définir son propre
    champ ParentalKey 'page' vers le modèle de page parent."""

    TYPE_NORMAL = "normal"
    TYPE_COLONNES = "colonnes"
    TYPE_CHOICES = [
        (TYPE_NORMAL, "Défilement normal (image + texte)"),
        (TYPE_COLONNES, "Colonnes (1 à 3)"),
    ]

    IMAGE_POSITION_CHOICES = [
        ("left", "Image à gauche"),
        ("right", "Image à droite"),
        ("full", "Image en pleine largeur (fond)"),
    ]

    NOMBRE_COLONNES_CHOICES = [(1, "1 colonne"), (2, "2 colonnes"), (3, "3 colonnes")]

    type_section = models.CharField(
        "Type de section",
        max_length=10,
        choices=TYPE_CHOICES,
        default=TYPE_NORMAL,
        help_text="Détermine quels champs ci-dessous sont utilisés à l'affichage.",
    )

    # --- Champs utilisés si type_section == 'normal' ----------------------
    title = models.CharField("Titre", max_length=255, blank=True)
    text = RichTextField("Texte", blank=True)
    image = models.ForeignKey(
        "wagtailimages.Image",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        verbose_name="Image",
    )
    image_position = models.CharField(
        "Position de l'image", max_length=10, choices=IMAGE_POSITION_CHOICES, default="left"
    )

    # --- Champs utilisés si type_section == 'colonnes' ---------------------
    titre_colonnes = models.CharField(
        "Titre de la section", max_length=255, blank=True,
        help_text="Facultatif : affiché au-dessus des colonnes.",
    )
    nombre_colonnes = models.PositiveSmallIntegerField(
        "Nombre de colonnes", choices=NOMBRE_COLONNES_CHOICES, default=2,
    )

    colonne_1_titre = models.CharField("Titre", max_length=200, blank=True)
    colonne_1_texte = RichTextField("Texte", blank=True)
    colonne_1_image = models.ForeignKey(
        "wagtailimages.Image", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="+", verbose_name="Image",
    )

    colonne_2_titre = models.CharField("Titre", max_length=200, blank=True)
    colonne_2_texte = RichTextField("Texte", blank=True)
    colonne_2_image = models.ForeignKey(
        "wagtailimages.Image", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="+", verbose_name="Image",
    )

    colonne_3_titre = models.CharField("Titre", max_length=200, blank=True)
    colonne_3_texte = RichTextField("Texte", blank=True)
    colonne_3_image = models.ForeignKey(
        "wagtailimages.Image", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="+", verbose_name="Image",
    )

    # --- Champ commun aux deux types : liste de liens (au moins deux) -----
    # Un StreamField accepte nativement un nombre illimité de blocs "lien"
    # (contrairement à un InlinePanel, qui ne peut pas être imbriqué dans
    # l'InlinePanel "sections" déjà utilisé par la page parente).
    liens = StreamField(
        [("lien", LienBlock())],
        blank=True,
        verbose_name="Liens",
        help_text="Ajoutez autant de liens que voulu (au moins deux si besoin), pour les deux types de section.",
    )

    panels = [
        FieldPanel("type_section"),
        MultiFieldPanel(
            [
                FieldPanel("title"),
                FieldPanel("text"),
                FieldPanel("image"),
                FieldPanel("image_position"),
            ],
            heading="Champs utilisés si le type 'Défilement normal' est sélectionné ci-dessus",
        ),
        MultiFieldPanel(
            [
                FieldPanel("titre_colonnes"),
                FieldPanel("nombre_colonnes"),
                MultiFieldPanel(
                    [FieldPanel("colonne_1_titre"), FieldPanel("colonne_1_texte"), FieldPanel("colonne_1_image")],
                    heading="Colonne 1",
                ),
                MultiFieldPanel(
                    [FieldPanel("colonne_2_titre"), FieldPanel("colonne_2_texte"), FieldPanel("colonne_2_image")],
                    heading="Colonne 2 (si 2 ou 3 colonnes sélectionnées)",
                ),
                MultiFieldPanel(
                    [FieldPanel("colonne_3_titre"), FieldPanel("colonne_3_texte"), FieldPanel("colonne_3_image")],
                    heading="Colonne 3 (si 3 colonnes sélectionnées)",
                ),
            ],
            heading="Champs utilisés si le type 'Colonnes' est sélectionné ci-dessus",
        ),
        FieldPanel("liens", heading="Liens (communs aux deux types de section)"),
    ]

    class Meta(Orderable.Meta):
        abstract = True

    def colonnes(self):
        """Renvoie uniquement les colonnes à afficher réellement (type
        'colonnes'), selon la valeur choisie pour 'nombre_colonnes'."""
        toutes_les_colonnes = [
            {"titre": self.colonne_1_titre, "texte": self.colonne_1_texte, "image": self.colonne_1_image},
            {"titre": self.colonne_2_titre, "texte": self.colonne_2_texte, "image": self.colonne_2_image},
            {"titre": self.colonne_3_titre, "texte": self.colonne_3_texte, "image": self.colonne_3_image},
        ]
        return toutes_les_colonnes[: self.nombre_colonnes]


class HomePage(SeoMixin, Page):
    """Page d'accueil : bandeau d'ouverture + suite de sections qui
    apparaissent en fondu au fil du défilement (voir static/js/scroll-effects.js)."""

    max_count = 1  # une seule page d'accueil

    hero_title = models.CharField(
        max_length=255,
        blank=True,
        default="Bienvenue à La Concorde",
        help_text="Grand titre affiché sur le bandeau d'ouverture.",
    )
    hero_subtitle = models.CharField(max_length=255, blank=True)
    hero_image = models.ForeignKey(
        "wagtailimages.Image",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        help_text="Image ou photo de fond du bandeau d'ouverture (effet de fondu à l'arrivée sur le site).",
    )
    hero_cta_text = models.CharField(
        max_length=50, blank=True, default="Découvrir nos activités"
    )
    hero_cta_link = models.URLField(blank=True)

    intro = RichTextField(blank=True, help_text="Court texte de présentation de l'ASBL.")

    # --- Sections dynamiques (affichées juste après l'introduction) -------
    # Chaque section n'apparaît que si l'interrupteur est activé ET qu'il y
    # a effectivement quelque chose à afficher (voir get_context ci-dessous).
    afficher_section_actualite = models.BooleanField(
        "Afficher la section 'Dernière actualité'",
        default=True,
        help_text=(
            "N'apparaît sur la page d'accueil que si une actualité a été "
            "publiée au cours des 30 derniers jours."
        ),
    )
    afficher_section_calendrier = models.BooleanField(
        "Afficher la section 'Prochaines activités'",
        default=True,
        help_text=(
            "N'apparaît sur la page d'accueil que s'il existe au moins une "
            "activité à venir dans le calendrier."
        ),
    )
    image_fond_calendrier = models.ForeignKey(
        "wagtailimages.Image",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        verbose_name="Image de fond de la section 'Prochaines activités'",
        help_text="Idéalement une image évoquant un calendrier/agenda.",
    )

    content_panels = Page.content_panels + [
        FieldPanel("hero_title"),
        FieldPanel("hero_subtitle"),
        FieldPanel("hero_image"),
        FieldPanel("hero_cta_text"),
        FieldPanel("hero_cta_link"),
        FieldPanel("intro"),
        MultiFieldPanel(
            [
                FieldPanel("afficher_section_actualite"),
                FieldPanel("afficher_section_calendrier"),
                FieldPanel("image_fond_calendrier"),
            ],
            heading="Sections dynamiques (actualité récente & prochaines activités)",
        ),
        InlinePanel("sections", label="Sections en défilement"),
    ]

    # Remplace les onglets "Promotion" par défaut de Wagtail par ceux, plus
    # complets, fournis par wagtail-seo (titre/description SEO, image de
    # partage, Open Graph, Twitter Card, données structurées...).
    promote_panels = SeoMixin.seo_panels

    class Meta:
        verbose_name = "Page d'accueil"

    def get_context(self, request, *args, **kwargs):
        context = super().get_context(request, *args, **kwargs)

        # Import local pour éviter toute dépendance circulaire au chargement
        # des applications (home <-> news / calendrier).
        from datetime import date, timedelta

        from calendrier.models import Activite
        from news.models import NewsPage

        # --- Section "Dernière actualité" (30 derniers jours) -------------
        context["derniere_actualite"] = None
        if self.afficher_section_actualite:
            il_y_a_30_jours = date.today() - timedelta(days=30)
            context["derniere_actualite"] = (
                NewsPage.objects.live()
                .public()
                .filter(date__gte=il_y_a_30_jours)
                .order_by("-date")
                .first()
            )

        # --- Section "Prochaines activités" (5 premières à partir d'aujourd'hui) ---
        context["prochaines_activites"] = []
        if self.afficher_section_calendrier:
            # date_fin__gte : inclut aussi une activité en cours (déjà
            # commencée mais pas encore terminée), pas seulement celles qui
            # débutent aujourd'hui ou après.
            activites = Activite.objects.filter(date_fin__gte=date.today())
            # Une activité privée ne doit être visible que par les
            # personnes connectées, même dans cet aperçu de la page d'accueil.
            if not request.user.is_authenticated:
                activites = activites.filter(visibilite=Activite.VISIBILITE_PUBLIQUE)
            context["prochaines_activites"] = activites.order_by("date_debut")[:5]

        return context


class HomePageSection(SectionDefilementAbstraite):
    """Section de la page d'accueil (voir SectionDefilementAbstraite pour le
    détail des champs communs)."""

    page = ParentalKey(
        HomePage, on_delete=models.CASCADE, related_name="sections"
    )
