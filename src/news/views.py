"""
Vues permettant à un utilisateur connecté de publier, modifier et
supprimer directement des actualités depuis le site public, sans passer
par l'admin Wagtail.

Règle de permission (CREATE/UPDATE/DELETE) :
- N'IMPORTE QUEL utilisateur connecté peut publier une actualité, qui est
  immédiatement visible sur le site (pas de brouillon ni de modération).
- Un utilisateur ne peut modifier ou supprimer QUE les actualités qu'il a
  lui-même créées depuis le site (voir NewsPage.peut_etre_modifiee_par).
  Les actualités créées depuis l'admin Wagtail restent gérables uniquement
  depuis cet admin (CRUD complet natif de Wagtail, voir README).
"""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.text import slugify

from wagtail.images.models import Image

from .forms import NewsPageForm
from .models import NewsIndexPage, NewsPage


def _texte_depuis_le_corps(body):
    """Reconstitue un texte brut à partir du contenu par blocs de
    l'article, pour pré-remplir le champ 'contenu' du formulaire simplifié
    lors d'une modification.

    Limite connue et acceptée : seuls les blocs 'paragraphe' sont repris.
    Un contenu enrichi depuis l'admin Wagtail avec d'autres types de blocs
    (citation, image, encart...) ne sera pas restitué dans ce formulaire
    simplifié ; le modifier depuis l'admin Wagtail dans ce cas plutôt que
    depuis le site public.
    """
    morceaux = [str(bloc.value) for bloc in body if bloc.block_type == "paragraph"]
    return "\n\n".join(morceaux)


@login_required
def ajouter_news(request):
    """CREATE — Affiche et traite le formulaire public d'ajout d'une actualité."""

    page_index = NewsIndexPage.objects.live().first()
    if page_index is None:
        # Cas improbable : aucune page 'Actualités' n'a encore été créée
        # dans l'arborescence Wagtail du site.
        messages.error(
            request,
            "Aucune page 'Actualités' n'a encore été créée sur le site. "
            "Contactez un administrateur.",
        )
        return redirect("/")

    if request.method == "POST":
        form = NewsPageForm(request.POST, request.FILES)
        if form.is_valid():
            donnees = form.cleaned_data

            # Génère un identifiant d'URL (slug) unique à partir du titre,
            # en y ajoutant un horodatage pour éviter toute collision entre
            # deux actualités portant un titre identique ou proche.
            base_slug = slugify(donnees["titre"])[:180] or "actualite"
            horodatage = timezone.now().strftime("%Y%m%d%H%M%S")

            news = NewsPage(
                title=donnees["titre"],
                slug=f"{base_slug}-{horodatage}",
                date=timezone.now().date(),
                intro=donnees.get("intro", ""),
                author=request.user.get_full_name() or request.user.username,
                lien_texte=donnees.get("lien_texte", ""),
                lien_url=donnees.get("lien_url", ""),
                cree_par=request.user,
            )

            if donnees.get("contenu"):
                news.body = [("paragraph", donnees["contenu"])]

            if donnees.get("image"):
                image_wagtail = Image.objects.create(
                    title=news.title,
                    file=donnees["image"],
                )
                news.featured_image = image_wagtail

            # Insertion dans l'arborescence Wagtail (obligatoire pour toute
            # Page) puis publication immédiate.
            page_index.add_child(instance=news)
            news.save_revision().publish()

            messages.success(request, "Votre actualité a bien été publiée.")
            return redirect(news.url)
    else:
        form = NewsPageForm()

    return render(
        request,
        "news/news_form.html",
        {"form": form, "page_index": page_index, "mode": "ajout"},
    )


@login_required
def modifier_news(request, pk):
    """UPDATE — Modification d'une actualité déjà créée depuis le site
    (réservé à son auteur)."""

    news = get_object_or_404(NewsPage, pk=pk)
    if not news.peut_etre_modifiee_par(request.user):
        raise PermissionDenied("Vous ne pouvez modifier que les actualités que vous avez créées.")

    if request.method == "POST":
        form = NewsPageForm(request.POST, request.FILES)
        if form.is_valid():
            donnees = form.cleaned_data

            news.title = donnees["titre"]
            news.intro = donnees.get("intro", "")
            news.lien_texte = donnees.get("lien_texte", "")
            news.lien_url = donnees.get("lien_url", "")
            news.body = [("paragraph", donnees["contenu"])] if donnees.get("contenu") else []

            if donnees.get("image"):
                image_wagtail = Image.objects.create(
                    title=news.title,
                    file=donnees["image"],
                )
                news.featured_image = image_wagtail

            news.save_revision().publish()

            messages.success(request, "L'actualité a bien été modifiée.")
            return redirect(news.url)
    else:
        form = NewsPageForm(
            initial={
                "titre": news.title,
                "intro": news.intro,
                "contenu": _texte_depuis_le_corps(news.body),
                "lien_texte": news.lien_texte,
                "lien_url": news.lien_url,
            }
        )

    return render(
        request,
        "news/news_form.html",
        {"form": form, "page_index": news.get_parent(), "news": news, "mode": "modification"},
    )


@login_required
def supprimer_news(request, pk):
    """DELETE — Suppression d'une actualité créée depuis le site (réservé
    à son auteur), avec demande de confirmation."""

    news = get_object_or_404(NewsPage, pk=pk)
    if not news.peut_etre_modifiee_par(request.user):
        raise PermissionDenied("Vous ne pouvez supprimer que les actualités que vous avez créées.")

    if request.method == "POST":
        page_parent = news.get_parent()
        titre = news.title
        news.delete()
        messages.success(request, f"L'actualité « {titre} » a bien été supprimée.")
        return redirect(page_parent.url if page_parent else "/")

    return render(request, "news/news_confirm_delete.html", {"news": news})
