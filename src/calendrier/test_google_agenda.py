"""
Tests de la recopie vers l'agenda Google partagé (google_agenda.py) : les
appels à Google sont remplacés par un faux agenda en mémoire.

Lancement : python manage.py test calendrier.test_google_agenda
"""
from datetime import date
from io import StringIO
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from . import google_agenda
from .models import Activite, Reservation


class Reponse:
    def __init__(self, statut=200, donnees=None):
        self.status_code, self._donnees = statut, donnees or {}

    def json(self):
        return self._donnees

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class FauxAgenda:
    """Imite l'API Google Agenda : événements rangés par identifiant."""

    def __init__(self):
        self.evenements, self.suivant, self.en_panne = {}, 1, False

    def _id(self, url):
        return url.rsplit("/", 1)[1]

    def _verifier(self):
        if self.en_panne:
            raise ConnectionError("Google injoignable")

    def post(self, url, json, timeout):
        self._verifier()
        event_id = f"evt{self.suivant}"
        self.suivant += 1
        self.evenements[event_id] = json
        return Reponse(200, {"id": event_id, **json})

    def put(self, url, json, timeout):
        self._verifier()
        event_id = self._id(url)
        if event_id not in self.evenements:
            return Reponse(404)
        self.evenements[event_id] = json
        return Reponse(200, {"id": event_id, **json})

    def delete(self, url, timeout):
        self._verifier()
        return Reponse(204 if self.evenements.pop(self._id(url), None) else 404)

    def get(self, url, params, timeout):
        self._verifier()
        return Reponse(200, {"items": [{"id": i, **e} for i, e in self.evenements.items()]})


@override_settings(GOOGLE_AGENDA_ID="agenda@group.calendar.google.com", GOOGLE_AGENDA_CLE="/cle.json")
class AgendaGoogleTests(TestCase):
    def setUp(self):
        self.agenda = FauxAgenda()
        remplacement = mock.patch.object(google_agenda, "session", return_value=self.agenda)
        remplacement.start()
        self.addCleanup(remplacement.stop)
        self.auteur = get_user_model().objects.create_user("auteur", "a@exemple.be", "mdp")

    def _activite(self, **champs):
        champs = {"nom": "Souper", "date_debut": date(2026, 11, 7), "date_fin": date(2026, 11, 8),
                  "auteur": self.auteur, **champs}
        with self.captureOnCommitCallbacks(execute=True):
            return Activite.objects.create(**champs)

    def _reservation(self, **champs):
        champs = {"nom": "Durand", "prenom": "Luc", "adresse": "Rue Haute 5", "email": "luc@exemple.be",
                  "telephone": "0470 00 00 00", "date_debut": date(2026, 12, 5), "date_fin": date(2026, 12, 5),
                  **champs}
        with self.captureOnCommitCallbacks(execute=True):
            return Reservation.objects.create(**champs)

    def _enregistrer(self, objet):
        with self.captureOnCommitCallbacks(execute=True):
            objet.save()
        objet.refresh_from_db()

    def test_activite_creee_modifiee_supprimee(self):
        activite = self._activite()
        activite.refresh_from_db()
        evenement = self.agenda.evenements[activite.google_event_id]
        self.assertEqual(evenement["summary"], "Souper")
        # Journée entière : la fin est le lendemain du dernier jour
        self.assertEqual((evenement["start"], evenement["end"]), ({"date": "2026-11-07"}, {"date": "2026-11-09"}))
        self.assertIn(f"/calendrier/activite/{activite.pk}/", evenement["description"])

        activite.nom = "Souper raclette"
        self._enregistrer(activite)
        self.assertEqual(len(self.agenda.evenements), 1)
        self.assertEqual(self.agenda.evenements[activite.google_event_id]["summary"], "Souper raclette")

        with self.captureOnCommitCallbacks(execute=True):
            activite.delete()
        self.assertEqual(self.agenda.evenements, {})

    def test_activite_privee_signalee(self):
        activite = self._activite(nom="Comité", visibilite=Activite.VISIBILITE_PRIVEE)
        activite.refresh_from_db()
        self.assertEqual(self.agenda.evenements[activite.google_event_id]["summary"], "Comité (privée)")

    def test_location_seulement_si_validee_et_sans_coordonnees(self):
        reservation = self._reservation()
        self.assertEqual(self.agenda.evenements, {})  # en attente

        reservation.statut = Reservation.STATUT_VALIDEE
        self._enregistrer(reservation)
        evenement = self.agenda.evenements[reservation.google_event_id]
        self.assertEqual(evenement["summary"], "Location de salle — Luc Durand")
        self.assertNotIn("luc@exemple.be", str(evenement))
        self.assertNotIn("0470", str(evenement))

        reservation.statut = Reservation.STATUT_ANNULEE
        self._enregistrer(reservation)
        self.assertEqual(self.agenda.evenements, {})
        self.assertEqual(reservation.google_event_id, "")

    def test_evenement_supprime_dans_google_recree(self):
        activite = self._activite()
        activite.refresh_from_db()
        self.agenda.evenements.clear()
        self._enregistrer(activite)
        self.assertEqual(list(self.agenda.evenements), [activite.google_event_id])

    def test_panne_de_google_sans_erreur_sur_le_site(self):
        self.agenda.en_panne = True
        with self.assertLogs("calendrier", level="ERROR"):
            activite = self._activite()
        activite.refresh_from_db()
        self.assertEqual(activite.google_event_id, "")

    def test_commande_rattrape_et_nettoie(self):
        self.agenda.en_panne = True
        with self.assertLogs("calendrier", level="ERROR"):
            activite = self._activite()
        self.agenda.en_panne = False
        # Événement d'une activité supprimée pendant une panne, et événement
        # ajouté à la main dans Google (sans la marque du site)
        self.agenda.evenements["orphelin"] = {"extendedProperties": {"private": {"concorde_site": "activite-999"}}}
        self.agenda.evenements["a-la-main"] = {"summary": "Réunion Google"}

        call_command("synchroniser_agenda_google", stdout=StringIO())

        activite.refresh_from_db()
        self.assertEqual(set(self.agenda.evenements), {activite.google_event_id, "a-la-main"})

    @override_settings(GOOGLE_AGENDA_ID="")
    def test_desactive_sans_reglages(self):
        self._activite()
        self.assertEqual(self.agenda.evenements, {})
        with self.assertRaises(CommandError):
            call_command("synchroniser_agenda_google", stdout=StringIO())

    def test_action_d_administration_valider(self):
        from django.contrib.admin.sites import site
        from django.test import RequestFactory

        reservation = self._reservation()
        admin_reservation = site._registry[Reservation]
        requete = RequestFactory().post("/")
        requete.user = get_user_model().objects.create_superuser("chef", "c@exemple.be", "mdp")
        with mock.patch.object(admin_reservation, "message_user"):
            admin_reservation.valider_les_reservations(requete, Reservation.objects.filter(statut=Reservation.STATUT_ATTENTE))
        reservation.refresh_from_db()
        self.assertIn(reservation.google_event_id, self.agenda.evenements)
