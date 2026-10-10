"""
Tests de la newsletter : verrou d'envoi (pas de double envoi entre la tâche
cron et l'admin) et limite d'inscriptions par adresse IP.

Lancement : python manage.py test newsletter
"""
import json
import multiprocessing
import os
import tempfile
from io import StringIO
from unittest import skipUnless

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.core import mail
from django.core.cache import cache
from django.core.management import call_command
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from wagtail.models import Page, Site

from concorde_site.antispam import ip_client

from . import envoi
from .models import Abonne, Envoi, Livraison, Newsletter, NewsletterPage
from .views import LIMITE_PAR_IP


def _tenir_le_verrou(base_dir, verrou_pris, liberer):
    """Exécuté dans un processus séparé : prend le verrou d'envoi comme le
    ferait la tâche cron, et le garde jusqu'au signal `liberer`."""
    with override_settings(BASE_DIR=base_dir):
        with envoi._verrou_envoi():
            verrou_pris.set()
            liberer.wait(10)


class VerrouEnvoiTests(TestCase):
    """Un seul lot à la fois, tous processus confondus : sinon deux lots
    liraient les mêmes livraisons et l'abonné recevrait la lettre deux fois."""

    def setUp(self):
        # Fichier de verrou dans un dossier temporaire, pas dans src/tmp/.
        dossier = tempfile.TemporaryDirectory()
        self.addCleanup(dossier.cleanup)
        reglages = override_settings(
            BASE_DIR=dossier.name,
            EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
            NEWSLETTER_PAUSE_SECONDES=0,
        )
        reglages.enable()
        self.addCleanup(reglages.disable)
        self.base_dir = dossier.name

    def _envoi_en_cours(self, nb_abonnes=1):
        newsletter = Newsletter.objects.create(titre="Lettre de test", objet="Des nouvelles")
        envoi_obj = Envoi.objects.create(newsletter=newsletter)
        for i in range(nb_abonnes):
            abonne = Abonne.objects.create(email=f"abonne{i}@exemple.be")
            Livraison.objects.create(envoi=envoi_obj, abonne=abonne, email=abonne.email)
        return newsletter, envoi_obj

    def test_lot_refuse_si_un_lot_tourne_deja_dans_le_meme_processus(self):
        with envoi._verrou_envoi():
            with self.assertRaises(envoi.EnvoiDejaEnCours):
                envoi.traiter_lot()

    @skipUnless(hasattr(os, "fork"), "nécessite fork (Linux, comme o2switch)")
    def test_lot_refuse_si_un_autre_processus_tient_le_verrou(self):
        contexte = multiprocessing.get_context("fork")
        verrou_pris, liberer = contexte.Event(), contexte.Event()
        processus = contexte.Process(target=_tenir_le_verrou, args=(self.base_dir, verrou_pris, liberer))
        processus.start()
        try:
            self.assertTrue(verrou_pris.wait(10), "le processus enfant n'a pas pris le verrou")
            with self.assertRaises(envoi.EnvoiDejaEnCours):
                envoi.traiter_lot()
        finally:
            liberer.set()
            processus.join(10)

        # Le premier lot terminé, le verrou est de nouveau disponible.
        with envoi._verrou_envoi():
            pass

    def test_verrou_libere_apres_un_lot(self):
        self._envoi_en_cours(nb_abonnes=2)

        self.assertEqual(envoi.traiter_lot(), 2)
        self.assertEqual(len(mail.outbox), 2)

        # Deuxième passage : rien à renvoyer, et pas de verrou resté bloqué.
        self.assertEqual(envoi.traiter_lot(), 0)
        self.assertEqual(len(mail.outbox), 2)

    def test_commande_cron_ne_fait_rien_si_un_lot_tourne(self):
        self._envoi_en_cours()
        sortie = StringIO()
        with envoi._verrou_envoi():
            call_command("envoyer_newsletters", stdout=sortie)

        self.assertIn("déjà en cours", sortie.getvalue())
        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(Livraison.objects.filter(statut=Livraison.STATUT_A_ENVOYER).count(), 1)

    def test_bouton_admin_ne_double_pas_un_lot_en_cours(self):
        newsletter, _ = self._envoi_en_cours()
        admin = get_user_model().objects.create_superuser("admin", "admin@exemple.be", "mdp")
        self.client.force_login(admin)

        with envoi._verrou_envoi():
            reponse = self.client.post(
                reverse("newsletter_admin:suivi", args=[newsletter.pk]), {"action": "lot"}
            )

        self.assertEqual(reponse.status_code, 302)
        textes = [str(m) for m in get_messages(reponse.wsgi_request)]
        self.assertTrue(any("déjà en cours" in t for t in textes), textes)
        self.assertEqual(len(mail.outbox), 0)


@override_settings(CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}})
class LimiteInscriptionTests(TestCase):
    """Au plus LIMITE_PAR_IP inscriptions par heure depuis une même adresse IP."""

    def setUp(self):
        cache.clear()
        racine = Page.objects.get(depth=1)
        self.page = racine.add_child(instance=NewsletterPage(
            title="Newsletter", slug="newsletter-test", confirmation_par_email=False,
        ))
        Site.objects.all().delete()
        Site.objects.create(hostname="testserver", root_page=self.page, is_default_site=True)

    def _inscrire(self, numero, **entetes):
        return self.client.post(
            self.page.url,
            {"email": f"visiteur{numero}@exemple.be", "consentement": "on"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            **entetes,
        )

    def test_ip_lue_dans_remote_addr_et_non_dans_x_forwarded_for(self):
        requete = RequestFactory().post("/", HTTP_X_FORWARDED_FOR="1.2.3.4", REMOTE_ADDR="9.9.9.9")
        self.assertEqual(ip_client(requete), "9.9.9.9")

    def test_limite_atteinte_meme_en_changeant_x_forwarded_for(self):
        for numero in range(LIMITE_PAR_IP):
            reponse = self._inscrire(numero, HTTP_X_FORWARDED_FOR=f"10.0.0.{numero}")
            self.assertEqual(reponse.status_code, 200, reponse.content)

        reponse = self._inscrire(LIMITE_PAR_IP, HTTP_X_FORWARDED_FOR="10.0.0.250")
        self.assertEqual(reponse.status_code, 400)
        self.assertIn("Trop de tentatives", json.loads(reponse.content)["message"])
        self.assertEqual(Abonne.objects.count(), LIMITE_PAR_IP)

    def test_limite_propre_a_chaque_ip(self):
        for numero in range(LIMITE_PAR_IP):
            self._inscrire(numero, REMOTE_ADDR="192.0.2.1")

        reponse = self._inscrire(LIMITE_PAR_IP, REMOTE_ADDR="192.0.2.2")
        self.assertEqual(reponse.status_code, 200, reponse.content)


class CacheTests(TestCase):
    def test_cache_partage_entre_processus(self):
        # Le cache mémoire est propre à chaque processus Passenger : la limite
        # par IP n'y serait pas partagée.
        self.assertEqual(
            settings.CACHES["default"]["BACKEND"],
            "django.core.cache.backends.filebased.FileBasedCache",
        )
