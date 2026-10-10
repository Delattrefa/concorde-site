"""
Tests de la demande publique de réservation de salle : protection anti-spam
(champ piège et limite par adresse IP).

Lancement : python manage.py test calendrier
"""
from datetime import date, timedelta

from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import Reservation
from .views import LIMITE_DEMANDES_PAR_IP


@override_settings(
    CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}},
    STORAGES={"staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}},
)
class DemandeReservationAntispamTests(TestCase):
    url = reverse("calendrier:reservation_demander")

    def setUp(self):
        cache.clear()

    def _demander(self, numero=0, entetes=None, **champs):
        jour = date.today() + timedelta(days=30 + numero)
        donnees = {
            "type_client": Reservation.TYPE_PARTICULIER,
            "nom": "Dupont", "prenom": "Marie", "adresse": "Rue de la Station 1, 1000 Bruxelles",
            "email": f"marie{numero}@exemple.be", "telephone": "0470 12 34 56",
            "date_debut": jour.isoformat(), "date_fin": jour.isoformat(),
        }
        donnees.update(champs)
        return self.client.post(self.url, donnees, REMOTE_ADDR="192.0.2.1", **(entetes or {}))

    def test_demande_normale_enregistree(self):
        reponse = self._demander()
        self.assertEqual(reponse.status_code, 302)
        self.assertEqual(Reservation.objects.count(), 1)

    def test_champ_piege_rempli_rien_enregistre_mais_reponse_normale(self):
        reponse = self._demander(website="https://spam.example")
        self.assertEqual(reponse.status_code, 302)
        self.assertEqual(Reservation.objects.count(), 0)

    def test_limite_par_ip(self):
        for numero in range(LIMITE_DEMANDES_PAR_IP):
            self.assertEqual(self._demander(numero).status_code, 302)

        reponse = self._demander(LIMITE_DEMANDES_PAR_IP, entetes={"HTTP_X_FORWARDED_FOR": "10.9.9.9"})
        self.assertEqual(reponse.status_code, 200)
        self.assertContains(reponse, "Trop de demandes")
        self.assertEqual(Reservation.objects.count(), LIMITE_DEMANDES_PAR_IP)

    def test_erreurs_de_saisie_non_comptees(self):
        for _ in range(LIMITE_DEMANDES_PAR_IP + 2):
            self.assertEqual(self._demander(email="pas-une-adresse").status_code, 200)

        self.assertEqual(self._demander().status_code, 302)

    def test_formulaire_contient_le_champ_piege(self):
        self.assertContains(self.client.get(self.url), 'name="website"')
