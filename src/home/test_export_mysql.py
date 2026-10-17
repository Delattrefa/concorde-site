"""
Tests de la préparation de la base locale à son export vers MySQL
(commande preparer_export_mysql).

Lancement : python manage.py test home
"""
from datetime import date
from io import StringIO

from django.core.management import CommandError, call_command
from django.test import TestCase
from taggit.models import Tag
from wagtail.contrib.redirects.models import Redirect
from wagtail.models import Page, PageLogEntry

from news.models import NewsIndexPage, NewsPage


class PreparerExportMysqlTests(TestCase):

    def setUp(self):
        racine = Page.objects.get(depth=1)
        self.index = racine.add_child(instance=NewsIndexPage(title="Actualités", slug="actualites"))

    def _actualite(self, titre, mots):
        news = self.index.add_child(instance=NewsPage(title=titre, slug=titre.lower(), date=date.today()))
        news.tags.add(*mots)
        news.save_revision().publish()
        return NewsPage.objects.get(pk=news.pk)

    def _preparer(self):
        call_command("preparer_export_mysql", stdout=StringIO(), stderr=StringIO())

    def test_mots_cles_fusionnes_partout(self):
        une = self._actualite("Une", ["theatre"])
        deux = self._actualite("Deux", ["Théâtre"])
        self._actualite("Trois", ["theatre"])

        self._preparer()

        self.assertEqual(list(Tag.objects.values_list("name", flat=True)), ["theatre"])
        for news in (une, deux):
            news.refresh_from_db()
            self.assertEqual([t.name for t in news.tags.all()], ["theatre"])
            revision = news.get_latest_revision_as_object()
            self.assertEqual([t.name for t in revision.tags.all()], ["theatre"])

    def test_redirections_accentuees_et_historique_orphelin_retires(self):
        Redirect.objects.create(old_path="/médias", redirect_link="/medias/", automatically_created=True)
        Redirect.objects.create(old_path="/ancienne", redirect_link="/nouvelle/", automatically_created=True)
        page = self._actualite("Temporaire", [])
        PageLogEntry.objects.log_action(page, "wagtail.edit")
        page.delete()

        self._preparer()

        self.assertEqual(list(Redirect.objects.values_list("old_path", flat=True)), ["/ancienne"])
        self.assertFalse(PageLogEntry.objects.exclude(page_id__in=Page.objects.values("id")).exists())

    def test_doublon_impossible_a_corriger_seul_bloque_l_export(self):
        Redirect.objects.create(old_path="/Contact", redirect_link="/contact/")
        Redirect.objects.create(old_path="/contact", redirect_link="/contact/")

        with self.assertRaises(CommandError):
            self._preparer()
        self.assertEqual(Redirect.objects.count(), 2)
