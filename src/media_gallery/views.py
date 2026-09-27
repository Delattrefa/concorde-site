"""
Vue permettant d'ajouter plusieurs photos en une seule fois à un album,
plutôt que de devoir les ajouter une par une depuis l'admin Wagtail
(InlinePanel classique). Réservée aux administrateurs (is_staff), comme la
gestion des réservations dans l'app 'calendrier'.
"""
from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.shortcuts import get_object_or_404, redirect, render

from wagtail.images.models import Image

from .forms import AjoutPhotosForm
from .models import GalleryAlbum, GalleryImage


def _est_administrateur(user):
    return user.is_authenticated and user.is_staff


@user_passes_test(_est_administrateur, login_url="login")
def ajouter_photos(request, album_id):
    """Affiche et traite le formulaire d'ajout de plusieurs photos à la fois
    dans l'album donné."""

    album = get_object_or_404(GalleryAlbum, pk=album_id)

    if request.method == "POST":
        form = AjoutPhotosForm(request.POST, request.FILES)
        if form.is_valid():
            fichiers = form.cleaned_data["images"]

            # Les nouvelles photos viennent après celles déjà présentes
            # dans l'album, pour ne pas perturber l'ordre existant.
            ordre_depart = album.gallery_images.count()

            for index, fichier in enumerate(fichiers):
                image_wagtail = Image.objects.create(
                    title=fichier.name,
                    file=fichier,
                )
                GalleryImage.objects.create(
                    page=album,
                    image=image_wagtail,
                    sort_order=ordre_depart + index,
                )

            messages.success(
                request,
                f"{len(fichiers)} photo(s) ajoutée(s) à l'album « {album.title} ».",
            )
            return redirect("galerie_ajouter_photos", album_id=album.pk)
    else:
        form = AjoutPhotosForm()

    return render(
        request,
        "media_gallery/ajouter_photos.html",
        {"form": form, "album": album},
    )
