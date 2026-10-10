"""
Tests du placement automatique en salle (theatre/placement.py).

- Fonctions de calcul (sans base de données) : configuration de salle,
  numérotation, blocs contigus, scores, ordre de traitement.
- Génération complète d'un plan (placer_reservations) : règles qui doivent
  toujours tenir (chaque réservation reçoit son nombre de places, aucune
  place attribuée deux fois, toutes les places du plan sont soit
  réservées soit libres) et respect des préférences.

Lancement : python manage.py test theatre
"""
from datetime import date, timedelta
from decimal import Decimal
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from django.utils import timezone

from .models import PlaceLibre, PlaceReservee, PlanSalle, Representation, Reservation, Ticket
from .placement import (
    Case, appliquer_placement, creer_grille, determiner_configuration, placement_force,
    placer_reservations, score_colonne, score_rangee, trier_reservations,
    trouver_blocs_contigus, trouver_meilleur_placement,
)


# ══════════════════════════════════════════════════════════════════════════════
#  FONCTIONS DE CALCUL
# ══════════════════════════════════════════════════════════════════════════════

class ConfigurationSalleTests(SimpleTestCase):

    def test_seuils_et_capacites(self):
        for nb_inscrits, nb_rangees, capacite in [
            (0, 10, 100), (80, 10, 100),
            (81, 11, 122), (120, 11, 122),
            (121, 12, 172), (500, 12, 172),
        ]:
            with self.subTest(nb_inscrits=nb_inscrits):
                config = determiner_configuration(nb_inscrits)
                self.assertEqual((len(config), sum(config)), (nb_rangees, capacite))

    def test_numerotation_continue_de_l_avant_vers_l_arriere(self):
        grille = creer_grille([3, 2])
        self.assertEqual(
            [[(c.rangee, c.colonne, c.numero) for c in rangee] for rangee in grille],
            [[(0, 0, 1), (0, 1, 2), (0, 2, 3)], [(1, 0, 4), (1, 1, 5)]],
        )


class BlocsContigusTests(SimpleTestCase):

    def _cases(self, *colonnes):
        return [Case(rangee=0, colonne=c, numero=c + 1) for c in colonnes]

    def test_ignore_les_trous(self):
        blocs = trouver_blocs_contigus(self._cases(0, 1, 3, 4, 5), 2)
        self.assertEqual([[c.colonne for c in b] for b in blocs], [[0, 1], [3, 4], [4, 5]])

    def test_aucun_bloc_assez_large(self):
        self.assertEqual(trouver_blocs_contigus(self._cases(0, 2, 4), 2), [])
        self.assertEqual(trouver_blocs_contigus(self._cases(0, 1), 3), [])

    def test_renvoie_des_copies_independantes(self):
        cases = self._cases(0, 1)
        bloc = trouver_blocs_contigus(cases, 2)[0]
        bloc[0].numero = None
        self.assertEqual(cases[0].numero, 1)


class ScoresTests(SimpleTestCase):

    def test_rangee_souhaitee_prioritaire_et_distance(self):
        # Rangée 3 souhaitée (index 2) : 0 sur la bonne rangée, +10 par rangée d'écart
        self.assertEqual([score_rangee(i, 10, 'arriere', '3') for i in (2, 1, 3, 0)], [0, 10, 10, 20])

    def test_preference_avant_centre_arriere(self):
        def meilleure(preference):
            return min(range(10), key=lambda i: score_rangee(i, 10, preference, ''))
        self.assertEqual(meilleure('avant'), 0)
        self.assertEqual(meilleure('arriere'), 9)
        self.assertIn(meilleure('centre'), (4, 5))
        self.assertIn(meilleure(''), (4, 5))

    def test_rangee_souhaitee_toujours_mieux_notee_qu_une_preference(self):
        self.assertLess(score_rangee(9, 10, '', '1'), score_rangee(0, 10, 'avant', ''))

    def test_preference_de_cote(self):
        # Bloc de 2 places dans une rangée de 10 : colonnes de départ possibles 0 à 8
        def meilleur_debut(cote):
            return min(range(9), key=lambda d: score_colonne(d, 10, 2, cote))
        self.assertEqual(meilleur_debut('gauche'), 0)
        self.assertEqual(meilleur_debut('droite'), 8)
        self.assertEqual(meilleur_debut('milieu'), 4)


class OrdreDeTraitementTests(SimpleTestCase):

    def _resa(self, nom, minutes, preference='', rangee=''):
        return SimpleNamespace(
            nom=nom, preference_rangee=preference, rangee_preferee=rangee,
            created_at=timezone.now() + timedelta(minutes=minutes),
        )

    def test_rangee_souhaitee_puis_avant_centre_arriere_puis_ordre_d_inscription(self):
        reservations = [
            self._resa("arrière", 0, 'arriere'),
            self._resa("centre tardif", 5, 'centre'),
            self._resa("sans préférence", 1),
            self._resa("avant", 2, 'avant'),
            self._resa("rangée 4", 9, rangee='4'),
        ]
        self.assertEqual(
            [r.nom for r in trier_reservations(reservations)],
            ["rangée 4", "avant", "sans préférence", "centre tardif", "arrière"],
        )


class RechercheDePlacementTests(SimpleTestCase):

    def test_groupe_trop_large_pour_une_rangee_sur_deux_rangees_alignees(self):
        config = [4, 4, 4]
        grille = creer_grille(config)
        placement = trouver_meilleur_placement(grille, config, 6, 'avant', '', '')

        rangees = sorted({c.rangee for c in placement.cases})
        self.assertEqual(len(placement.cases), 6)
        self.assertEqual(len(rangees), 2)
        self.assertEqual(rangees[1] - rangees[0], 1)

    def test_salle_fragmentee_placement_force(self):
        config = [3, 3]
        grille = creer_grille(config)
        # Libres : (0,0), (1,2) — ni contiguës, ni alignées
        for r, c in [(0, 1), (0, 2), (1, 0), (1, 1)]:
            grille[r][c].numero = None

        placement = trouver_meilleur_placement(grille, config, 2, '', '', '')
        self.assertEqual(sorted(c.numero for c in placement.cases), [1, 6])

    def test_salle_pleine(self):
        grille = creer_grille([2])
        self.assertIsNone(placement_force(grille, 3))

    def test_appliquer_placement_occupe_les_cases(self):
        config = [4]
        grille = creer_grille(config)
        placement = trouver_meilleur_placement(grille, config, 2, '', '', 'gauche')
        self.assertEqual([c.numero for c in placement.snapshot()], [1, 2])

        appliquer_placement(grille, placement)
        self.assertEqual([c.numero for c in grille[0]], [None, None, 3, 4])


# ══════════════════════════════════════════════════════════════════════════════
#  GÉNÉRATION COMPLÈTE D'UN PLAN
# ══════════════════════════════════════════════════════════════════════════════

class GenerationPlanTests(TestCase):

    def setUp(self):
        self.rep = Representation.objects.create(
            nom="Le Bourgeois gentilhomme", date=date(2026, 12, 12),
            prix_adulte=Decimal("12"), prix_enfant=Decimal("8"),
        )
        self._minutes = 0

    def _resa(self, adultes, enfants=0, preference='', cote='', rangee='', nom="Spectateur"):
        resa = Reservation.objects.create(
            representation=self.rep, nom=nom, prenom="X", nb_adultes=adultes, nb_enfants=enfants,
            preference_rangee=preference, preference_cote=cote, rangee_preferee=rangee,
        )
        # Ordre d'inscription explicite (created_at départage les ex aequo)
        self._minutes += 1
        Reservation.objects.filter(pk=resa.pk).update(
            created_at=timezone.now() - timedelta(days=1) + timedelta(minutes=self._minutes)
        )
        return resa

    def _places(self, resa):
        return list(PlaceReservee.objects.filter(reservation=resa).order_by('numero_place'))

    def assertPlanCoherent(self, plan):
        """Règles qui doivent toujours tenir, quel que soit le remplissage."""
        reservees = list(PlaceReservee.objects.filter(plan_salle=plan))
        libres = list(PlaceLibre.objects.filter(plan_salle=plan))
        numeros = [p.numero_place for p in reservees] + [p.numero_place for p in libres]

        # Chaque place du plan existe une seule fois, réservée ou libre
        self.assertEqual(sorted(numeros), list(range(1, plan.nb_total_places + 1)))
        self.assertEqual(plan.nb_total_places, sum(plan.configuration))
        self.assertEqual(plan.nb_rangees, len(plan.configuration))

        # Numéro, rangée et colonne correspondent à la numérotation de la grille
        grille = creer_grille(plan.configuration)
        for place in reservees + libres:
            self.assertEqual(grille[place.rangee][place.colonne].numero, place.numero_place)

    def assertBlocContigu(self, places):
        self.assertEqual(len({p.rangee for p in places}), 1, "places sur plusieurs rangées")
        colonnes = sorted(p.colonne for p in places)
        self.assertEqual(colonnes, list(range(colonnes[0], colonnes[0] + len(colonnes))))

    def test_salle_remplie_de_maniere_realiste(self):
        preferences = ['', 'avant', 'centre', 'arriere']
        cotes = ['', 'gauche', 'milieu', 'droite']
        reservations = []
        for i in range(40):
            reservations.append(self._resa(
                adultes=1 + i % 3, enfants=i % 4 // 2,
                preference=preferences[i % 4], cote=cotes[(i // 4) % 4],
                rangee=str(1 + i % 6) if i % 7 == 0 else '',
            ))
        nb_inscrits = sum(r.total_places() for r in reservations)

        plan = placer_reservations(self.rep)

        self.assertEqual(sum(plan.configuration), sum(determiner_configuration(nb_inscrits)))
        self.assertPlanCoherent(plan)
        for resa in reservations:
            with self.subTest(reservation=resa.pk, places=resa.total_places()):
                places = self._places(resa)
                self.assertEqual(len(places), resa.total_places())
                # Salle peu remplie : chaque groupe reste ensemble sur une rangée
                self.assertBlocContigu(places)

    def test_rangee_souhaitee_respectee(self):
        resa = self._resa(adultes=2, rangee='3')
        placer_reservations(self.rep)
        self.assertEqual({p.rangee for p in self._places(resa)}, {2})

    def test_preferences_avant_arriere_et_cote(self):
        avant_gauche = self._resa(adultes=2, preference='avant', cote='gauche')
        arriere_droite = self._resa(adultes=2, preference='arriere', cote='droite')

        plan = placer_reservations(self.rep)

        self.assertEqual([(p.rangee, p.colonne) for p in self._places(avant_gauche)], [(0, 0), (0, 1)])
        derniere = plan.nb_rangees - 1
        largeur = plan.configuration[derniere]
        self.assertEqual(
            [(p.rangee, p.colonne) for p in self._places(arriere_droite)],
            [(derniere, largeur - 2), (derniere, largeur - 1)],
        )

    def test_premier_inscrit_prioritaire_sur_les_meilleures_places(self):
        premier = self._resa(adultes=2, preference='avant', cote='gauche', nom="Premier")
        second = self._resa(adultes=2, preference='avant', cote='gauche', nom="Second")

        placer_reservations(self.rep)

        self.assertEqual([p.colonne for p in self._places(premier)], [0, 1])
        self.assertEqual([p.colonne for p in self._places(second)], [2, 3])

    def test_groupe_plus_large_qu_une_rangee_sur_deux_rangees(self):
        resa = self._resa(adultes=12, preference='avant')   # rangées de 10 places
        placer_reservations(self.rep)

        places = self._places(resa)
        rangees = sorted({p.rangee for p in places})
        self.assertEqual(len(places), 12)
        self.assertEqual(len(rangees), 2)
        self.assertEqual(rangees[1] - rangees[0], 1)

    def test_reservation_sans_place_ignoree(self):
        vide = self._resa(adultes=0)
        plan = placer_reservations(self.rep)
        self.assertEqual(self._places(vide), [])
        self.assertEqual(PlaceLibre.objects.filter(plan_salle=plan).count(), 100)

    def test_salle_complete_au_dela_de_la_capacite(self):
        # 180 places demandées pour 172 : aucune place attribuée deux fois,
        # et seules des réservations entières sont placées.
        reservations = [self._resa(adultes=4) for _ in range(45)]

        plan = placer_reservations(self.rep)

        self.assertEqual(plan.nb_total_places, 172)
        self.assertPlanCoherent(plan)
        nb_places = [len(self._places(r)) for r in reservations]
        self.assertTrue(all(n in (0, 4) for n in nb_places), nb_places)
        self.assertEqual(sum(nb_places), 172)
        # Les 2 dernières inscrites, signalées pour avertir l'utilisateur
        self.assertEqual(plan.reservations_non_placees, reservations[-2:])
        self.assertEqual([len(self._places(r)) for r in reservations[-2:]], [0, 0])

    def test_aucune_reservation_non_placee_quand_la_salle_suffit(self):
        self._resa(adultes=4)
        self.assertEqual(placer_reservations(self.rep).reservations_non_placees, [])

    def test_generation_depuis_le_site_avertit_des_reservations_sans_place(self):
        for i in range(45):
            self._resa(adultes=4, nom=f"Famille{i:02d}")
        self.client.force_login(get_user_model().objects.create_superuser("admin", "a@exemple.be", "mdp"))

        reponse = self.client.post(reverse("plan_salle_generer", args=[self.rep.pk]))

        avertissements = [str(m) for m in get_messages(reponse.wsgi_request) if m.level_tag == "warning"]
        self.assertEqual(len(avertissements), 1)
        self.assertIn("2 réservation(s) sans place", avertissements[0])
        self.assertIn("Famille43 X (4 places)", avertissements[0])
        self.assertIn("Famille44 X (4 places)", avertissements[0])

    def test_generation_depuis_le_site_sans_avertissement_si_tout_est_place(self):
        self._resa(adultes=2)
        self.client.force_login(get_user_model().objects.create_superuser("admin", "a@exemple.be", "mdp"))

        reponse = self.client.post(reverse("plan_salle_generer", args=[self.rep.pk]))

        niveaux = [m.level_tag for m in get_messages(reponse.wsgi_request)]
        self.assertEqual(niveaux, ["success"])

    def test_regeneration_remplace_l_ancien_plan(self):
        resa = self._resa(adultes=2)
        ancien = placer_reservations(self.rep)
        Ticket.objects.create(place=self._places(resa)[0], prix_unitaire=Decimal("12"))

        self._resa(adultes=3)
        nouveau = placer_reservations(self.rep)

        self.assertEqual(PlanSalle.objects.filter(representation=self.rep).count(), 1)
        self.assertFalse(PlanSalle.objects.filter(pk=ancien.pk).exists())
        self.assertFalse(Ticket.objects.exists())   # supprimés avec l'ancien plan
        self.assertPlanCoherent(nouveau)
