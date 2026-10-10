"""
Tests de l'application calendrier :
- demande publique de réservation de salle : protection anti-spam (champ
  piège et limite par adresse IP) ;
- permissions : visibilité des activités privées et des réservations,
  droits de l'auteur, du membre connecté et de l'administrateur.

Lancement : python manage.py test calendrier
"""
import io
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from pypdf import PdfWriter

from .models import Activite, AnnexeContrat, ArticleContrat, Reservation
from .views import LIMITE_DEMANDES_PAR_IP


@override_settings(
    CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}},
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


def _pdf_vierge():
    tampon = io.BytesIO()
    pdf = PdfWriter()
    pdf.add_blank_page(width=595, height=842)
    pdf.write(tampon)
    return tampon.getvalue()


class PermissionsTests(TestCase):
    """Quatre profils : visiteur anonyme, membre (auteur de l'activité),
    autre membre, administrateur (is_staff)."""

    @classmethod
    def setUpTestData(cls):
        Utilisateur = get_user_model()
        cls.auteur = Utilisateur.objects.create_user("auteur", password="mdp")
        cls.autre_membre = Utilisateur.objects.create_user("autre", password="mdp")
        cls.admin = Utilisateur.objects.create_user("admin", password="mdp", is_staff=True)

        cls.jour = date.today() + timedelta(days=60)
        cls.activite_publique = Activite.objects.create(
            nom="Atelier public", date_debut=cls.jour, date_fin=cls.jour,
            visibilite=Activite.VISIBILITE_PUBLIQUE, auteur=cls.auteur,
        )
        cls.activite_privee = Activite.objects.create(
            nom="Réunion du comité", date_debut=cls.jour, date_fin=cls.jour,
            visibilite=Activite.VISIBILITE_PRIVEE, auteur=cls.auteur,
        )
        cls.reservation = Reservation.objects.create(
            nom="Durand", prenom="Luc", adresse="Rue Haute 5, 1000 Bruxelles",
            email="luc.durand@exemple.be", telephone="0470 00 00 00",
            date_debut=cls.jour + timedelta(days=3), date_fin=cls.jour + timedelta(days=3),
        )
        cls.article = ArticleContrat.objects.create(ordre=10, titre="ARTICLE 1", texte="Objet du contrat.")
        cls.annexe = AnnexeContrat.objects.create(
            ordre=10, titre="Annexe I", fichier=SimpleUploadedFile("annexe.pdf", _pdf_vierge()),
        )

    def _url_mois(self):
        return reverse("calendrier:mois", args=[self.jour.year, self.jour.month])

    def assertAccesRefuse(self, reponse):
        """Refus = 403, ou redirection vers la page de connexion."""
        if reponse.status_code == 302:
            self.assertTrue(reponse.url.startswith(reverse("login")), reponse.url)
        else:
            self.assertEqual(reponse.status_code, 403)

    # ── Visibilité des activités ──────────────────────────────────────────

    def test_activite_privee_invisible_pour_un_visiteur(self):
        reponse = self.client.get(reverse("calendrier:activite_detail", args=[self.activite_privee.pk]))
        self.assertEqual(reponse.status_code, 403)

        reponse = self.client.get(self._url_mois())
        self.assertContains(reponse, "Atelier public")
        self.assertNotContains(reponse, "Réunion du comité")

    def test_activite_privee_visible_pour_un_membre(self):
        self.client.force_login(self.autre_membre)
        reponse = self.client.get(reverse("calendrier:activite_detail", args=[self.activite_privee.pk]))
        self.assertEqual(reponse.status_code, 200)
        self.assertContains(self.client.get(self._url_mois()), "Réunion du comité")

    # ── Ajout d'une activité ──────────────────────────────────────────────

    def test_ajout_activite_reserve_aux_membres(self):
        reponse = self.client.get(reverse("calendrier:activite_ajouter"))
        self.assertAccesRefuse(reponse)

    def test_auteur_impose_par_le_serveur(self):
        self.client.force_login(self.autre_membre)
        self.client.post(reverse("calendrier:activite_ajouter"), {
            "nom": "Chorale", "date_debut": self.jour.isoformat(), "date_fin": self.jour.isoformat(),
            "visibilite": Activite.VISIBILITE_PUBLIQUE, "auteur": self.admin.pk,
        })
        self.assertEqual(Activite.objects.get(nom="Chorale").auteur, self.autre_membre)

    # ── Modification / suppression d'une activité ─────────────────────────

    def _modifier(self, nouveau_nom):
        return self.client.post(
            reverse("calendrier:activite_modifier", args=[self.activite_publique.pk]),
            {
                "nom": nouveau_nom, "date_debut": self.jour.isoformat(), "date_fin": self.jour.isoformat(),
                "visibilite": Activite.VISIBILITE_PUBLIQUE,
            },
        )

    def _nom_activite(self):
        return Activite.objects.get(pk=self.activite_publique.pk).nom

    def test_visiteur_ne_peut_ni_modifier_ni_supprimer(self):
        self.assertAccesRefuse(self._modifier("Piraté"))
        self.assertAccesRefuse(
            self.client.post(reverse("calendrier:activite_supprimer", args=[self.activite_publique.pk]))
        )
        self.assertEqual(self._nom_activite(), "Atelier public")

    def test_autre_membre_ne_peut_ni_modifier_ni_supprimer(self):
        self.client.force_login(self.autre_membre)
        self.assertEqual(self._modifier("Piraté").status_code, 403)
        reponse = self.client.post(reverse("calendrier:activite_supprimer", args=[self.activite_publique.pk]))
        self.assertEqual(reponse.status_code, 403)
        self.assertEqual(self._nom_activite(), "Atelier public")

    def test_auteur_peut_modifier_et_supprimer(self):
        self.client.force_login(self.auteur)
        self.assertEqual(self._modifier("Atelier renommé").status_code, 302)
        self.assertEqual(self._nom_activite(), "Atelier renommé")

        self.client.post(reverse("calendrier:activite_supprimer", args=[self.activite_publique.pk]))
        self.assertFalse(Activite.objects.filter(pk=self.activite_publique.pk).exists())

    def test_administrateur_peut_modifier_l_activite_d_un_autre(self):
        self.client.force_login(self.admin)
        self.assertEqual(self._modifier("Corrigé par l'admin").status_code, 302)
        self.assertEqual(self._nom_activite(), "Corrigé par l'admin")

    # ── Réservations de salle : données réservées aux administrateurs ─────

    def test_calendrier_ne_montre_pas_les_demandes_aux_non_administrateurs(self):
        for utilisateur in (None, self.autre_membre):
            with self.subTest(utilisateur=utilisateur):
                if utilisateur:
                    self.client.force_login(utilisateur)
                self.assertNotContains(self.client.get(self._url_mois()), "Durand")

        self.client.force_login(self.admin)
        self.assertContains(self.client.get(self._url_mois()), "Durand")

    def test_salle_reservee_visible_par_tous_sans_coordonnees(self):
        self.reservation.statut = Reservation.STATUT_VALIDEE
        self.reservation.save()

        reponse = self.client.get(self._url_mois())
        self.assertContains(reponse, "Salle réservée")
        self.assertNotContains(reponse, "Durand")

    def _pages_administrateur(self):
        r, a, x = self.reservation.pk, self.article.pk, self.annexe.pk
        return [
            reverse("calendrier:reservation_liste"),
            reverse("calendrier:reservation_ajouter"),
            reverse("calendrier:reservation_detail", args=[r]),
            reverse("calendrier:reservation_modifier", args=[r]),
            reverse("calendrier:reservation_supprimer", args=[r]),
            reverse("calendrier:reservation_contrat", args=[r]),
            reverse("calendrier:reservation_contrat_pdf", args=[r]),
            reverse("calendrier:suivi_paiements"),
            reverse("calendrier:modele_contrat"),
            reverse("calendrier:modele_contrat_apercu"),
            reverse("calendrier:mise_en_page_contrat"),
            reverse("calendrier:article_contrat_ajouter"),
            reverse("calendrier:article_contrat_modifier", args=[a]),
            reverse("calendrier:article_contrat_supprimer", args=[a]),
            reverse("calendrier:annexe_contrat_ajouter"),
            reverse("calendrier:annexe_contrat_modifier", args=[x]),
            reverse("calendrier:annexe_contrat_supprimer", args=[x]),
        ]

    def test_pages_administrateur_refusees_aux_visiteurs_et_membres(self):
        for utilisateur in (None, self.auteur):
            if utilisateur:
                self.client.force_login(utilisateur)
            for url in self._pages_administrateur():
                with self.subTest(utilisateur=utilisateur, url=url):
                    self.assertAccesRefuse(self.client.get(url))

    def test_pages_administrateur_accessibles_a_l_administrateur(self):
        self.client.force_login(self.admin)
        # Le contrat et son PDF n'existent pas encore pour cette demande :
        # ces deux pages sont testées à part.
        pages = [u for u in self._pages_administrateur() if "/contrat/" not in u or "contrat-type" in u]
        for url in pages:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_membre_ne_peut_pas_valider_ni_supprimer_une_demande(self):
        self.client.force_login(self.auteur)

        self.assertAccesRefuse(self.client.post(
            reverse("calendrier:reservation_traiter", args=[self.reservation.pk]), {"action": "valider"}
        ))
        self.assertAccesRefuse(self.client.post(
            reverse("calendrier:reservation_supprimer", args=[self.reservation.pk])
        ))
        self.assertAccesRefuse(self.client.post(
            reverse("calendrier:article_contrat_supprimer", args=[self.article.pk])
        ))

        self.reservation.refresh_from_db()
        self.assertEqual(self.reservation.statut, Reservation.STATUT_ATTENTE)
        self.assertTrue(ArticleContrat.objects.filter(pk=self.article.pk).exists())

    def test_administrateur_peut_valider_une_demande(self):
        self.client.force_login(self.admin)
        self.client.post(reverse("calendrier:reservation_traiter", args=[self.reservation.pk]), {"action": "valider"})
        self.reservation.refresh_from_db()
        self.assertEqual(self.reservation.statut, Reservation.STATUT_VALIDEE)

    # ── Clic sur une case du calendrier ───────────────────────────────────

    def _clic_jour(self):
        return self.client.get(
            reverse("calendrier:jour_action", args=[self.jour.year, self.jour.month, self.jour.day])
        )

    def test_clic_jour_selon_le_profil(self):
        date_str = self.jour.isoformat()

        reponse = self._clic_jour()
        self.assertRedirects(
            reponse, f"{reverse('calendrier:reservation_demander')}?date={date_str}", fetch_redirect_response=False
        )

        self.client.force_login(self.auteur)
        self.assertRedirects(
            self._clic_jour(), f"{reverse('calendrier:activite_ajouter')}?date={date_str}",
            fetch_redirect_response=False,
        )

        self.client.force_login(self.admin)
        reponse = self._clic_jour()
        self.assertEqual(reponse.status_code, 200)
        self.assertContains(reponse, reverse("calendrier:reservation_ajouter"))
