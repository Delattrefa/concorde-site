"""
Tests de l'ajout de photos et de vidéos à un album depuis le site
(administrateurs is_staff, avec ou sans groupe Wagtail).

Lancement : python manage.py test media_gallery
"""
import io

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from PIL import Image as ImagePIL
from wagtail.models import Page, Site

from .models import GalleryAlbum, MediaPage


def _photo(nom):
    tampon = io.BytesIO()
    ImagePIL.new("RGB", (40, 30), "teal").save(tampon, format="PNG")
    return SimpleUploadedFile(nom, tampon.getvalue(), content_type="image/png")


class AjoutMediasTests(TestCase):

    def setUp(self):
        Utilisateur = get_user_model()
        # Administrateur du site (is_staff) sans aucun groupe ni droit Wagtail
        self.admin = Utilisateur.objects.create_user("admin", password="mdp", is_staff=True)
        self.membre = Utilisateur.objects.create_user("membre", password="mdp")

        racine = Page.objects.get(depth=1)
        medias = racine.add_child(instance=MediaPage(title="Médias", slug="medias"))
        Site.objects.all().delete()
        Site.objects.create(hostname="testserver", root_page=medias, is_default_site=True)
        self.album = medias.add_child(instance=GalleryAlbum(title="Spectacle 2026", slug="spectacle-2026"))
        self.album.save_revision().publish()

    def _ajouter_photos(self, *noms):
        return self.client.post(
            reverse("galerie_ajouter_photos", args=[self.album.pk]),
            {"images": [_photo(nom) for nom in noms]},
        )

    def _ajouter_video(self):
        return self.client.post(
            reverse("galerie_ajouter_video", args=[self.album.pk]),
            {"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "titre": "Bande-annonce"},
        )

    def _version_en_ligne(self):
        album = GalleryAlbum.objects.get(pk=self.album.pk)
        return album.live_revision.as_object()

    def test_administrateur_sans_groupe_wagtail_ajoute_des_photos(self):
        self.client.force_login(self.admin)

        reponse = self._ajouter_photos("scene_1.png", "scene_2.png")

        self.assertEqual(reponse.status_code, 302)
        en_ligne = self._version_en_ligne()
        self.assertEqual(
            [g.image.title for g in en_ligne.gallery_images.all()], ["scene 1", "scene 2"],
        )

    def test_administrateur_sans_groupe_wagtail_ajoute_une_video(self):
        self.client.force_login(self.admin)

        reponse = self._ajouter_video()

        self.assertRedirects(reponse, self.album.url, fetch_redirect_response=False)
        self.assertEqual([v.titre for v in self._version_en_ligne().videos.all()], ["Bande-annonce"])

    def test_album_hors_ligne_reste_hors_ligne(self):
        self.album.unpublish()
        self.client.force_login(self.admin)

        self._ajouter_photos("coulisses.png")

        album = GalleryAlbum.objects.get(pk=self.album.pk)
        self.assertFalse(album.live)
        self.assertEqual(album.get_latest_revision_as_object().gallery_images.count(), 1)

    def test_reserve_aux_administrateurs(self):
        for utilisateur in (None, self.membre):
            with self.subTest(utilisateur=utilisateur):
                if utilisateur:
                    self.client.force_login(utilisateur)
                for reponse in (self._ajouter_photos("intrus.png"), self._ajouter_video()):
                    self.assertEqual(reponse.status_code, 302)
                    self.assertIn(reverse("login"), reponse.url)

        album = GalleryAlbum.objects.get(pk=self.album.pk)
        self.assertEqual((album.gallery_images.count(), album.videos.count()), (0, 0))
