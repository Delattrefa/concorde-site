"""
Génère d'avance les miniatures des albums de la galerie, pour que la
première ouverture d'un album ne les crée pas toutes d'un coup (page très
lente, voire interrompue par le serveur).

    python manage.py generer_miniatures              # tous les albums
    python manage.py generer_miniatures --album 25   # un seul album

Les miniatures déjà présentes ne sont pas recréées : la commande peut être
relancée sans risque. Les photos ajoutées depuis le site les reçoivent dès
l'envoi (voir FORMATS_PHOTO_ALBUM dans views.py).
"""
from django.core.management.base import BaseCommand, CommandError

from media_gallery.models import GalleryAlbum
from media_gallery.views import FORMATS_PHOTO_ALBUM

# Formats utilisés par les modèles de pages, en plus de ceux des photos
FORMAT_COUVERTURE = "fill-600x450"                       # media_page.html
FORMATS_VIGNETTE_VIDEO = ("fill-200x150", "fill-640x360")  # gallery_album.html


class Command(BaseCommand):
    help = "Génère d'avance les miniatures des photos, couvertures et vignettes vidéo des albums."

    def add_arguments(self, parser):
        parser.add_argument("--album", type=int, help="Identifiant (pk) d'un seul album à traiter.")

    def handle(self, *args, **options):
        albums = GalleryAlbum.objects.order_by("path")
        if options["album"]:
            albums = albums.filter(pk=options["album"])
            if not albums.exists():
                raise CommandError(f"Aucun album avec l'identifiant {options['album']}.")

        total_images = total_erreurs = 0
        for album in albums:
            a_generer = [(g.image, FORMATS_PHOTO_ALBUM) for g in album.gallery_images.select_related("image")]
            a_generer += [(v.vignette, FORMATS_VIGNETTE_VIDEO) for v in album.videos.exclude(vignette=None).select_related("vignette")]
            couverture = album.couverture
            if couverture is not None:
                a_generer.append((couverture, (FORMAT_COUVERTURE,)))

            erreurs = 0
            for image, formats in a_generer:
                try:
                    image.get_renditions(*formats)
                except Exception as exc:  # fichier manquant ou illisible : on continue
                    erreurs += 1
                    self.stderr.write(f"  « {image.title} » (image {image.pk}) : {exc}")

            total_images += len(a_generer)
            total_erreurs += erreurs
            self.stdout.write(f"{album.title} : {len(a_generer) - erreurs} image(s) traitée(s)"
                              + (f", {erreurs} erreur(s)" if erreurs else ""))

        style = self.style.WARNING if total_erreurs else self.style.SUCCESS
        self.stdout.write(style(
            f"Terminé : {albums.count()} album(s), {total_images - total_erreurs} image(s) traitée(s)"
            + (f", {total_erreurs} erreur(s)." if total_erreurs else ".")
        ))
