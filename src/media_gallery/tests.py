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

    def _ajouter_lot(self, *noms):
        return self.client.post(
            reverse("galerie_ajouter_photos", args=[self.album.pk]),
            {"images": [_photo(nom) for nom in noms]},
            headers={"x-requested-with": "XMLHttpRequest"},
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

    def test_envoi_par_lots(self):
        self.client.force_login(self.admin)

        self.assertEqual(self._ajouter_lot("lot1_a.png", "lot1_b.png").json(), {"ajoutees": 2})
        self.assertEqual(self._ajouter_lot("lot2_a.png").json(), {"ajoutees": 1})
        fin = self.client.post(
            reverse("galerie_ajouter_photos", args=[self.album.pk]) + "?retour=admin",
            {"etape": "terminer"},
            headers={"x-requested-with": "XMLHttpRequest"},
        )

        self.assertEqual(fin.json(), {"redirection": reverse("wagtailadmin_pages:edit", args=[self.album.pk])})
        self.assertEqual(
            [g.image.title for g in self._version_en_ligne().gallery_images.all()],
            ["lot1 a", "lot1 b", "lot2 a"],
        )
        messages = [str(m) for m in fin.wsgi_request._messages]
        self.assertEqual(messages, ["3 photo(s) ajoutée(s) à l'album « Spectacle 2026 »."])

    def test_lot_invalide_renvoie_les_erreurs(self):
        self.client.force_login(self.admin)
        faux = SimpleUploadedFile("faux.png", b"pas une image", content_type="image/png")

        reponse = self.client.post(
            reverse("galerie_ajouter_photos", args=[self.album.pk]),
            {"images": [faux]},
            headers={"x-requested-with": "XMLHttpRequest"},
        )

        self.assertEqual(reponse.status_code, 400)
        self.assertIn("« faux.png » n'est pas une image valide", reponse.json()["erreurs"][0])
        self.assertEqual(self.album.gallery_images.count(), 0)

    def test_miniatures_generees_a_l_envoi(self):
        from django.core.cache import cache

        from .views import FORMATS_PHOTO_ALBUM

        # Les identifiants d'images sont réutilisés d'un test à l'autre : sans
        # cela, Wagtail retrouverait en cache les miniatures d'un test précédent.
        cache.clear()
        self.client.force_login(self.admin)
        self._ajouter_lot("affiche.png")

        image = self.album.gallery_images.get().image
        self.assertEqual(
            sorted(r.filter_spec for r in image.renditions.all()), sorted(FORMATS_PHOTO_ALBUM),
        )

    def test_commande_generer_miniatures(self):
        from django.core.cache import cache
        from django.core.management import call_command
        from wagtail.images.models import Image

        from .models import GalleryImage
        from .views import FORMATS_PHOTO_ALBUM

        cache.clear()  # voir test_miniatures_generees_a_l_envoi
        image = Image.objects.create(title="ancienne", file=_photo("ancienne.png"))
        GalleryImage.objects.create(page=self.album, image=image, sort_order=0)
        self.assertFalse(image.renditions.exists())

        call_command("generer_miniatures", stdout=io.StringIO())

        self.assertEqual(
            sorted(r.filter_spec for r in image.renditions.all()),
            sorted(FORMATS_PHOTO_ALBUM + ("fill-600x450",)),  # photo et couverture de l'album
        )
