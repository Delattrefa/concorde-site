"""
Tests de la préparation des collections au déploiement : Calendrier ›
Signature créées ou rangées, signatures réservées aux super-utilisateurs
dans Wagtail, fichiers de signature à l'abri.

Lancement : python manage.py test calendrier.test_collections
"""
import io

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.db.models.signals import post_save
from django.test import TestCase
from PIL import Image as ImagePIL
from wagtail.images import get_image_model
from wagtail.images.permissions import permission_policy
from wagtail.models import Collection, GroupCollectionPermission

from .collections import (
    DOSSIER_SIGNATURES, collection_calendrier, collection_signatures, preparer_collections,
    proteger_signature_enregistree,
)
from .forms import images_de_signature


def _png(nom="signature.png"):
    tampon = io.BytesIO()
    ImagePIL.new("RGB", (60, 20), "black").save(tampon, format="PNG")
    return SimpleUploadedFile(nom, tampon.getvalue(), content_type="image/png")


class PreparerCollectionsTests(TestCase):

    def setUp(self):
        self.racine = Collection.get_first_root_node()

    def test_creation_puis_sans_effet(self):
        self.assertTrue(preparer_collections())
        self.assertEqual(collection_signatures().get_parent(), collection_calendrier())
        self.assertEqual(collection_calendrier().get_parent(), self.racine)
        self.assertEqual(preparer_collections(), [])

    def test_signature_rangee_ailleurs_deplacee_avec_ses_images(self):
        ailleurs = self.racine.add_child(name="images du site").add_child(name="signature")
        image = get_image_model().objects.create(title="Signature Jean", collection=ailleurs, file=_png())

        preparer_collections()

        self.assertEqual(Collection.objects.filter(name__iexact="signature").count(), 1)
        image.refresh_from_db()
        self.assertEqual(image.collection, collection_signatures())
        self.assertEqual(list(images_de_signature()), [image])

    def test_signatures_reservees_aux_super_utilisateurs(self):
        # Le groupe Editors créé par Wagtail a ses droits sur Root
        editors = Group.objects.get(name="Editors")
        self.assertTrue(GroupCollectionPermission.objects.filter(group=editors, collection=self.racine).exists())
        editeur = get_user_model().objects.create_user("editeur", "e@exemple.be", "mdp")
        editeur.groups.add(editors)
        site = self.racine.add_child(name="images du site")
        calendrier = self.racine.add_child(name="Calendrier")

        preparer_collections()

        photo = get_image_model().objects.create(title="Photo", collection=site, file=_png("photo.png"))
        signature = get_image_model().objects.create(title="Signature", collection=collection_signatures(), file=_png())
        visibles = permission_policy.instances_user_has_permission_for(editeur, "choose")
        self.assertIn(photo, visibles)
        self.assertNotIn(signature, visibles)
        droits_images = GroupCollectionPermission.objects.filter(permission__content_type__app_label="wagtailimages")
        self.assertFalse(droits_images.filter(collection__in=[self.racine, calendrier]).exists())
        # Les droits sur les documents ne sont pas concernés
        self.assertTrue(GroupCollectionPermission.objects.filter(
            collection=self.racine, permission__content_type__app_label="wagtaildocs").exists())

        admin = get_user_model().objects.create_superuser("admin", "a@exemple.be", "mdp")
        self.assertIn(signature, permission_policy.instances_user_has_permission_for(admin, "choose"))

    def test_fichier_de_signature_a_l_abri(self):
        preparer_collections()
        image = get_image_model().objects.create(title="Signature", collection=collection_signatures(), file=_png("jean.png"))

        image.refresh_from_db()
        self.assertTrue(image.file.name.startswith(DOSSIER_SIGNATURES))
        self.assertNotIn("jean", image.file.name)
        self.assertTrue(image.file.storage.exists(image.file.name))
        self.assertNotIn("jean", image.get_rendition("max-100x100").url)

    def test_signature_existante_protegee_au_deploiement(self):
        calendrier = self.racine.add_child(name="Calendrier")
        signature = calendrier.add_child(name="Signature")
        # Image enregistrée avant la mise en place (signal coupé)
        post_save.disconnect(proteger_signature_enregistree, sender=get_image_model(), dispatch_uid="calendrier_proteger_signature")
        try:
            image = get_image_model().objects.create(title="Signature", collection=signature, file=_png("jean.png"))
        finally:
            post_save.connect(proteger_signature_enregistree, sender=get_image_model(), dispatch_uid="calendrier_proteger_signature")
        self.assertTrue(image.file.name.startswith("original_images/"))

        call_command("preparer_collections", stdout=io.StringIO())

        image.refresh_from_db()
        self.assertTrue(image.file.name.startswith(DOSSIER_SIGNATURES))
