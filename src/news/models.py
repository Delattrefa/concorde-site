from django.conf import settings
from django.db import models
from django.shortcuts import render

from modelcluster.contrib.taggit import ClusterTaggableManager
from modelcluster.fields import ParentalKey
from taggit.models import TaggedItemBase

from wagtail.admin.panels import FieldPanel, MultiFieldPanel
from wagtail.blocks import CharBlock, RichTextBlock
from wagtail.fields import RichTextField, StreamField
from wagtail.images.blocks import ImageChooserBlock
from wagtail.models import Page
from wagtail.search import index
from wagtailseo.models import SeoMixin, SeoType, TwitterCard

from info.models import CalloutBlock, LinkBlock
from news.blocks import QuoteBlock


class NewsIndexPage(SeoMixin, Page):
    """Page 'Actualités' : liste tous les articles (pages enfants NewsPage),
    du plus récent au plus ancien, avec filtre par mot-clé (tag) et pagination."""

    max_count = 1
    intro = RichTextField(blank=True)

    subpage_types = ["news.NewsPage"]

    content_panels = Page.content_panels + [
        FieldPanel("intro"),
    ]

    promote_panels = SeoMixin.seo_panels

    class Meta:
        verbose_name = "Page actualités"

    def get_posts(self):
        return NewsPage.objects.child_of(self).live().order_by("-date")

    def get_context(self, request, *args, **kwargs):
        context = super().get_context(request, *args, **kwargs)

        posts = self.get_posts()

        tag = request.GET.get("tag")
        if tag:
            posts = posts.filter(tags__name__iexact=tag)
        context["active_tag"] = tag

        from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator

        paginator = Paginator(posts, 6)
        page_number = request.GET.get("page")
        try:
            posts = paginator.page(page_number)
        except PageNotAnInteger:
            posts = paginator.page(1)
        except EmptyPage:
            posts = paginator.page(paginator.num_pages)

        context["posts"] = posts

        # Nuage de mots-clés à partir des articles publiés
        all_tags = []
        for post in self.get_posts():
            all_tags.extend([t.name for t in post.tags.all()])
        context["all_tags"] = sorted(set(all_tags), key=str.lower)

        return context


class NewsPageTag(TaggedItemBase):
    content_object = ParentalKey(
        "news.NewsPage", on_delete=models.CASCADE, related_name="tagged_items"
    )


class NewsPage(SeoMixin, Page):
    """Un article d'actualité / de blog."""

    parent_page_types = ["news.NewsIndexPage"]
    subpage_types = []

    # Indique à wagtail-seo qu'il s'agit d'un contenu de type "article"
    # (utilisé pour les données structurées Schema.org : NewsArticle/BlogPosting).
    seo_content_type = SeoType.ARTICLE
    seo_twitter_card = TwitterCard.LARGE

    date = models.DateField(
        "Date de publication", help_text="Utilisée pour trier les articles."
    )
    intro = models.CharField(
        max_length=300,
        blank=True,
        help_text="Court résumé affiché dans la liste des actualités.",
    )
    featured_image = models.ForeignKey(
        "wagtailimages.Image",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    author = models.CharField(max_length=100, blank=True)
    tags = ClusterTaggableManager(through=NewsPageTag, blank=True)

    # Lien hypertexte facultatif (ex : vers un événement externe, un
    # article source, une billetterie...), affiché comme bouton d'appel à
    # l'action sur la page de l'article.
    lien_texte = models.CharField(
        "Texte du lien", max_length=100, blank=True,
        help_text="Ex : 'Réserver vos places'. Laisser vide si pas de lien.",
    )
    lien_url = models.URLField("Adresse du lien", blank=True)

    # Utilisateur ayant créé l'actualité depuis le site (formulaire public).
    # Vide pour les actualités créées directement depuis l'admin Wagtail.
    # Champ technique : jamais affiché dans les formulaires, utilisé
    # uniquement pour restreindre la modification/suppression à son auteur.
    cree_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="news_creees",
        editable=False,
        verbose_name="Créée depuis le site par",
    )

    body = StreamField(
        [
            ("heading", CharBlock(icon="title", form_classname="title")),
            ("paragraph", RichTextBlock(icon="pilcrow")),
            ("image", ImageChooserBlock(icon="image")),
            ("quote", QuoteBlock()),
            ("callout", CalloutBlock()),
            ("useful_link", LinkBlock()),
        ],
        blank=True,
    )

    search_fields = Page.search_fields + [
        index.SearchField("intro"),
        index.SearchField("body"),
        index.FilterField("date"),
    ]

    content_panels = Page.content_panels + [
        FieldPanel("date"),
        FieldPanel("intro"),
        FieldPanel("featured_image"),
        FieldPanel("author"),
        FieldPanel("tags"),
        FieldPanel("body"),
        MultiFieldPanel(
            [FieldPanel("lien_texte"), FieldPanel("lien_url")],
            heading="Lien externe (facultatif)",
        ),
    ]

    promote_panels = SeoMixin.seo_panels

    class Meta:
        verbose_name = "Article d'actualité"
        verbose_name_plural = "Articles d'actualité"
        ordering = ["-date"]

    def get_context(self, request, *args, **kwargs):
        context = super().get_context(request, *args, **kwargs)
        context["related_posts"] = (
            NewsPage.objects.sibling_of(self)
            .exclude(id=self.id)
            .live()
            .order_by("-date")[:3]
        )
        # Calculé ici (et non dans le template, qui ne peut pas appeler une
        # méthode avec un argument) : contrôle l'affichage des boutons
        # Modifier/Supprimer, réservés à l'auteur de l'actualité.
        context["peut_modifier"] = self.peut_etre_modifiee_par(request.user)
        return context

    def peut_etre_modifiee_par(self, user):
        """Seul l'utilisateur ayant créé l'actualité depuis le site peut la
        modifier ou la supprimer via les pages publiques. Les actualités
        créées depuis l'admin Wagtail (cree_par vide) ne sont modifiables
        que depuis cet admin, pas depuis le site public."""
        return (
            user.is_authenticated
            and self.cree_par_id is not None
            and self.cree_par_id == user.id
        )
