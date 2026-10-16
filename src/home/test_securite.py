"""
Tests de la sécurité des connexions : blocage après plusieurs mots de
passe erronés (django-axes) et règles de mot de passe.

Lancement : python manage.py test home
"""
from axes.utils import reset
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse


class BlocageConnexionsTests(TestCase):

    def setUp(self):
        get_user_model().objects.create_superuser("secretariat", "s@exemple.be", "Un-bon-mot-de-passe")

    def tearDown(self):
        reset()

    def _connexion(self, url, mot_de_passe):
        return self.client.post(url, {"username": "secretariat", "password": mot_de_passe})

    def test_blocage_apres_cinq_echecs(self):
        for _ in range(4):
            self.assertEqual(self._connexion(reverse("login"), "faux").status_code, 200)

        reponse = self._connexion(reverse("login"), "faux")
        self.assertEqual(reponse.status_code, 429)
        self.assertContains(reponse, "Connexion bloquée", status_code=429)
        self.assertContains(reponse, "15 minutes", status_code=429)

        # Même le bon mot de passe est refusé, sur toutes les pages de connexion
        for url in (reverse("login"), "/admin/login/", "/django-admin/login/"):
            self.assertEqual(self._connexion(url, "Un-bon-mot-de-passe").status_code, 429)

    def test_connexion_reussie_remet_le_compteur_a_zero(self):
        for _ in range(4):
            self._connexion(reverse("login"), "faux")
        self.assertEqual(self._connexion(reverse("login"), "Un-bon-mot-de-passe").status_code, 302)
        self.client.logout()

        for _ in range(4):
            self.assertEqual(self._connexion("/admin/login/", "faux").status_code, 200)


class ReglesMotDePasseTests(TestCase):

    def test_mots_de_passe_refuses(self):
        for mot_de_passe in ("court", "1234567890123", "motdepasse"):
            with self.assertRaises(ValidationError):
                validate_password(mot_de_passe)

    def test_mot_de_passe_accepte(self):
        validate_password("Blé-qui-lève-2026")
