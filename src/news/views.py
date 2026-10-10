"""
Vues permettant à un utilisateur connecté de publier, modifier et
supprimer directement des actualités depuis le site public, sans passer
par l'admin Wagtail.

Règle de permission (CREATE/UPDATE/DELETE) :
- Tout utilisateur connecté peut proposer une actualité.
- Celle d'un administrateur (is_staff) est publiée immédiatement. Celle d'un
  autre membre est soumise à validation : elle n'est visible sur le site
  qu'après approbation par un administrateur, depuis l'admin Wagtail
  (circuit de validation « Moderators approval », tableau de bord
  « En attente de votre relecture »). Il en va de même pour ses
  modifications : la version en ligne reste affichée jusqu'à l'approbation.
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


def _publie_directement(user):
    """Les administrateurs publient directement ; les autres membres
    soumettent leurs actualités à validation."""
    return user.is_staff


def _enregistrer(news, user):
    """Enregistre une nouvelle version de l'actualité, puis la publie
    (administrateur) ou la soumet à validation (autre membre).
    Renvoie True si elle a été publiée."""
    revision = news.save_revision(user=user, log_action=True)
    if _publie_directement(user):
        # Le droit de publier vient de is_staff (règle du site), pas des
        # groupes Wagtail : un administrateur sans groupe Wagtail doit pouvoir
        # publier depuis le site.
        revision.publish(user=user, skip_permission_checks=True)
        return True

    workflow = news.get_workflow()
    if workflow is not None:
        en_cours = news.current_workflow_state
        if en_cours is not None:
            # Modifiée pendant sa relecture : la validation repart sur la
            # nouvelle version (Wagtail publie la dernière version approuvée).
            en_cours.cancel(user=user)
        workflow.start(news, user)
    return False


MESSAGE_EN_ATTENTE = (
    "Merci ! Votre actualité a été envoyée pour validation : elle sera visible "
    "sur le site dès qu'un administrateur l'aura approuvée."
)


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
                # Hors ligne tant qu'elle n'est pas publiée (voir _enregistrer)
                live=_publie_directement(request.user),
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
            # Page), puis publication ou envoi pour validation.
            page_index.add_child(instance=news)
            if _enregistrer(news, request.user):
                messages.success(request, "Votre actualité a bien été publiée.")
                return redirect(news.url)
            messages.success(request, MESSAGE_EN_ATTENTE)
            return redirect(page_index.url)
    else:
        form = NewsPageForm()

    return render(
        request,
        "news/news_form.html",
        {
            "form": form, "page_index": page_index, "mode": "ajout",
            "publie_directement": _publie_directement(request.user),
        },
    )


@login_required
def modifier_news(request, pk):
    """UPDATE — Modification d'une actualité déjà créée depuis le site
    (réservé à son auteur)."""

    news = get_object_or_404(NewsPage, pk=pk)
    if not news.peut_etre_modifiee_par(request.user):
        raise PermissionDenied("Vous ne pouvez modifier que les actualités que vous avez créées.")
    # On repart de la dernière version enregistrée, éventuellement encore en
    # attente de validation, et non de la version en ligne.
    news = news.get_latest_revision_as_object()

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

            if _enregistrer(news, request.user):
                messages.success(request, "L'actualité a bien été modifiée.")
                return redirect(news.url)
            messages.success(request, MESSAGE_EN_ATTENTE)
            return redirect(news.get_parent().url)
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
        {
            "form": form, "page_index": news.get_parent(), "news": news, "mode": "modification",
            "publie_directement": _publie_directement(request.user),
        },
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
