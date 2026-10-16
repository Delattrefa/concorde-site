"""
Tests des slugs sans accents (les serveurs d'o2switch ne servent pas
les URL accentuées).

Lancement : python manage.py test home
"""
from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from wagtail.models import Page

from .slugs import slug_ascii


class SlugAsciiTests(TestCase):

    def test_accents_et_ligatures(self):
        self.assertEqual(slug_ascii("Marché de Noël"), "marche-de-noel")
        self.assertEqual(slug_ascii("Œuvre à cœur"), "oeuvre-a-coeur")

    def test_formulaire_admin_convertit_le_slug(self):
        champ = Page.get_edit_handler().get_form_class().base_fields["slug"]
        self.assertEqual(champ.clean("la-pétanque"), "la-petanque")


class ConvertirSlugsTests(TestCase):

    def setUp(self):
        self.racine = Page.objects.get(depth=1)

    def _convertir(self):
        call_command("convertir_slugs_ascii", stdout=StringIO())

    def test_page_sous_pages_et_revisions(self):
        parent = self.racine.add_child(instance=Page(title="Médias", slug="médias"))
        enfant = parent.add_child(instance=Page(title="Vidéos", slug="les-vidéos"))
        enfant.save_revision()

        self._convertir()

        parent.refresh_from_db()
        enfant.refresh_from_db()
        self.assertEqual(parent.slug, "medias")
        self.assertEqual(enfant.url_path, "/medias/les-videos/")
        self.assertEqual(enfant.latest_revision.content["slug"], "les-videos")

    def test_slug_deja_pris_par_une_page_soeur(self):
        self.racine.add_child(instance=Page(title="Pétanque", slug="petanque"))
        page = self.racine.add_child(instance=Page(title="Pétanque", slug="pétanque"))

        self._convertir()

        page.refresh_from_db()
        self.assertEqual(page.slug, "petanque-2")
