"""Tests de la vérification de l'adresse du site (verifier_adresse_site)."""
from io import StringIO

from django.core.management import call_command
from django.test import TestCase, override_settings
from wagtail.models import Site


@override_settings(ALLOWED_HOSTS=["la-concorde.be", "www.la-concorde.be"])
class VerifierAdresseSiteTests(TestCase):
    def _lancer(self):
        sortie, erreurs = StringIO(), StringIO()
        call_command("verifier_adresse_site", stdout=sortie, stderr=erreurs)
        return sortie.getvalue(), erreurs.getvalue()

    def test_localhost_signale(self):
        Site.objects.update(hostname="localhost", port=80)
        _sortie, erreurs = self._lancer()
        self.assertIn("« localhost »", erreurs)
        self.assertIn("port 80", erreurs)

    def test_hote_absent_de_allowed_hosts_signale(self):
        Site.objects.update(hostname="ancien-domaine.be", port=443)
        _sortie, erreurs = self._lancer()
        self.assertIn("n'est pas dans ALLOWED_HOSTS", erreurs)

    def test_adresse_correcte(self):
        Site.objects.update(hostname="www.la-concorde.be", port=443)
        sortie, erreurs = self._lancer()
        self.assertIn("Adresse du site correcte", sortie)
        self.assertEqual(erreurs, "")
