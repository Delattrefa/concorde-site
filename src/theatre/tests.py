"""
Tests de la billetterie (contrôle d'entrée, vente flash, zone tampon).

Lancement : python manage.py test theatre
"""
import json
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import (
    PlaceLibre, PlaceReservee, PlanSalle, Representation, Reservation, Ticket,
    VenteFlash, ZoneTampon,
)


class BilletterieTests(TestCase):
    """Une rangée de 4 places : 1 et 2 réservées par Dupont (1 adulte,
    1 enfant), 3 et 4 libres (vente flash)."""

    def setUp(self):
        self.client.force_login(
            get_user_model().objects.create_superuser("admin", "admin@exemple.be", "mdp")
        )
        self.rep = Representation.objects.create(
            nom="Le Malade imaginaire", date=date(2026, 12, 5),
            prix_adulte=Decimal("12.50"), prix_enfant=Decimal("7.30"),
        )
        self.plan = PlanSalle.objects.create(
            representation=self.rep, nb_rangees=1, configuration=[4], nb_total_places=4,
        )
        self.resa = Reservation.objects.create(
            representation=self.rep, nom="Dupont", prenom="Marie", nb_adultes=1, nb_enfants=1,
        )
        self.place1 = PlaceReservee.objects.create(
            plan_salle=self.plan, reservation=self.resa, numero_place=1, rangee=0, colonne=0,
        )
        self.place2 = PlaceReservee.objects.create(
            plan_salle=self.plan, reservation=self.resa, numero_place=2, rangee=0, colonne=1,
        )
        self.libre3 = PlaceLibre.objects.create(plan_salle=self.plan, numero_place=3, rangee=0, colonne=2)
        self.libre4 = PlaceLibre.objects.create(plan_salle=self.plan, numero_place=4, rangee=0, colonne=3)

    def _post(self, nom_url, args, donnees):
        corps = donnees if isinstance(donnees, str) else json.dumps(donnees)
        return self.client.post(
            reverse(nom_url, args=args), corps, content_type="application/json",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

    def _valider(self, *places):
        return self._post("valider_entree", [self.rep.pk], {"place_ids": [p.pk for p in places]})

    def _vendre(self, place, tarif="adulte"):
        return self._post("vente_flash", [self.plan.pk], {
            "place_libre_id": place.pk, "nom": "Martin", "prenom": "Paul", "tarif": tarif,
        })

    # ── Contrôle d'entrée ──────────────────────────────────────────────────

    def test_valider_entree_tarifs_exacts(self):
        reponse = self._valider(self.place1, self.place2)

        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(Ticket.objects.get(place=self.place1).prix_unitaire, Decimal("12.50"))
        self.assertEqual(Ticket.objects.get(place=self.place2).prix_unitaire, Decimal("7.30"))
        self.assertEqual(reponse.json()["ca_total"], 19.8)

    def test_valider_deux_fois_ne_cree_pas_de_doublon(self):
        self._valider(self.place1)
        reponse = self._valider(self.place1)

        self.assertEqual(reponse.json()["tickets"], [])
        self.assertEqual(Ticket.objects.count(), 1)

    def test_ca_inclut_les_ventes_flash(self):
        self._vendre(self.libre3)                       # 12,50
        reponse = self._valider(self.place1)           # + 12,50
        self.assertEqual(reponse.json()["ca_total"], 25.0)

        ticket = Ticket.objects.get(place=self.place1)
        reponse = self._post("annuler_ticket", [ticket.pk], {})
        self.assertEqual(reponse.json()["ca_total"], 12.5)

    def test_donnees_json_invalides_400_et_non_500(self):
        for corps in ("pas du json", "[1, 2]", '{"place_ids": "abc"}', '{"place_ids": 5}', "{}"):
            with self.subTest(corps=corps):
                self.assertEqual(self._post("valider_entree", [self.rep.pk], corps).status_code, 400)
        for corps in ("[]", '{"place_libre_id": 1, "nom": 5, "prenom": "x", "tarif": "adulte"}'):
            with self.subTest(corps=corps):
                self.assertEqual(self._post("vente_flash", [self.plan.pk], corps).status_code, 400)

    def test_annuler_ticket_deja_annule_garde_la_date(self):
        self._valider(self.place1)
        ticket = Ticket.objects.get(place=self.place1)
        self._post("annuler_ticket", [ticket.pk], {})
        annule_le = Ticket.objects.get(pk=ticket.pk).annule_le

        self._post("annuler_ticket", [ticket.pk], {})
        self.assertEqual(Ticket.objects.get(pk=ticket.pk).annule_le, annule_le)

    # ── Vente flash ────────────────────────────────────────────────────────

    def test_revendre_une_place_apres_annulation(self):
        self._vendre(self.libre3)
        vente = VenteFlash.objects.get()
        self._post("annuler_vente_flash", [vente.pk], {})

        reponse = self._vendre(self.libre3, tarif="enfant")

        self.assertEqual(reponse.status_code, 200)
        vente = VenteFlash.objects.get()
        self.assertEqual((vente.statut, vente.prix), ("valide", Decimal("7.30")))

    def test_place_deja_vendue_refusee(self):
        self._vendre(self.libre3)
        reponse = self._vendre(self.libre3)
        self.assertEqual(reponse.status_code, 400)
        self.assertIn("déjà vendue", reponse.json()["erreur"])

    def test_tarif_inconnu_refuse(self):
        self.assertEqual(self._vendre(self.libre3, tarif="vip").status_code, 400)
        self.assertFalse(VenteFlash.objects.exists())

    # ── Zone tampon ────────────────────────────────────────────────────────

    def _mettre_en_tampon(self):
        reponse = self._post("mettre_en_tampon", [self.plan.pk], {"reservation_id": self.resa.pk})
        self.assertEqual(reponse.status_code, 200, reponse.content)
        return ZoneTampon.objects.get()

    def _numeros_de(self, reservation):
        return sorted(PlaceReservee.objects.filter(reservation=reservation).values_list("numero_place", flat=True))

    def test_retirer_du_tampon_rend_les_places_d_origine(self):
        tampon = self._mettre_en_tampon()
        self.assertEqual(self._numeros_de(self.resa), [])

        reponse = self._post("retirer_du_tampon", [tampon.pk], {})

        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(self._numeros_de(self.resa), [1, 2])
        self.assertEqual(sorted(PlaceLibre.objects.values_list("numero_place", flat=True)), [3, 4])
        self.assertFalse(ZoneTampon.objects.exists())

    def test_retirer_refuse_si_une_place_d_origine_est_vendue(self):
        tampon = self._mettre_en_tampon()
        self._vendre(PlaceLibre.objects.get(numero_place=1))

        reponse = self._post("retirer_du_tampon", [tampon.pk], {})

        self.assertEqual(reponse.status_code, 400)
        self.assertTrue(ZoneTampon.objects.filter(pk=tampon.pk).exists())
        self.assertEqual(self._numeros_de(self.resa), [])

    def test_retirer_refuse_pour_un_ancien_tampon(self):
        tampon = self._mettre_en_tampon()
        tampon.places_liberes = [self.place1.pk, self.place2.pk]   # ancien format
        tampon.save()

        self.assertEqual(self._post("retirer_du_tampon", [tampon.pk], {}).status_code, 400)
        self.assertTrue(ZoneTampon.objects.filter(pk=tampon.pk).exists())

    def test_placer_depuis_tampon(self):
        tampon = self._mettre_en_tampon()
        reponse = self._post("placer_depuis_tampon", [self.plan.pk], {
            "tampon_id": tampon.pk, "place_ids": [self.libre3.pk, self.libre4.pk],
        })

        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(self._numeros_de(self.resa), [3, 4])
        self.assertEqual(sorted(PlaceLibre.objects.values_list("numero_place", flat=True)), [1, 2])

    def test_mettre_en_tampon_reservation_d_une_autre_representation(self):
        autre = Representation.objects.create(
            nom="Autre", date=date(2026, 12, 6), prix_adulte=Decimal("10"), prix_enfant=Decimal("5"),
        )
        resa = Reservation.objects.create(representation=autre, nom="X", prenom="Y", nb_adultes=1)
        reponse = self._post("mettre_en_tampon", [self.plan.pk], {"reservation_id": resa.pk})
        self.assertEqual(reponse.status_code, 404)

    # ── Divers ─────────────────────────────────────────────────────────────

    def test_get_prix_identifiant_invalide(self):
        reponse = self.client.get(reverse("get_prix"), {"rep_id": "abc"})
        self.assertEqual(reponse.status_code, 404)

    def test_page_controle_entree_urls_sous_theatre(self):
        reponse = self.client.get(reverse("controle_entree", args=[self.rep.pk]))

        self.assertEqual(reponse.status_code, 200)
        for nom_url in ("annuler_ticket", "annuler_vente_flash", "retirer_du_tampon"):
            with self.subTest(nom_url=nom_url):
                url = reverse(nom_url, args=[0])
                self.assertTrue(url.startswith("/theatre/"))
                self.assertContains(reponse, url)
