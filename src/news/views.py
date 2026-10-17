"""
Vues permettant à un utilisateur connecté de publier, modifier et
supprimer directement des actualités depuis le site public, sans passer
par l'admin Wagtail : tous les champs de l'actualité, dont le contenu
complet de l'article (texte enrichi, intertitres, images positionnées,
citations, encarts, liens), composé avec l'éditeur par blocs.

Règle de permission (CREATE/UPDATE/DELETE) :
- Tout utilisateur connecté peut proposer une actualité.
- Celle d'un membre qui a le droit Wagtail de publier les actualités
  (super-utilisateur, groupe « Moderators ») est publiée immédiatement.
  Celle d'un autre membre, même administrateur (is_staff) du calendrier,
  est soumise à validation : elle n'est visible sur le site qu'après
  approbation par un modérateur, depuis l'admin Wagtail
  (circuit de validation « Moderators approval », tableau de bord
  « En attente de votre relecture »). Il en va de même pour ses
  modifications : la version en ligne reste affichée jusqu'à l'approbation.
- Un administrateur (is_staff) peut modifier toutes les actualités depuis
  le site, y compris celles créées dans l'admin Wagtail. Un autre membre ne
  peut modifier QUE les actualités qu'il a lui-même créées depuis le site.
- La suppression depuis le site est réservée à l'auteur de l'actualité
  (voir NewsPage.peut_etre_modifiee_par / peut_etre_supprimee_par) ; les
  autres se suppriment depuis l'admin Wagtail.
"""
import json
import os

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST
from wagtail.images.models import Image

from home.slugs import slug_ascii

from .editeur import apercu_image, corps_vers_editeur, editeur_vers_corps
from .forms import NewsPageForm, PhotoArticleForm
from .models import NewsIndexPage, NewsPage


def _publie_directement(user, page_index):
    """Publient directement ceux qui ont le droit Wagtail de publier dans la
    page des actualités (super-utilisateurs, groupe « Moderators ») ; les
    autres membres, administrateurs (is_staff) compris, soumettent leurs
    actualités à validation."""
    return page_index.permissions_for_user(user).can_publish_subpage()


def _enregistrer(news, user):
    """Enregistre une nouvelle version de l'actualité, puis la publie
    (droit de publier) ou la soumet à validation (autre membre).
    Renvoie True si elle a été publiée."""
    revision = news.save_revision(user=user, log_action=True)
    if _publie_directement(user, news.get_parent()):
        # Actualité d'un membre en cours de relecture : la publication par
        # un modérateur vaut validation, la relecture est close.
        if news.current_workflow_state is not None:
            news.current_workflow_state.cancel(user=user)
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


def _creer_image(fichier, titre, user):
    return Image.objects.create(title=titre[:255] or fichier.name, file=fichier, uploaded_by_user=user)


def _corps_valide(form, stream_block):
    """Contenu de l'article envoyé par l'éditeur, ou None (erreur ajoutée
    au formulaire) s'il est invalide."""
    try:
        return editeur_vers_corps(form.data.get("corps"), stream_block)
    except ValidationError as erreur:
        form.add_error(None, erreur.messages)
        return None


def _appliquer(news, donnees, corps, user):
    """Recopie les champs du formulaire dans l'actualité (avant enregistrement)."""
    news.title = donnees["titre"]
    news.date = donnees["date"]
    news.author = donnees.get("auteur", "")
    news.intro = donnees.get("intro", "")
    news.a_la_une = donnees.get("a_la_une", False)
    news.lien_texte = donnees.get("lien_texte", "")
    news.lien_url = donnees.get("lien_url", "")
    news.body = corps
    news.tags.set(donnees["mots_cles"])
    if donnees.get("image"):
        news.featured_image = _creer_image(donnees["image"], news.title, user)
    elif donnees.get("retirer_image"):
        news.featured_image = None


def _contexte_formulaire(request, form, page_index, **extra):
    return {
        "form": form, "page_index": page_index,
        "publie_directement": _publie_directement(request.user, page_index),
        **extra,
    }


@login_required
def ajouter_news(request):
    """CREATE — Affiche et traite le formulaire d'ajout d'une actualité."""

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

    stream_block = NewsPage._meta.get_field("body").stream_block
    if request.method == "POST":
        form = NewsPageForm(request.POST, request.FILES)
        corps = _corps_valide(form, stream_block)
        if form.is_valid() and corps is not None:
            donnees = form.cleaned_data

            # Génère un identifiant d'URL (slug) unique à partir du titre,
            # en y ajoutant un horodatage pour éviter toute collision entre
            # deux actualités portant un titre identique ou proche.
            base_slug = slug_ascii(donnees["titre"])[:180] or "actualite"
            horodatage = timezone.now().strftime("%Y%m%d%H%M%S")

            news = NewsPage(
                # Hors ligne tant qu'elle n'est pas publiée (voir _enregistrer)
                live=_publie_directement(request.user, page_index),
                slug=f"{base_slug}-{horodatage}",
                cree_par=request.user,
            )
            _appliquer(news, donnees, corps, request.user)

            # Insertion dans l'arborescence Wagtail (obligatoire pour toute
            # Page), puis publication ou envoi pour validation.
            page_index.add_child(instance=news)
            if _enregistrer(news, request.user):
                messages.success(request, "Votre actualité a bien été publiée.")
                return redirect(news.url)
            messages.success(request, MESSAGE_EN_ATTENTE)
            return redirect(page_index.url)
    else:
        form = NewsPageForm(initial={
            "auteur": request.user.get_full_name() or request.user.username,
            "corps": json.dumps([{"type": "paragraph", "value": ""}]),
        })

    return render(request, "news/news_form.html", _contexte_formulaire(request, form, page_index, mode="ajout"))


@login_required
def modifier_news(request, pk):
    """UPDATE — Modification d'une actualité (son auteur, ou un administrateur)."""

    news = get_object_or_404(NewsPage, pk=pk)
    if not news.peut_etre_modifiee_par(request.user):
        raise PermissionDenied("Vous ne pouvez modifier que les actualités que vous avez créées.")
    # On repart de la dernière version enregistrée, éventuellement encore en
    # attente de validation, et non de la version en ligne.
    news = news.get_latest_revision_as_object()

    stream_block = NewsPage._meta.get_field("body").stream_block
    if request.method == "POST":
        form = NewsPageForm(request.POST, request.FILES)
        corps = _corps_valide(form, stream_block)
        if form.is_valid() and corps is not None:
            _appliquer(news, form.cleaned_data, corps, request.user)
            if _enregistrer(news, request.user):
                messages.success(request, "L'actualité a bien été modifiée.")
                return redirect(news.url)
            messages.success(request, MESSAGE_EN_ATTENTE)
            return redirect(news.get_parent().url)
    else:
        form = NewsPageForm(initial={
            "titre": news.title,
            "date": news.date,
            "auteur": news.author,
            "intro": news.intro,
            "a_la_une": news.a_la_une,
            "corps": json.dumps(corps_vers_editeur(news.body)),
            "mots_cles": ", ".join(tag.name for tag in news.tags.all()),
            "lien_texte": news.lien_texte,
            "lien_url": news.lien_url,
        })

    return render(request, "news/news_form.html", _contexte_formulaire(
        request, form, news.get_parent(), mode="modification", news=news,
        peut_supprimer=news.peut_etre_supprimee_par(request.user),
    ))


@login_required
@require_POST
def envoyer_photo(request):
    """Envoi d'une photo pour un bloc image de l'éditeur (requête JavaScript).
    Renvoie l'identifiant de l'image Wagtail créée et l'adresse de son aperçu."""
    form = PhotoArticleForm(request.POST, request.FILES)
    if not form.is_valid():
        erreurs = [str(e) for liste in form.errors.values() for e in liste]
        return JsonResponse({"erreur": " ".join(erreurs) or "Photo refusée."}, status=400)
    fichier = form.cleaned_data["photo"]
    titre = os.path.splitext(fichier.name)[0].replace("_", " ").strip()
    image = _creer_image(fichier, titre, request.user)
    return JsonResponse({"id": image.pk, "apercu": apercu_image(image)})


@login_required
def supprimer_news(request, pk):
    """DELETE — Suppression d'une actualité créée depuis le site (réservé
    à son auteur), avec demande de confirmation."""

    news = get_object_or_404(NewsPage, pk=pk)
    if not news.peut_etre_supprimee_par(request.user):
        raise PermissionDenied("Vous ne pouvez supprimer que les actualités que vous avez créées.")

    if request.method == "POST":
        page_parent = news.get_parent()
        titre = news.title
        news.delete()
        messages.success(request, f"L'actualité « {titre} » a bien été supprimée.")
        return redirect(page_parent.url if page_parent else "/")

    return render(request, "news/news_confirm_delete.html", {"news": news})
