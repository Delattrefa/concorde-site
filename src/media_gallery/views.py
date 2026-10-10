"""
Vue permettant d'ajouter plusieurs photos en une seule fois à un album,
plutôt que de devoir les ajouter une par une depuis l'admin Wagtail
(InlinePanel classique). Réservée aux administrateurs (is_staff), comme la
gestion des réservations dans l'app 'calendrier'.
"""
from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
import os

from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from wagtail.images.models import Image

from .forms import AjoutPhotosForm, AjoutVideoForm
from .models import GalleryAlbum, GalleryImage, GalleryVideo


def _est_administrateur(user):
    return user.is_authenticated and user.is_staff


def _enregistrer_revision(album_pk, utilisateur):
    """Crée une révision Wagtail de l'album à jour (photos et vidéos ajoutées
    comprises) et la publie si l'album est en ligne. Sans cela, une
    modification ultérieure dans l'admin Wagtail repartirait de l'ancienne
    révision et ferait disparaître les ajouts."""
    album = GalleryAlbum.objects.get(pk=album_pk)
    revision = album.save_revision(user=utilisateur, log_action=True)
    if album.live:
        # Le droit d'ajouter des médias vient de is_staff (règle du site), pas
        # des groupes Wagtail : sans cela, un administrateur sans groupe
        # Wagtail recevait une erreur 403 à la publication.
        revision.publish(user=utilisateur, skip_permission_checks=True)


@user_passes_test(_est_administrateur, login_url="login")
def ajouter_photos(request, album_id):
    """Ajout de plusieurs photos en une fois à un album. Accessible depuis
    l'album sur le site, ou depuis l'éditeur de l'album dans l'admin Wagtail
    (?retour=admin : on y revient après l'envoi)."""

    album = get_object_or_404(GalleryAlbum, pk=album_id)
    retour_admin = request.GET.get("retour") == "admin" or request.POST.get("retour") == "admin"
    url_editeur = reverse("wagtailadmin_pages:edit", args=[album.pk])

    if request.method == "POST":
        form = AjoutPhotosForm(request.POST, request.FILES)
        if form.is_valid():
            fichiers = form.cleaned_data["images"]
            collection = form.cleaned_data.get("collection")

            # Les nouvelles photos viennent après celles déjà présentes
            # dans l'album, pour ne pas perturber l'ordre existant.
            ordre_depart = album.gallery_images.count()

            for index, fichier in enumerate(fichiers):
                titre = os.path.splitext(fichier.name)[0].replace("_", " ").strip() or fichier.name
                donnees = {"title": titre, "file": fichier, "uploaded_by_user": request.user}
                if collection is not None:
                    donnees["collection"] = collection
                image_wagtail = Image.objects.create(**donnees)
                GalleryImage.objects.create(
                    page=album,
                    image=image_wagtail,
                    sort_order=ordre_depart + index,
                )

            _enregistrer_revision(album.pk, request.user)

            messages.success(
                request,
                f"{len(fichiers)} photo(s) ajoutée(s) à l'album « {album.title} ».",
            )
            if retour_admin:
                return redirect(url_editeur)
            return redirect("galerie_ajouter_photos", album_id=album.pk)
    else:
        form = AjoutPhotosForm()

    return render(
        request,
        "media_gallery/ajouter_photos.html",
        {"form": form, "album": album, "retour_admin": retour_admin, "url_editeur": url_editeur},
    )


@user_passes_test(_est_administrateur, login_url="login")
def ajouter_video(request, album_id):
    """Ajout rapide d'une vidéo (lien YouTube, Facebook...) à un album."""
    album = get_object_or_404(GalleryAlbum, pk=album_id)

    if request.method == "POST":
        form = AjoutVideoForm(request.POST)
        if form.is_valid():
            GalleryVideo.objects.create(
                page=album,
                url=form.cleaned_data["url"],
                titre=form.cleaned_data["titre"],
                sort_order=album.videos.count(),
            )
            _enregistrer_revision(album.pk, request.user)
            messages.success(request, f"La vidéo a été ajoutée à l'album « {album.title} ».")
            if request.POST.get("encore"):
                return redirect("galerie_ajouter_video", album_id=album.pk)
            return redirect(album.url)
    else:
        form = AjoutVideoForm()

    return render(request, "media_gallery/ajouter_video.html", {"form": form, "album": album})
